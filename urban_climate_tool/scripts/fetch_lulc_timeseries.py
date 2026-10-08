#!/usr/bin/env python3
"""Fetch yearly Dynamic World LULC composites for Planegg (2016-2025).

Outputs:
- storage/rasters/derived/planegg/lulc_yearly/lulc_<year>.tif
- storage/rasters/derived/planegg/lulc_yearly/yearly_class_area.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import ee
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ROI_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary.geojson"
OUT_DIR = REPO_ROOT / "storage" / "rasters" / "derived" / "planegg" / "lulc_yearly"
AREA_CSV = OUT_DIR / "yearly_class_area.csv"

EE_PROJECT = "ee-simonmarggraf"
CRS = "EPSG:4326"
SCALE = 10
CLASS_LABELS = [
    "Water",
    "Trees",
    "Grass",
    "Flooded vegetation",
    "Crops",
    "Shrub & scrub",
    "Built area",
    "Bare ground",
    "Snow & ice",
]


def load_roi() -> ee.Geometry:
    data = json.loads(ROI_PATH.read_text(encoding="utf-8"))
    return ee.Geometry(data["features"][0]["geometry"])


def download_label_tif(image: ee.Image, roi: ee.Geometry, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = image.getDownloadURL(
        {
            "region": roi,
            "scale": SCALE,
            "crs": CRS,
            "format": "GEO_TIFF",
            "bands": ["LULC"],
        }
    )
    resp = requests.get(url, timeout=300)
    if not resp.ok:
        raise RuntimeError(f"GEE download failed ({resp.status_code}): {resp.text[:1500]}")
    out_path.write_bytes(resp.content)


def area_stats_ha(label_img: ee.Image, roi: ee.Geometry) -> list[float]:
    out: list[float] = []
    for cls in range(9):
        area_m2 = ee.Number(
            ee.Image.pixelArea()
            .updateMask(label_img.eq(cls))
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=roi,
                scale=SCALE,
                maxPixels=1_000_000_000,
                bestEffort=True,
            )
            .get("area")
        )
        out.append(float(area_m2.divide(10_000).getInfo() or 0.0))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    ee.Initialize(project=EE_PROJECT)
    roi = load_roi()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str | int | float]] = []

    for year in range(args.start_year, args.end_year + 1):
        start = f"{year}-04-01"
        end = f"{year}-10-31"
        dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterBounds(roi).filterDate(start, end)
        label = dw.select("label").mode().rename("LULC").toInt().clip(roi)

        out_path = OUT_DIR / f"lulc_{year}.tif"
        if out_path.exists() and not args.force:
            print(f"Skipping existing raster: {out_path}")
        else:
            download_label_tif(label, roi, out_path)
            print(f"Wrote {out_path}")

        areas = area_stats_ha(label, roi)
        for cls, area_ha in enumerate(areas):
            rows.append(
                {
                    "year": year,
                    "layer_id": f"lulc-planegg-{year}",
                    "class_index": cls,
                    "class_label": CLASS_LABELS[cls],
                    "area_ha": round(area_ha, 4),
                }
            )

    with AREA_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["year", "layer_id", "class_index", "class_label", "area_ha"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {AREA_CSV}")


if __name__ == "__main__":
    main()
