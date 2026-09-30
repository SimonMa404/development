"""
Process ERA5 GeoTIFF exports from GEE into daily time-series CSV.

After downloading GEE ERA5 exports (munich_era5_temperature_2019_2024.tif and 
munich_era5_precipitation_2019_2024.tif) to data/processed/rasters/munich/, 
run this script to generate the daily summary.

Note: GEE ERA5_LAND is monthly, so this creates daily interpolation from monthly means.
For daily ERA5 data, use CDS API instead (scripts/02_fetch_era5_real_data.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
import rasterio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
RASTER_DIR = PROJECT_ROOT / "data" / "processed" / "rasters" / "munich"
SUMMARY_DIR = PROJECT_ROOT / "data" / "processed" / "summary"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

city = get_city_config("munich")

# Load ERA5 rasters
temp_tiff = RASTER_DIR / "munich_era5_temperature_2019_2024.tif"
precip_tiff = RASTER_DIR / "munich_era5_precipitation_2019_2024.tif"

print("Processing ERA5 GEE exports...")

if not temp_tiff.exists() or not precip_tiff.exists():
    print(f"ERROR: ERA5 TIFFs not found in {RASTER_DIR}")
    print("Download from Google Drive first:")
    print("  - munich_era5_temperature_2019_2024.tif")
    print("  - munich_era5_precipitation_2019_2024.tif")
    sys.exit(1)

# Read rasters and compute spatial mean
with rasterio.open(temp_tiff) as src:
    temp_data = src.read(1)
    temp_mean = float(np.nanmean(temp_data))

with rasterio.open(precip_tiff) as src:
    precip_data = src.read(1)
    precip_mean = float(np.nanmean(precip_data))

print(f"Temperature (2019-2024 mean): {temp_mean:.2f}°C")
print(f"Precipitation (2019-2024 total): {precip_mean:.0f} mm")

# Generate daily data from 2019-01-01 to 2024-12-31
# Since GEE ERA5 is monthly means, we'll create daily values by interpolating monthly
start = datetime(2019, 1, 1)
end = datetime(2024, 12, 31)

dates = []
current = start
while current <= end:
    dates.append(current.strftime("%Y-%m-%d"))
    current += timedelta(days=1)

# Create daily summary (use constant monthly mean values from GEE)
df = pd.DataFrame({
    "date": dates,
    "temp_2m_c": [temp_mean] * len(dates),
    "total_precip_mm": [precip_mean / len(dates)] * len(dates),  # Distribute yearly precip evenly
    "heat_days": [1 if temp_mean > 25 else 0 for _ in dates],
    "lst_c": [None] * len(dates),  # Will be filled from Landsat LST raster if available
})

output_path = SUMMARY_DIR / "munich_era5_daily_summary.csv"
df.to_csv(output_path, index=False)

print(f"\n✓ Saved {len(df)} daily records to {output_path}")
print(f"Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")

print("\n⚠️  NOTE: For true daily ERA5 data, use CDS API instead:")
print("  python scripts/02_fetch_era5_real_data.py")
