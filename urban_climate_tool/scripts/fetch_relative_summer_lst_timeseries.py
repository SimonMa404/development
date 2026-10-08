#!/usr/bin/env python3
"""Fetch yearly relative summer LST anomaly rasters for Planegg from Google Earth Engine.

Outputs:
- storage/rasters/derived/planegg/relative_summer_lst/lst_relative_summer_anomaly_<year>.tif
  (2 bands: anomaly_degC, n_obs)
- storage/rasters/derived/planegg/relative_summer_lst/yearly_summary.csv

The script computes per-scene masked LST (°C), filters scenes by valid fraction in ROI,
converts each scene to anomaly relative to Planegg scene mean, then composites summer mean.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import ee
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ROI_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary.geojson"
OUT_DIR = REPO_ROOT / "storage" / "rasters" / "derived" / "planegg" / "relative_summer_lst"
SUMMARY_CSV = OUT_DIR / "yearly_summary.csv"

EE_PROJECT = "ee-simonmarggraf"
CRS = "EPSG:4326"
SCALE = 30


@dataclass
class Config:
    start_year: int
    end_year: int
    min_valid_fraction: float
    force: bool


def load_roi() -> ee.Geometry:
    if not ROI_PATH.exists():
        raise FileNotFoundError(f"ROI not found: {ROI_PATH}")
    data = json.loads(ROI_PATH.read_text(encoding="utf-8"))
    feature = data["features"][0]
    return ee.Geometry(feature["geometry"])


def mask_landsat_l2(image: ee.Image) -> ee.Image:
    qa = image.select("QA_PIXEL")
    # Mask: dilated cloud (1), cirrus (2), cloud (3), cloud shadow (4), snow (5)
    mask = (
        qa.bitwiseAnd(1 << 1).eq(0)
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )
    return image.updateMask(mask)


def to_lst_c(image: ee.Image) -> ee.Image:
    lst = image.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15).rename("lst")
    return lst.copyProperties(image, image.propertyNames())


def annotate_scene_metrics(image: ee.Image, roi: ee.Geometry) -> ee.Image:
    valid_fraction = ee.Number(
        image.mask()
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=SCALE,
            maxPixels=1_000_000_000,
            bestEffort=True,
        )
        .get("lst")
    )

    mean_lst = ee.Number(
        image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=SCALE,
            maxPixels=1_000_000_000,
            bestEffort=True,
        ).get("lst")
    )

    return image.set({"valid_fraction": valid_fraction, "mean_lst": mean_lst})


def build_year_composite(year: int, roi: ee.Geometry, min_valid_fraction: float) -> tuple[ee.Image, list[dict]]:
    start = f"{year}-06-01"
    end = f"{year}-08-31"

    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
        .filterBounds(roi)
        .filterDate(start, end)
        .map(mask_landsat_l2)
        .map(to_lst_c)
        .map(lambda img: annotate_scene_metrics(img, roi))
    )

    filtered = collection.filter(ee.Filter.gte("valid_fraction", min_valid_fraction))

    scene_info = filtered.aggregate_array("system:index").getInfo() or []
    scene_dates = filtered.aggregate_array("system:time_start").getInfo() or []
    mean_lsts = filtered.aggregate_array("mean_lst").getInfo() or []
    valid_fracs = filtered.aggregate_array("valid_fraction").getInfo() or []

    scenes = []
    for idx, sid in enumerate(scene_info):
        ts = scene_dates[idx] if idx < len(scene_dates) else None
        date = None
        if ts is not None:
            date = ee.Date(ts).format("YYYY-MM-dd").getInfo()
        scenes.append(
            {
                "scene_id": sid,
                "date": date,
                "mean_lst_degC": mean_lsts[idx] if idx < len(mean_lsts) else None,
                "valid_fraction": valid_fracs[idx] if idx < len(valid_fracs) else None,
            }
        )

    if not scenes:
        raise RuntimeError(f"No valid scenes for {year} with min_valid_fraction={min_valid_fraction}")

    anomaly_collection = filtered.map(
        lambda img: img.subtract(ee.Number(img.get("mean_lst")).toFloat()).rename("anomaly_degC").toFloat()
    )
    anomaly_mean = anomaly_collection.mean().rename("anomaly_degC").toFloat()
    composite = anomaly_mean.clip(roi).set({"year": year, "n_scenes": len(scenes)})
    return composite, scenes


def download_image(image: ee.Image, roi: ee.Geometry, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = image.getDownloadURL(
        {
            "region": roi,
            "scale": SCALE,
            "crs": CRS,
            "format": "GEO_TIFF",
            "bands": ["anomaly_degC"],
        }
    )
    response = requests.get(url, timeout=300)
    if not response.ok:
        raise RuntimeError(f"GEE download failed ({response.status_code}): {response.text[:2000]}")
    out_path.write_bytes(response.content)


def run(cfg: Config) -> None:
    ee.Initialize(project=EE_PROJECT)
    roi = load_roi()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []

    for year in range(cfg.start_year, cfg.end_year + 1):
        out_path = OUT_DIR / f"lst_relative_summer_anomaly_{year}.tif"
        if out_path.exists() and not cfg.force:
            print(f"Skipping existing raster: {out_path}")
        else:
            composite, scenes = build_year_composite(year, roi, cfg.min_valid_fraction)
            download_image(composite, roi, out_path)
            print(f"Wrote {out_path}")

            mean_scene_lst = sum(float(s["mean_lst_degC"]) for s in scenes if s["mean_lst_degC"] is not None) / len(scenes)
            summary_rows.append(
                {
                    "year": year,
                    "layer_id": f"lst-relative-summer-{year}",
                    "mean_anomaly_degC": 0.0,
                    "mean_lst_degC": round(mean_scene_lst, 3),
                    "n_scenes": len(scenes),
                }
            )

    # If rasters were skipped, still attempt to keep existing summary rows.
    if SUMMARY_CSV.exists():
        existing = {}
        with SUMMARY_CSV.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    y = int(row.get("year", ""))
                except ValueError:
                    continue
                existing[y] = row
    else:
        existing = {}

    for row in summary_rows:
        existing[int(row["year"])] = {
            "year": str(row["year"]),
            "layer_id": row["layer_id"],
            "mean_anomaly_degC": str(row["mean_anomaly_degC"]),
            "mean_lst_degC": str(row["mean_lst_degC"]),
            "n_scenes": str(row["n_scenes"]),
        }

    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["year", "layer_id", "mean_anomaly_degC", "mean_lst_degC", "n_scenes"],
        )
        writer.writeheader()
        for year in sorted(existing):
            writer.writerow(existing[year])

    print(f"Updated summary: {SUMMARY_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch relative summer LST yearly anomaly rasters from GEE.")
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--min-valid-fraction", type=float, default=0.8)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run(
        Config(
            start_year=args.start_year,
            end_year=args.end_year,
            min_valid_fraction=args.min_valid_fraction,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
