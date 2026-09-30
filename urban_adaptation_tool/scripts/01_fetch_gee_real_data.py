"""
Fetch real data from Google Earth Engine:
- Sentinel-2 NDVI (2024 annual mean)
- Landsat 8/9 LST (2023-2024 mean)
- Dynamic World v1 LULC (2023 mode)

Run once authenticated via: earthengine authenticate
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ee
from src.config import get_city_config, get_project_root

# Initialize Earth Engine (same pattern as gee_test.ipynb)
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

# === 1. Sentinel-2 NDVI (2024) ===
def compute_s2_ndvi():
    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
          .filterBounds(roi)
          .filterDate("2024-01-01", "2024-12-31")
          .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
          .median())  # Use median to reduce noise
    
    ndvi = s2.normalizedDifference(['B8', 'B4']).rename("NDVI")
    return ndvi.clip(roi)

print("Computing Sentinel-2 NDVI...")
ndvi = compute_s2_ndvi()

# === 2. Landsat 8/9 LST (2023-2024) ===
def compute_lst():
    # Use Collection 2 Level 2 with calibrated thermal band
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(roi).filterDate("2023-01-01", "2024-12-31")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterBounds(roi).filterDate("2023-01-01", "2024-12-31")
    
    combined = l8.merge(l9).filter(ee.Filter.lt("CLOUD_COVER", 3))
    
    # ST_B10 is thermal band; convert from radiance to Celsius using proper scaling
    def get_temp(img):
        # Landsat C2 ST_B10: multiply by 0.0003125, add 149.0, subtract 273.15 for Celsius
        temp = img.select("ST_B10").multiply(0.0003125).add(149.0).subtract(273.15).rename("LST_C")
        return temp
    
    lst = combined.map(get_temp).select("LST_C").mean()
    return lst.clip(roi)

print("Computing Landsat LST...")
lst = compute_lst()

# === 3. Dynamic World v1 LULC (2023 mode) ===
def compute_dynamic_world():
    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterBounds(roi).filterDate("2023-01-01", "2023-12-31")
    # Select classification band and compute mode
    classification = dw.select("classification")
    mode = classification.mode()
    return mode

print("Computing Dynamic World classification...")
dw_mode = compute_dynamic_world()

# === Export tasks ===
def export_to_geotiff(image, description, filename):
    """Start a GEE export task to Google Drive."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder="urban_adaptation_tool",
        fileNamePrefix=filename,
        scale=30,
        region=roi.bounds(),
        fileFormat="GeoTIFF",
        crs="EPSG:4326"
    )
    task.start()
    print(f"  ✓ Started: {description}")
    return task

# Export NDVI
export_to_geotiff(ndvi, "munich_ndvi_2024", "munich_ndvi_2024")

# Export LST
export_to_geotiff(lst, "munich_lst_2023_2024", "munich_lst_2023_2024")

# Export Dynamic World classes (one per class)
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
    9: "clouds"
}

for class_id, class_name in dw_classes.items():
    class_mask = dw_mode.eq(class_id).float().rename(f"DW_{class_name}")
    export_to_geotiff(class_mask, f"munich_dynamic_world_{class_name}", f"munich_dynamic_world_{class_name}")

# === 4. ERA5 Hourly Climate Data (2019-2024) ===
print("\nComputing ERA5 climate data (2019-2024)...")
era5 = (ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY")
        .select(['temperature_2m', 'total_precipitation'])
        .filterBounds(roi)
        .filterDate("2019-01-01", "2024-12-31"))

def process_era5(img):
    temp = img.select("temperature_2m").subtract(273.15).rename("temp_2m_c")
    precip = img.select("total_precipitation").multiply(1000).rename("precip_mm")
    return temp.addBands(precip)

era5_processed = era5.map(process_era5)
era5_temp_mean = era5_processed.select("temp_2m_c").mean()
era5_precip_sum = era5_processed.select("precip_mm").sum()

# === Export all tasks ===
print("\n--- Starting GEE export tasks ---")
export_to_geotiff(ndvi, "munich_ndvi_2024", "munich_ndvi_2024")
export_to_geotiff(lst, "munich_lst_2023_2024", "munich_lst_2023_2024")
export_to_geotiff(era5_temp_mean, "munich_era5_temp_mean_2019_2024", "munich_era5_temp_mean_2019_2024")
export_to_geotiff(era5_precip_sum, "munich_era5_precip_total_2019_2024", "munich_era5_precip_total_2019_2024")

# Dynamic World: Export each class (without "clouds")
dw_classes_updated = {
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

for class_id, class_name in dw_classes_updated.items():
    class_mask = dw_mode.eq(class_id).float().rename(f"DW_{class_name}")
    export_to_geotiff(class_mask, f"munich_dw_{class_name}_2023", f"munich_dw_{class_name}_2023")

print("\n✓ All exports started!")
print(f"📍 Check your Google Drive folder: urban_adaptation_tool")
print(f"⏱️  Exports typically complete in 5-30 minutes")
print(f"\n📥 Download all TIFFs to: {RASTER_DIR}")
print(f"\n✅ Then run: python scripts/06_prepare_overlays.py")
