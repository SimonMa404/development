from __future__ import annotations

from pathlib import Path

import ee

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "gee"


def initialize_earth_engine(project_name: str = "ee-simonmarggraf") -> None:
    try:
        ee.Initialize(project=project_name)
    except Exception:
        ee.Authenticate(auth_mode="localhost")
        ee.Initialize(project=project_name)


def city_roi(city_name: str = "munich"):
    city = get_city_config(city_name)
    return ee.Geometry.Point([city.center_lon, city.center_lat]).buffer(city.buffer_km * 1000)


def get_ndvi_annual(city_name: str = "munich", year: int = 2024):
    roi = city_roi(city_name)
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )
    annual_median = collection.median()
    return annual_median.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(roi)


def get_lst_mean(city_name: str = "munich", year_start: int = 2023, year_end: int = 2024):
    roi = city_roi(city_name)
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(roi).filterDate(f"{year_start}-01-01", f"{year_end}-12-31")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterBounds(roi).filterDate(f"{year_start}-01-01", f"{year_end}-12-31")
    collection = ee.ImageCollection(l8.merge(l9)).filter(ee.Filter.lt("CLOUD_COVER", 30))

    def to_lst(img):
        temp = img.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15)
        return temp.rename("LST_C").clip(roi)

    return collection.map(to_lst).mean()


def get_dynamic_world_mode(city_name: str = "munich", year_start: int = 2024, year_end: int = 2024):
    roi = city_roi(city_name)
    dw = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate(f"{year_start}-01-01", f"{year_end}-12-31")
        .select("label")
        .mode()
    )
    return dw.clip(roi)


def export_image(image, description: str, region, scale: int = 10, out_path: str | Path | None = None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        out_path = OUTPUT_DIR / f"{description}.tif"
    else:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        fileNamePrefix=description,
        region=region,
        scale=scale,
        maxPixels=1e13,
    )
    task.start()
    return out_path
