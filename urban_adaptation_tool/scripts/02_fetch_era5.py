from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import cdsapi
import pandas as pd

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "era5"


def get_munich_era5_daily(city_name: str = "munich") -> Path:
    city = get_city_config(city_name)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = cdsapi.Client()
    year_start = datetime.strptime(city.start_date, "%Y-%m-%d").year
    year_end = datetime.strptime(city.end_date, "%Y-%m-%d").year

    years = list(range(year_start, year_end + 1))
    out_path = OUTPUT_DIR / f"{city_name}_era5_daily.nc"
    client.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "variable": ["2m_temperature", "total_precipitation", "total_column_water_vapour"],
            "year": [str(year) for year in years],
            "month": [
                "01", "02", "03", "04", "05", "06",
                "07", "08", "09", "10", "11", "12",
            ],
            "day": [
                "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
                "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
                "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
            ],
            "time": ["00:00", "06:00", "12:00", "18:00"],
            "area": [city.center_lat + 0.3, city.center_lon - 0.3, city.center_lat - 0.3, city.center_lon + 0.3],
            "format": "netcdf",
        },
        str(out_path),
    )

    print(f"Saved ERA5 daily data to: {out_path}")
    return out_path


def create_era5_summary(city_name: str = "munich") -> Path:
    path = OUTPUT_DIR / f"{city_name}_era5_daily.nc"
    if not path.exists():
        raise FileNotFoundError(f"ERA5 data not found: {path}")

    summary_dir = PROJECT_ROOT / "data" / "processed" / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    summary_path = summary_dir / f"{city_name}_era5_daily_summary.csv"
    df = pd.DataFrame({"source": ["ERA5 daily summary"], "path": [str(path)]})
    df.to_csv(summary_path, index=False)
    print(f"Saved ERA5 summary metadata to: {summary_path}")
    return summary_path


def main() -> None:
    get_munich_era5_daily()
    create_era5_summary()


if __name__ == "__main__":
    main()
