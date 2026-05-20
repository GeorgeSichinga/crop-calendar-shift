"""
03_export_for_r.py
------------------
Validates and exports processed OOR data for R analysis.
If real CHIRPS data hasn't been downloaded yet, generates
realistic synthetic data so the full pipeline can be tested end-to-end.

Outputs:
  data/processed/oor_for_r.csv    — clean long-format CSV for R
  data/processed/metadata.json   — pipeline run metadata

Usage:
    python scripts/python/03_export_for_r.py
    python scripts/python/03_export_for_r.py --synthetic  # force synthetic data
"""

import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

PROC_DIR = Path("data/processed")
PROC_DIR.mkdir(parents=True, exist_ok=True)

# Malawi's 28 districts
MALAWI_DISTRICTS = [
    "Balaka", "Blantyre", "Chikwawa", "Chiradzulu", "Chitipa",
    "Dedza", "Dowa", "Karonga", "Kasungu", "Lilongwe",
    "Machinga", "Mangochi", "Mchinji", "Mulanje", "Mwanza",
    "Mzimba", "Neno", "Nkhata Bay", "Nkhotakota", "Nsanje",
    "Ntcheu", "Ntchisi", "Phalombe", "Rumphi", "Salima",
    "Thyolo", "Zomba", "Likoma"
]

# Realistic regional OOR baselines (day of year, roughly Nov–Dec)
# Southern: earlier onset (~315), Northern: later (~335)
REGIONAL_BASELINE = {
    "Blantyre": 312, "Chiradzulu": 313, "Mulanje": 310, "Thyolo": 311,
    "Chikwawa": 318, "Nsanje": 315, "Phalombe": 312, "Balaka": 316,
    "Zomba": 314, "Machinga": 317, "Mangochi": 320, "Mwanza": 319,
    "Neno": 316, "Lilongwe": 325, "Dedza": 323, "Dowa": 326,
    "Ntcheu": 322, "Mchinji": 327, "Kasungu": 328, "Ntchisi": 326,
    "Nkhotakota": 324, "Salima": 322, "Mzimba": 332, "Rumphi": 334,
    "Karonga": 330, "Chitipa": 336, "Nkhata Bay": 328, "Likoma": 325,
}


def generate_synthetic_oor(seed: int = 42) -> pd.DataFrame:
    """
    Generate realistic synthetic OOR data with:
    - A positive trend (delayed onset) of ~0.4 days/year on average
    - Regional variation (south earlier, north later)
    - Inter-annual noise and ENSO-like variability
    - Occasional missing seasons (data gaps)
    """
    rng = np.random.default_rng(seed)
    records = []
    seasons = range(1990, 2024)

    # Simulate El Niño years (delayed onset) — approximate
    el_nino_years = {1991, 1994, 1997, 2002, 2004, 2009, 2015, 2018, 2023}
    la_nina_years = {1995, 1998, 1999, 2000, 2007, 2010, 2011, 2020, 2021}

    for district in MALAWI_DISTRICTS:
        baseline = REGIONAL_BASELINE.get(district, 325)
        # Each district gets a slightly different trend rate
        trend_rate = rng.uniform(0.2, 0.7)  # days delay per year

        for yr in seasons:
            t = yr - 1990  # years since baseline

            enso_effect = 0
            if yr in el_nino_years:
                enso_effect = rng.uniform(5, 14)   # delay
            elif yr in la_nina_years:
                enso_effect = rng.uniform(-10, -3)  # early onset

            noise = rng.normal(0, 6)  # inter-annual variability

            oor = baseline + trend_rate * t + enso_effect + noise

            # Occasional missing data (~4%)
            if rng.random() < 0.04:
                oor = np.nan

            records.append({
                "district":     district,
                "season":       f"{yr}/{str(yr+1)[2:]}",
                "season_start": yr,
                "oor_doy":      round(oor, 1) if not np.isnan(oor) else np.nan,
                "data_source":  "synthetic"
            })

    df = pd.DataFrame(records)
    print(f"  Generated {len(df)} synthetic records for {len(MALAWI_DISTRICTS)} districts × {len(seasons)} seasons")
    return df


def load_real_oor() -> pd.DataFrame:
    real_path = PROC_DIR / "oor_dates.csv"
    df = pd.read_csv(real_path)
    df["data_source"] = "CHIRPS_v2"
    return df


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add useful derived columns for R analysis."""
    # Convert DOY to approximate calendar date (using a non-leap reference year)
    def doy_to_approx_date(doy):
        if pd.isna(doy):
            return pd.NaT
        try:
            return pd.Timestamp("2000-01-01") + pd.Timedelta(days=int(doy) - 1)
        except:
            return pd.NaT

    df["oor_date_approx"] = df["oor_doy"].apply(doy_to_approx_date)
    df["oor_month"] = df["oor_date_approx"].dt.month
    df["oor_month_name"] = df["oor_date_approx"].dt.strftime("%B")

    # Decade for grouping
    df["decade"] = ((df["season_start"] // 10) * 10).astype(str) + "s"

    # Region classification
    south = {"Blantyre","Chiradzulu","Mulanje","Thyolo","Chikwawa",
              "Nsanje","Phalombe","Balaka","Zomba","Machinga",
              "Mangochi","Mwanza","Neno"}
    central = {"Lilongwe","Dedza","Dowa","Ntcheu","Mchinji",
               "Kasungu","Ntchisi","Nkhotakota","Salima"}
    north = {"Mzimba","Rumphi","Karonga","Chitipa","Nkhata Bay","Likoma"}

    def classify_region(d):
        if d in south: return "Southern"
        if d in central: return "Central"
        if d in north: return "Northern"
        return "Unknown"

    df["region"] = df["district"].apply(classify_region)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true",
                        help="Force synthetic data generation")
    args = parser.parse_args()

    real_exists = (PROC_DIR / "oor_dates.csv").exists()

    if args.synthetic or not real_exists:
        if not real_exists:
            print("  No real OOR data found — generating synthetic data for pipeline testing...")
        else:
            print("  --synthetic flag set — generating synthetic data...")
        df = generate_synthetic_oor()
    else:
        print("  Loading real CHIRPS-derived OOR data...")
        df = load_real_oor()

    df = add_derived_columns(df)

    out_path = PROC_DIR / "oor_for_r.csv"
    df.to_csv(out_path, index=False)
    print(f"\nExported {len(df)} rows → {out_path}")
    print(f"Columns: {list(df.columns)}")
    print(f"\nMissing OOR values: {df['oor_doy'].isna().sum()} ({df['oor_doy'].isna().mean()*100:.1f}%)")
    print(f"Seasons: {df['season_start'].min()}–{df['season_start'].max()}")
    print(f"Districts: {df['district'].nunique()}")

    # Save metadata
    meta = {
        "generated_at": datetime.now().isoformat(),
        "data_source": df["data_source"].iloc[0] if "data_source" in df.columns else "unknown",
        "n_records": len(df),
        "n_districts": df["district"].nunique(),
        "season_range": [int(df["season_start"].min()), int(df["season_start"].max())],
        "missing_pct": round(df["oor_doy"].isna().mean() * 100, 2)
    }
    with open(PROC_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\nMetadata saved → {PROC_DIR / 'metadata.json'}")


if __name__ == "__main__":
    main()
