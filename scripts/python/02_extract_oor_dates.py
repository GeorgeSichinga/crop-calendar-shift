"""
02_extract_oor_dates.py
-----------------------
Computes onset-of-rains (OOR) date for each Malawi district,
for each agricultural season from 1990/91 to 2023/24.

OOR Definition (FAO/FEWS NET standard):
  First day after October 1 when:
    (a) cumulative rainfall >= 25mm over 3 consecutive days, AND
    (b) no dry spell > 10 days in the following 20-day window

Outputs:
  data/processed/oor_dates.csv      — long-format: district, season, oor_doy, oor_date
  data/processed/district_summary.csv — mean OOR + trend stats per district

Usage:
    python scripts/python/02_extract_oor_dates.py
"""

import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
import rioxarray
from pathlib import Path
from tqdm import tqdm
from shapely.geometry import mapping
import warnings
warnings.filterwarnings("ignore")

RAW_DIR   = Path("data/raw/chirps")
PROC_DIR  = Path("data/processed")
PROC_DIR.mkdir(parents=True, exist_ok=True)

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_MWI_2.json"


def load_malawi_districts() -> gpd.GeoDataFrame:
    """Load Malawi district boundaries (GADM level 2)."""
    gadm_path = Path("data/raw/gadm_malawi_districts.geojson")
    if not gadm_path.exists():
        print("  Downloading Malawi district boundaries...")
        import requests
        r = requests.get(GADM_URL, timeout=60)
        gadm_path.write_bytes(r.content)
    gdf = gpd.read_file(gadm_path)
    gdf = gdf[["NAME_2", "geometry"]].rename(columns={"NAME_2": "district"})
    return gdf.to_crs("EPSG:4326")


def detect_oor(daily_rain: np.ndarray, start_doy: int = 275) -> int:
    """
    Detect onset-of-rains date index within a season array.

    Args:
        daily_rain: array of daily rainfall (mm) for Oct–Apr
        start_doy:  day-of-year for Oct 1 (275)

    Returns:
        Day-of-year of OOR, or NaN if not detected
    """
    n = len(daily_rain)
    for i in range(n - 22):
        window3 = daily_rain[i:i+3]
        if np.sum(window3) >= 25.0:
            # Check no 10-day dry spell in next 20 days
            future = daily_rain[i+3:i+23]
            dry_run = 0
            max_dry = 0
            for r in future:
                if r < 1.0:
                    dry_run += 1
                    max_dry = max(max_dry, dry_run)
                else:
                    dry_run = 0
            if max_dry <= 10:
                return start_doy + i
    return np.nan


def extract_district_rainfall(ds: xr.Dataset, geom) -> np.ndarray:
    """Spatial mean rainfall over a district geometry."""
    clipped = ds.rio.clip([mapping(geom)], crs="EPSG:4326", drop=True, all_touched=True)
    return clipped.mean(dim=["latitude", "longitude"]).values


def main():
    print("\nLoading Malawi districts...")
    districts = load_malawi_districts()
    print(f"  {len(districts)} districts found")

    seasons = range(1990, 2024)  # 1990/91 through 2023/24
    records = []

    for season_start in tqdm(seasons, desc="Processing seasons"):
        yr1, yr2 = season_start, season_start + 1
        nc_path1 = RAW_DIR / f"chirps-v2.0.{yr1}.days_p05.nc"
        nc_path2 = RAW_DIR / f"chirps-v2.0.{yr2}.days_p05.nc"

        if not nc_path1.exists() or not nc_path2.exists():
            print(f"  [skip] Missing CHIRPS files for {yr1}/{yr2}")
            continue

        # Load Oct–Apr window
        ds1 = xr.open_dataset(nc_path1, engine="netcdf4")["precip"]
        ds2 = xr.open_dataset(nc_path2, engine="netcdf4")["precip"]

        # Rename to standard coords if needed
        for coord_map in [{"lon": "longitude", "lat": "latitude"}, {"x": "longitude", "y": "latitude"}]:
            for old, new in coord_map.items():
                if old in ds1.coords:
                    ds1 = ds1.rename({old: new})
                    ds2 = ds2.rename({old: new})

        oct_apr1 = ds1.sel(time=ds1.time.dt.month.isin([10, 11, 12]))
        jan_apr2 = ds2.sel(time=ds2.time.dt.month.isin([1, 2, 3, 4]))

        # Clip to Malawi bbox
        bbox = dict(latitude=slice(-9.2, -17.3), longitude=slice(32.5, 36.1))
        oct_apr1 = oct_apr1.sel(**bbox)
        jan_apr2 = jan_apr2.sel(**bbox)

        ds_season = xr.concat([oct_apr1, jan_apr2], dim="time")
        ds_season = ds_season.rio.set_spatial_dims(x_dim="longitude", y_dim="latitude")
        ds_season = ds_season.rio.write_crs("EPSG:4326")

        for _, row in districts.iterrows():
            try:
                rain = extract_district_rainfall(ds_season, row.geometry)
                rain = np.nan_to_num(rain, nan=0.0)
                oor_doy = detect_oor(rain)
                records.append({
                    "district": row["district"],
                    "season":   f"{yr1}/{str(yr2)[2:]}",
                    "season_start": yr1,
                    "oor_doy":  oor_doy,
                })
            except Exception as e:
                records.append({
                    "district": row["district"],
                    "season":   f"{yr1}/{str(yr2)[2:]}",
                    "season_start": yr1,
                    "oor_doy":  np.nan,
                })

        ds1.close(); ds2.close()

    df = pd.DataFrame(records)
    df.to_csv(PROC_DIR / "oor_dates.csv", index=False)
    print(f"\nSaved {len(df)} records → {PROC_DIR / 'oor_dates.csv'}")

    # Quick district summary
    summary = df.groupby("district").agg(
        mean_oor=("oor_doy", "mean"),
        std_oor=("oor_doy", "std"),
        n_seasons=("oor_doy", "count")
    ).reset_index()
    summary.to_csv(PROC_DIR / "district_summary.csv", index=False)
    print(f"District summary → {PROC_DIR / 'district_summary.csv'}")


if __name__ == "__main__":
    main()
