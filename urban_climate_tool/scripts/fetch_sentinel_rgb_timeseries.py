#!/usr/bin/env python3
"""Fetch yearly Sentinel-2 RGB composites for Planegg (same season as LULC script).

Uses the same date windows as `fetch_lulc_timeseries.py` (Apr 1 to Oct 31)
so the yearly RGB visual context corresponds to the Dynamic World period.

Outputs:
- storage/rasters/derived/planegg/rgb_yearly/rgb_<year>.tif
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import ee
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ROI_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary.geojson"
OUT_DIR = REPO_ROOT / "storage" / "rasters" / "derived" / "planegg" / "rgb_yearly"

EE_PROJECT = "ee-simonmarggraf"
CRS = "EPSG:4326"
SCALE = 10


def load_roi() -> ee.Geometry:
    data = json.loads(ROI_PATH.read_text(encoding="utf-8"))
    return ee.Geometry(data["features"][0]["geometry"])


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    qa = image.select("QA60")
    cloud = qa.bitwiseAnd(1 << 10).eq(0)
    cirrus = qa.bitwiseAnd(1 << 11).eq(0)
    scl = image.select("SCL")
    # Exclude cloud shadow (3), clouds (8/9), cirrus (10), snow/ice (11)
    scl_mask = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return image.updateMask(cloud.And(cirrus).And(scl_mask))


def download_rgb_tif(image: ee.Image, roi: ee.Geometry, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = image.getDownloadURL(
        {
            "region": roi,
            "scale": SCALE,
            "crs": CRS,
            "format": "GEO_TIFF",
            "bands": ["R", "G", "B"],
        }
    )
    resp = requests.get(url, timeout=300)
    if not resp.ok:
        raise RuntimeError(f"GEE download failed ({resp.status_code}): {resp.text[:1500]}")
    out_path.write_bytes(resp.content)


def yearly_rgb(year: int, roi: ee.Geometry) -> ee.Image | None:
    start = f"{year}-04-01"
    end = f"{year}-10-31"

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
        .map(mask_s2_clouds)
    )

    count = int(collection.size().getInfo() or 0)
    if count == 0:
        return None

    rgb = (
        collection.select(["B4", "B3", "B2"])
        .median()
        .multiply(0.0001)
        .clamp(0, 1)
        .rename(["R", "G", "B"])
        .clip(roi)
        .toFloat()
    )
    return rgb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ee.Initialize(project=EE_PROJECT)
    roi = load_roi()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for year in range(args.start_year, args.end_year + 1):
        out_path = OUT_DIR / f"rgb_{year}.tif"
        if out_path.exists() and not args.force:
            print(f"Skipping existing raster: {out_path}")
            continue

        rgb_img = yearly_rgb(year, roi)
        if rgb_img is None:
            print(f"No Sentinel-2 scenes for {year} in selected season; skipping export.")
            continue

        download_rgb_tif(rgb_img, roi, out_path)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
