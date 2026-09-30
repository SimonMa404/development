from __future__ import annotations

from pathlib import Path

import cdsapi

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "era5"


def fetch_era5_daily(city_name: str = "munich") -> Path:
    city = get_city_config(city_name)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    years = list(range(int(city.start_date[:4]), int(city.end_date[:4]) + 1))
    out_path = OUTPUT_DIR / f"{city_name}_era5_daily.nc"

    client = cdsapi.Client()
    client.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "variable": ["2m_temperature", "total_precipitation", "total_column_water_vapour"],
            "year": [str(year) for year in years],
            "month": [f"{i:02d}" for i in range(1, 13)],
            "day": [f"{i:02d}" for i in range(1, 32)],
            "time": ["00:00", "06:00", "12:00", "18:00"],
            "area": [city.center_lat + 0.3, city.center_lon - 0.3, city.center_lat - 0.3, city.center_lon + 0.3],
            "format": "netcdf",
        },
        str(out_path),
    )

    return out_path
