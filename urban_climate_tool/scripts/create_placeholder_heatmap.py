#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "storage"
TARGET_PATH = DATA_ROOT / "rasters" / "processed" / "placeholder_heat.tif"


def ensure_storage_dirs() -> None:
    for directory in [
        DATA_ROOT,
        DATA_ROOT / "rasters",
        DATA_ROOT / "rasters" / "source",
        DATA_ROOT / "rasters" / "processed",
        DATA_ROOT / "rasters" / "derived",
        DATA_ROOT / "vectors",
        DATA_ROOT / "vectors" / "source",
        DATA_ROOT / "vectors" / "processed",
        DATA_ROOT / "uploads",
        DATA_ROOT / "cache",
        DATA_ROOT / "temporary",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def generate_placeholder_heatmap(force: bool = False) -> Path:
    ensure_storage_dirs()

    if TARGET_PATH.exists() and not force:
        print(f"Placeholder raster already exists: {TARGET_PATH}")
        return TARGET_PATH

    width = 120
    height = 100
    pixel_size = 100.0

    west = 455000.0
    north = 5344000.0
    transform = from_origin(west, north, pixel_size, pixel_size)

    y_idx, x_idx = np.mgrid[0:height, 0:width]
    center_x = west + (x_idx + 0.5) * pixel_size
    center_y = north - (y_idx + 0.5) * pixel_size

    x_center = 482000.0
    y_center = 5337000.0
    sigma_x = 6000.0
    sigma_y = 5000.0

    dx = (center_x - x_center) / sigma_x
    dy = (center_y - y_center) / sigma_y
    heat = 24.0 + 13.0 * np.exp(-(dx**2 + dy**2))
    heat += 3.0 * np.sin((x_idx / width) * np.pi * 2.0) * np.cos((y_idx / height) * np.pi * 2.0)
    heat = np.clip(heat, 20.0, 45.0)

    nodata = -9999.0
    heat = np.where(np.isfinite(heat), heat, nodata).astype(np.float32)

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": "EPSG:25832",
        "transform": transform,
        "nodata": nodata,
        "compress": "LZW",
        "tiled": True,
        "blockxsize": 64,
        "blockysize": 64,
        "interleave": "band",
        "BIGTIFF": "IF_SAFER",
    }

    with rasterio.open(TARGET_PATH, "w", **profile) as dst:
        dst.write(heat, 1)

    with rasterio.open(TARGET_PATH) as src:
        print(f"Created placeholder raster at: {TARGET_PATH}")
        print(f"Shape: {src.width}x{src.height}")
        print(f"Bounds: {src.bounds}")
        print(f"CRS: {src.crs}")
        print(f"Nodata: {src.nodata}")
        print(f"Resolution: {src.res}")

    return TARGET_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a placeholder heat raster for the geospatial app.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing placeholder raster.")
    args = parser.parse_args()
    generate_placeholder_heatmap(force=args.force)
