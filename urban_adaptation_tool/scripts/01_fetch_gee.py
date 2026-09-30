from __future__ import annotations

import json
from pathlib import Path

import ee

from src.config import get_city_config, get_project_root


PROJECT_ROOT = get_project_root()
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "gee"


def initialize_earth_engine(project_name: str = "ee-simonmarggraf") -> None:
    try:
        ee.Initialize(project=project_name)
    except Exception:
        print("Earth Engine not initialized; authenticating via local browser...")
        ee.Authenticate(auth_mode="localhost")
        ee.Initialize(project=project_name)


def build_munich_roi(city_name: str = "munich"):
    city = get_city_config(city_name)
    center = ee.Geometry.Point([city.center_lon, city.center_lat]).buffer(city.buffer_km * 1000)
    return center


def export_ndvi(city_name: str = "munich") -> Path:
    roi = build_munich_roi(city_name)
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate("2024-01-01", "2024-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .median()
    )

    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("NDVI")
    path = OUTPUT_DIR / f"{city_name}_ndvi_2024.tif"
    export_task = ee.batch.Export.image.toDrive(
        image=ndvi.clip(roi),
        description=f"{city_name}_ndvi_2024",
        fileNamePrefix=f"{city_name}_ndvi_2024",
        region=roi.geometry().bounds().getInfo(),
        scale=10,
        maxPixels=1e13,
    )
    export_task.start()
    print(f"Started NDVI export for {city_name}. Check Google Drive exports.")
    return path


def export_lst(city_name: str = "munich") -> Path:
    roi = build_munich_roi(city_name)
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(roi).filterDate("2023-01-01", "2024-12-31")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterBounds(roi).filterDate("2023-01-01", "2024-12-31")
    collection = ee.ImageCollection(l8.merge(l9)).filter(ee.Filter.lt("CLOUD_COVER", 30))

    def to_lst(img):
        sr_band = img.select("ST_B10")
        lst = sr_band.multiply(0.00341802).add(149.0).subtract(273.15).rename("LST_C")
        return lst.clip(roi)

    mean_lst = collection.map(to_lst).mean()
    path = OUTPUT_DIR / f"{city_name}_lst_mean_2023_2024.tif"
    task = ee.batch.Export.image.toDrive(
        image=mean_lst,
        description=f"{city_name}_lst_mean",
        fileNamePrefix=f"{city_name}_lst_mean",
        region=roi.geometry().bounds().getInfo(),
        scale=100,
        maxPixels=1e13,
    )
    task.start()
    print(f"Started LST export for {city_name}. Check Google Drive exports.")
    return path


def export_dynamic_world(city_name: str = "munich") -> list[Path]:
    roi = build_munich_roi(city_name)
    dw = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate("2024-01-01", "2024-12-31")
        .select("label")
        .mode()
    )

    classes = [
        "water",
        "trees",
        "grass",
        "flooded_vegetation",
        "crops",
        "shrub_and_scrub",
        "built",
        "bare",
        "snow_and_ice",
        "clouds",
    ]

    out_paths: list[Path] = []
    for class_name in classes:
        class_id = classes.index(class_name)
        mask = dw.eq(class_id)
        path = OUTPUT_DIR / f"{city_name}_dynamic_world_{class_name}.tif"
        task = ee.batch.Export.image.toDrive(
            image=mask.float().rename(class_name),
            description=f"{city_name}_{class_name}",
            fileNamePrefix=f"{city_name}_{class_name}",
            region=roi.geometry().bounds().getInfo(),
            scale=10,
            maxPixels=1e13,
        )
        task.start()
        out_paths.append(path)
    print(f"Started Dynamic World per-class exports for {city_name}.")
    return out_paths


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    initialize_earth_engine()
    export_ndvi()
    export_lst()
    export_dynamic_world()


if __name__ == "__main__":
    main()
