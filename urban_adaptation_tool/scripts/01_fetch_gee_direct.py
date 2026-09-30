"""
Fetch real GEE data and download directly to local storage.
No Google Drive waiting—everything downloads immediately to data/processed/rasters/munich/

Uses getDownloadUrl() for direct streaming downloads with concurrent threads.
"""
from __future__ import annotations

import sys
from pathlib import Path
import ee
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_city_config, get_project_root

# Initialize Earth Engine
try:
    ee.Initialize(project='ee-simonmarggraf')
except Exception:
    print("Authenticating with Earth Engine...")
    ee.Authenticate(auth_mode='localhost')
    ee.Initialize(project='ee-simonmarggraf')

PROJECT_ROOT = get_project_root()
RASTER_DIR = PROJECT_ROOT / "data" / "processed" / "rasters" / "munich"
RASTER_DIR.mkdir(parents=True, exist_ok=True)

city = get_city_config("munich")
roi_bbox = city.bbox  # (minx, miny, maxx, maxy)
roi = ee.Geometry.BBox(roi_bbox[0], roi_bbox[1], roi_bbox[2], roi_bbox[3])

print(f"Fetching real GEE data for {city.name}...")
print(f"ROI: {roi_bbox}")
print(f"📥 Download destination: {RASTER_DIR}\n")

# === 1. Sentinel-2 NDVI (2024) ===
print("Computing Sentinel-2 NDVI (2024)...")
s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
      .filterBounds(roi)
      .filterDate("2024-01-01", "2024-12-31")
      .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
      .median())

ndvi = s2.normalizedDifference(['B8', 'B4']).rename("NDVI").clip(roi)

# === 2. Landsat 8/9 LST (2023-2024) ===
print("Computing Landsat 8/9 LST (2023-2024)...")
l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(roi).filterDate("2023-01-01", "2024-12-31")
l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterBounds(roi).filterDate("2023-01-01", "2024-12-31")
lst_collection = l8.merge(l9).filter(ee.Filter.lt("CLOUD_COVER", 3))

def kelvin_to_celsius(img):
    return img.select("ST_B10").multiply(0.0003125).add(149.0).subtract(273.15).rename("LST_C")

lst = kelvin_to_celsius(lst_collection.mean()).clip(roi)

# === 3. Dynamic World v1 LULC (2023) ===
print("Computing Dynamic World classification (2023)...")
dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterBounds(roi).filterDate("2023-01-01", "2023-12-31").mean()

# Dynamic World v1 has class probability bands directly (water, trees, grass, etc.)
# No need to select 'classification' - use the class bands directly
dw_classes = {
    "water": "water",
    "trees": "trees",
    "grass": "grass",
    "flooded_vegetation": "flooded_vegetation",
    "crops": "crops",
    "shrub_and_scrub": "shrub_and_scrub",
    "built": "built",
    "bare": "bare",
    "snow_and_ice": "snow_and_ice",
}

# === 4. ERA5 Climate Data (2019-2024) ===
print("Computing ERA5 climate data (2019-2024)...")
era5 = (ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
        .select(['temperature_2m', 'total_precipitation'])
        .filterBounds(roi)
        .filterDate("2019-01-01", "2024-12-31"))

def process_era5(img):
    temp = img.select("temperature_2m").subtract(273.15).rename("temp_2m_c")
    precip = img.select("total_precipitation").multiply(1000).rename("precip_mm")
    return temp.addBands(precip)

era5_processed = era5.map(process_era5)
era5_temp = era5_processed.select("temp_2m_c").mean()
era5_precip = era5_processed.select("precip_mm").sum()

# === Download function ===
def download_image(image, filename, description):
    """Download a GEE image to local GeoTIFF using getDownloadUrl()."""
    try:
        print(f"  ⏳ Getting download URL: {description}...")
        url = image.getDownloadURL({
            'scale': 30,
            'crs': 'EPSG:4326',
            'fileFormat': 'GeoTIFF',
            'region': roi.bounds()
        })
        
        filepath = RASTER_DIR / filename
        print(f"  📥 Downloading: {filename}...")
        
        urllib.request.urlretrieve(url, filepath)
        print(f"  ✓ Downloaded: {filename} ({filepath.stat().st_size / 1024 / 1024:.2f} MB)")
        return True
    except Exception as e:
        print(f"  ✗ Failed to download {filename}: {e}")
        return False

# === Concurrent downloads ===
print("\n--- Downloading GEE data (multithreaded) ---\n")

download_tasks = [
    (ndvi, "munich_ndvi_2024.tif", "Sentinel-2 NDVI 2024"),
    (lst, "munich_lst_2023_2024.tif", "Landsat LST 2023-2024"),
    (era5_temp, "munich_era5_temp_mean_2019_2024.tif", "ERA5 Temperature Mean"),
    (era5_precip, "munich_era5_precip_total_2019_2024.tif", "ERA5 Precipitation Total"),
]

# Dynamic World classes
dw_classes = {
    0: "water",
    1: "trees",
    2: "grass",
    3: "flooded_vegetation",
    4: "crops",
    5: "shrub_and_scrub",
    6: "built",
    7: "bare",
    8: "snow_and_ice",
}

# Dynamic World classes
dw_classes = {
    "water": "water",
    "trees": "trees",
    "grass": "grass",
    "flooded_vegetation": "flooded_vegetation",
    "crops": "crops",
    "shrub_and_scrub": "shrub_and_scrub",
    "built": "built",
    "bare": "bare",
    "snow_and_ice": "snow_and_ice",
}

for class_name, band_name in dw_classes.items():
    class_img = dw.select(band_name).clip(roi)
    download_tasks.append((class_img, f"munich_dw_{class_name}_2023.tif", f"Dynamic World {class_name}"))

# Download with ThreadPoolExecutor (max 4 concurrent to avoid rate limiting)
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(download_image, img, filename, desc)
        for img, filename, desc in download_tasks
    ]
    
    results = []
    for future in as_completed(futures):
        results.append(future.result())

success_count = sum(results)
total_count = len(results)

print(f"\n✓ Downloads complete: {success_count}/{total_count} files")
print(f"📁 Location: {RASTER_DIR}")
print(f"\n✅ Next: python scripts/06_prepare_overlays.py")
