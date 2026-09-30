"""
Fetch real ERA5 daily climate data via Copernicus Climate Data Store.

Run after setting up CDS API:
1. Register at: https://cds.climate.copernicus.eu/
2. Copy credentials to ~/.cdsapirc
"""
from __future__ import annotations

import sys
from pathlib import Path
import datetime
import cdsapi
import xarray as xr
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
SUMMARY_DIR = PROJECT_ROOT / "data" / "processed" / "summary"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

city = get_city_config("munich")
print(f"Fetching real ERA5 data for {city.name}...")
print(f"Date range: {city.start_date} to {city.end_date}")

# Initialize CDS client
cds = cdsapi.Client()

# ERA5 bounding box: [North, West, South, East] for CDS API
north = city.bbox[3]
south = city.bbox[1]
west = city.bbox[0]
east = city.bbox[2]
bbox = f"{north}/{west}/{south}/{east}"

print(f"Spatial extent: {bbox}")

# Parse dates
start_date = datetime.datetime.strptime(city.start_date, "%Y-%m-%d")
end_date = datetime.datetime.strptime(city.end_date, "%Y-%m-%d")

# Fetch monthly to avoid timeout (ERA5 daily, 2019-2024, is ~2000 days)
all_data = []

current = start_date
while current <= end_date:
    year = current.year
    month = f"{current.month:02d}"
    
    print(f"\nFetching ERA5 for {year}-{month}...")
    
    try:
        # Request daily data for the month
        result = cds.retrieve(
            "reanalysis-era5-land",
            {
                "variable": ["2m_temperature", "total_precipitation"],
                "year": year,
                "month": month,
                "day": [f"{d:02d}" for d in range(1, 32)],  # All days (invalid dates ignored by API)
                "time": "00:00",
                "area": bbox,
                "format": "netcdf",
            },
            target=f"/tmp/era5_{year}_{month}.nc"
        )
        
        # Load NetCDF
        ds = xr.open_dataset(f"/tmp/era5_{year}_{month}.nc")
        
        # Extract time series
        temp = ds["t2m"]  # 2m temperature in Kelvin
        precip = ds["tp"]  # Total precipitation in m
        
        times = ds["time"].values
        
        for i, time in enumerate(times):
            ts = pd.Timestamp(time)
            # Spatial mean over bounding box
            temp_c = float(temp.isel(time=i).mean().values) - 273.15
            precip_mm = float(precip.isel(time=i).mean().values) * 1000  # m to mm
            heat_day = 1 if temp_c > 25 else 0
            
            all_data.append({
                "date": ts.strftime("%Y-%m-%d"),
                "temp_2m_c": round(temp_c, 2),
                "total_precip_mm": round(precip_mm, 2),
                "heat_days": heat_day,
                "lst_c": None  # Will be filled from Landsat LST raster if available
            })
        
        ds.close()
    except Exception as e:
        print(f"Warning: Failed to fetch {year}-{month}: {e}")
    
    # Advance to next month
    if current.month == 12:
        current = current.replace(year=current.year + 1, month=1)
    else:
        current = current.replace(month=current.month + 1)

# Create DataFrame
df = pd.DataFrame(all_data)

# Sort by date
df = df.sort_values("date").reset_index(drop=True)

# Save to CSV
output_path = SUMMARY_DIR / "munich_era5_daily_summary.csv"
df.to_csv(output_path, index=False)

print(f"\n✓ Saved {len(df)} days of ERA5 data to {output_path}")
print(f"Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
print(f"Mean temperature: {df['temp_2m_c'].mean():.2f}°C")
print(f"Total precipitation: {df['total_precip_mm'].sum():.0f} mm")
print(f"Heat days (T>25°C): {df['heat_days'].sum()}")
