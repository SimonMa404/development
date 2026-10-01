"""Export real Earth Engine derived layers (NDVI, LST, Dynamic World LULC)
for the Planegg region, clipped to the buffered municipal boundary.

This mirrors the logic used in the exploratory gee_test.ipynb notebook
(Sentinel-2 NDVI, Landsat 8/9 Collection-2 LST in Celsius) and adds a
Dynamic World land-use/land-cover composite.

Outputs are written as GeoTIFFs (EPSG:4326) into:
    storage/rasters/processed/planegg/{ndvi,lst,lulc}.tif

The region of interest is the 500m-buffered Planegg boundary produced by
scripts/extract_planegg_boundary.py (run that script first).

Because the ROI is small, this script downloads pixels directly via
ee.Image.getDownloadURL (no Drive export / async task needed).

Usage:
    python scripts/fetch_gee_layers.py [--force]

Requires local Earth Engine authentication for project 'ee-simonmarggraf'
(run `earthengine authenticate` once if needed).
"""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path

import ee
import numpy as np
import rasterio
from rasterio.io import MemoryFile
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_BUFFERED = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"
OUTPUT_DIR = REPO_ROOT / "storage" / "rasters" / "processed" / "planegg"

EE_PROJECT = "ee-simonmarggraf"
EXPORT_SCALE_M = 10  # meters/pixel, matches Sentinel-2 / Dynamic World native resolution
EXPORT_CRS = "EPSG:4326"


def load_roi_geometry() -> ee.Geometry:
    if not BOUNDARY_BUFFERED.exists():
        raise FileNotFoundError(
            f"Buffered boundary not found at {BOUNDARY_BUFFERED}. "
            "Run scripts/extract_planegg_boundary.py first."
        )
    geojson = json.loads(BOUNDARY_BUFFERED.read_text())
    feature = geojson["features"][0]
    return ee.Geometry(feature["geometry"])


def download_image_as_geotiff(image: ee.Image, region: ee.Geometry, band_names: list[str], out_path: Path) -> None:
    """Download a (possibly multi-band) ee.Image clipped to region as GeoTIFF."""
    url = image.getDownloadURL(
        {
            "region": region,
            "scale": EXPORT_SCALE_M,
            "crs": EXPORT_CRS,
            "format": "GEO_TIFF",
            "bands": band_names,
        }
    )
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    print(f"Wrote {out_path} ({len(response.content):,} bytes)")


def export_ndvi(roi: ee.Geometry, force: bool) -> None:
    out_path = OUTPUT_DIR / "ndvi.tif"
    if out_path.exists() and not force:
        print(f"Skipping NDVI (exists): {out_path}")
        return

    sentinel2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate("2025-05-01", "2025-09-30")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .median()
    )
    ndvi = sentinel2.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(roi)
    download_image_as_geotiff(ndvi, roi, ["NDVI"], out_path)


def export_lst(roi: ee.Geometry, force: bool) -> None:
    out_path = OUTPUT_DIR / "lst.tif"
    if out_path.exists() and not force:
        print(f"Skipping LST (exists): {out_path}")
        return

    def kelvin_to_celsius(img: ee.Image) -> ee.Image:
        return (
            img.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("LST_C")
        )

    lst_collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
        .filterBounds(roi)
        .filterDate("2024-09-25", "2026-09-25")
        .filter(ee.Filter.lt("CLOUD_COVER", 3))
    )

    lst_mean = kelvin_to_celsius(lst_collection.mean()).clip(roi)
    download_image_as_geotiff(lst_mean, roi, ["LST_C"], out_path)


def export_lulc(roi: ee.Geometry, force: bool) -> None:
    out_path = OUTPUT_DIR / "lulc.tif"
    if out_path.exists() and not force:
        print(f"Skipping LULC (exists): {out_path}")
        return

    dw = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate("2025-01-01", "2025-12-31")
    )

    # Dynamic World 'label' band gives the argmax class per pixel (0-8).
    # Use the mode across the year as a representative per-pixel class.
    lulc_mode = dw.select("label").mode().clip(roi).rename("LULC").toInt()
    download_image_as_geotiff(lulc_mode, roi, ["LULC"], out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download and overwrite existing files.")
    args = parser.parse_args()

    ee.Initialize(project=EE_PROJECT)

    roi = load_roi_geometry()

    export_ndvi(roi, args.force)
    export_lst(roi, args.force)
    export_lulc(roi, args.force)

    print("Done.")


if __name__ == "__main__":
    main()
