from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.config import get_city_config, get_project_root
from src.raster_utils import ensure_dir, list_tiff_files, read_raster, write_raster

PROJECT_ROOT = get_project_root()
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "gee"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "rasters"

DYNAMIC_WORLD_CLASSES = {
    "water": 0,
    "trees": 1,
    "grass": 2,
    "flooded_vegetation": 3,
    "crops": 4,
    "shrub_and_scrub": 5,
    "built": 6,
    "bare": 7,
    "snow_and_ice": 8,
    "clouds": 9,
}


def produce_dynamic_world_class_layers(city_name: str = "munich") -> list[Path]:
    out_dir = PROCESSED_DIR / city_name / "dynamic_world"
    ensure_dir(out_dir)
    paths = []

    seed_file = RAW_DIR / f"{city_name}_dynamic_world_water.tif"
    if not seed_file.exists():
        print(f"No Dynamic World source rasters found in: {RAW_DIR}")
        return paths

    for class_name, class_id in DYNAMIC_WORLD_CLASSES.items():
        source_path = RAW_DIR / f"{city_name}_dynamic_world_{class_name}.tif"
        if not source_path.exists():
            continue

        info = read_raster(source_path)
        array = info["array"].astype(np.float32)
        array[np.isnan(array)] = 0
        array = np.where(array > 0, 1.0, 0.0)

        out_path = out_dir / f"{city_name}_{class_name}_percent.tif"
        write_raster(out_path, array, info["profile"])
        paths.append(out_path)

    return paths


def create_simple_summary_files(city_name: str = "munich") -> list[Path]:
    out_dir = PROCESSED_DIR / city_name / "summary"
    ensure_dir(out_dir)
    result_paths = []

    summary_file = out_dir / f"{city_name}_summary.txt"
    summary_file.write_text(
        "Urban adaptation summary for Munich\n"
        "- LST mean heat map from Landsat 8/9\n"
        "- NDVI vegetation index from Sentinel-2 median composite\n"
        "- Dynamic World per-class layers separated by land-cover type\n"
        "- ERA5 daily climate summaries prepared for later time-series analysis\n",
        encoding="utf-8",
    )
    result_paths.append(summary_file)
    return result_paths


def main() -> None:
    city = get_city_config()
    produce_dynamic_world_class_layers(city.name)
    create_simple_summary_files(city.name)
    print(f"Raster processing complete for {city.name}.")


if __name__ == "__main__":
    main()
