"""
01_download_chirps.py
---------------------
Downloads CHIRPS v2.0 daily rainfall NetCDF files for Malawi
bounding box: lat -17.1 to -9.4, lon 32.7 to 35.9

CHIRPS data is freely available — no API key required.
Files are ~200MB per year. Downloads 1990–2024 by default.

Usage:
    python scripts/python/01_download_chirps.py
    python scripts/python/01_download_chirps.py --years 2010 2020
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from tqdm import tqdm

RAW_DIR = Path("data/raw/chirps")
RAW_DIR.mkdir(parents=True, exist_ok=True)

CHIRPS_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_daily/tifs/p05"

# Malawi bounding box (with small buffer)
BBOX = {"min_lon": 32.5, "max_lon": 36.1, "min_lat": -17.3, "max_lat": -9.2}


def download_year(year: int, force: bool = False) -> Path:
    """Download CHIRPS annual NetCDF for a given year."""
    filename = f"chirps-v2.0.{year}.days_p05.nc"
    url = f"{CHIRPS_BASE}/{filename}"
    dest = RAW_DIR / filename

    if dest.exists() and not force:
        print(f"  [skip] {filename} already exists")
        return dest

    print(f"  Downloading {year}...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc=str(year), leave=False
    ) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

    return dest


def main():
    parser = argparse.ArgumentParser(description="Download CHIRPS daily rainfall")
    parser.add_argument(
        "--years", nargs="+", type=int,
        default=list(range(1990, 2025)),
        help="Years to download (default: 1990–2024)"
    )
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    args = parser.parse_args()

    print(f"\nDownloading CHIRPS data for {len(args.years)} years → {RAW_DIR}\n")
    failed = []

    for year in args.years:
        try:
            download_year(year, force=args.force)
        except Exception as e:
            print(f"  [error] {year}: {e}")
            failed.append(year)

    print(f"\nDone. {len(args.years) - len(failed)}/{len(args.years)} years downloaded.")
    if failed:
        print(f"Failed years: {failed}")
        print("Re-run with --force or check your connection.")


if __name__ == "__main__":
    main()
