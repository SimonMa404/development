from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

from src.config import get_city_config, get_project_root

PROJECT_ROOT = get_project_root()
DATA_ROOT = PROJECT_ROOT / "data"
RASTER_DIR = DATA_ROOT / "processed" / "rasters" / "munich"
SUMMARY_DIR = DATA_ROOT / "processed" / "summary"


def make_raster(path: Path, values: np.ndarray, nodata: float = -9999.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(11.38, 48.30, 0.004, 0.004)
    profile = {
        "driver": "GTiff",
        "height": values.shape[0],
        "width": values.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": nodata,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(values.astype("float32"), 1)


def generate_munich_demo_rasters() -> None:
    city = get_city_config("munich")
    rows, cols = 120, 120
    y, x = np.mgrid[0:rows, 0:cols]
    y_norm = y / rows
    x_norm = x / cols

    # create city-centered heat/vegetation gradients
    center_x = 0.52
    center_y = 0.48
    urban_center = np.exp(-((x_norm - center_x) ** 2 / 0.085 + (y_norm - center_y) ** 2 / 0.09))
    north_gradient = 1.0 - y_norm
    greenbelt = np.exp(-((x_norm - 0.25) ** 2 / 0.12 + (y_norm - 0.75) ** 2 / 0.10))
    water_band = np.exp(-((x_norm - 0.63) ** 2 / 0.008 + (y_norm - 0.30) ** 2 / 0.04))

    ndvi = 0.12 + 0.55 * greenbelt + 0.20 * north_gradient - 0.18 * urban_center
    ndvi = np.clip(ndvi, 0.0, 0.9)

    lst = 18.0 + 14.0 * urban_center + 8.0 * (1.0 - north_gradient) + 3.0 * water_band
    lst = np.clip(lst, 10.0, 37.0)

    built = np.clip(0.25 + 0.75 * urban_center, 0.0, 1.0)
    trees = np.clip(0.15 + 0.75 * greenbelt + 0.15 * north_gradient, 0.0, 1.0)
    water = np.clip(water_band * 1.8, 0.0, 1.0)
    grass = np.clip(0.4 + 0.35 * north_gradient - 0.25 * urban_center, 0.0, 1.0)
    bare = np.clip(0.10 + 0.32 * (1.0 - greenbelt) - 0.15 * (1.0 - urban_center), 0.0, 1.0)

    make_raster(RASTER_DIR / "munich_ndvi_2024.tif", ndvi)
    make_raster(RASTER_DIR / "munich_lst_mean_2023_2024.tif", lst)
    make_raster(RASTER_DIR / "munich_dynamic_world_water.tif", water)
    make_raster(RASTER_DIR / "munich_dynamic_world_trees.tif", trees)
    make_raster(RASTER_DIR / "munich_dynamic_world_grass.tif", grass)
    make_raster(RASTER_DIR / "munich_dynamic_world_built.tif", built)
    make_raster(RASTER_DIR / "munich_dynamic_world_bare.tif", bare)

    summary_df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "temp_2m_c": np.linspace(0.5, 27.2, 30),
            "total_precip_mm": np.linspace(0.3, 2.9, 30) * 10,
            "heat_days": np.where(np.linspace(0.5, 27.2, 30) > 25, 1, 0),
            "lst_c": np.linspace(12.0, 31.0, 30),
        }
    )
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(SUMMARY_DIR / "munich_era5_daily_summary.csv", index=False)

    print(f"Generated demo Munich raster and summary data in {RASTER_DIR} and {SUMMARY_DIR}.")


def main() -> None:
    generate_munich_demo_rasters()


if __name__ == "__main__":
    main()
