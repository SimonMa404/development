#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "catalog" / "layers.yaml"
DEFAULT_SUMMARY_CSV = ROOT / "storage" / "rasters" / "derived" / "planegg" / "relative_summer_lst" / "yearly_summary.csv"
DEFAULT_RASTERS_DIR = ROOT / "storage" / "rasters" / "derived" / "planegg" / "relative_summer_lst"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register yearly relative summer LST raster layers in catalog/layers.yaml.",
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG_PATH, help="Path to catalog YAML.")
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV, help="Optional yearly summary CSV with a 'year' column.")
    parser.add_argument("--rasters-dir", type=Path, default=DEFAULT_RASTERS_DIR, help="Directory containing yearly anomaly GeoTIFFs.")
    parser.add_argument(
        "--filename-regex",
        default=r"lst_relative_summer_anomaly_(?P<year>(19|20)\d{2})\.tif$",
        help="Regex to extract years from raster filenames.",
    )
    parser.add_argument("--id-prefix", default="lst-relative-summer", help="Layer id prefix.")
    parser.add_argument(
        "--relative-path-template",
        default="rasters/derived/planegg/relative_summer_lst/lst_relative_summer_anomaly_{year}.tif",
        help="Catalog relative_path template with {year} placeholder.",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to catalog. Without this flag the script only prints a preview.")
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Replace existing entries with matching ids instead of skipping them.",
    )
    return parser.parse_args()


def load_catalog(catalog_path: Path) -> dict[str, Any]:
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")
    with catalog_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict) or "layers" not in payload or not isinstance(payload["layers"], list):
        raise ValueError("Catalog YAML must contain a top-level 'layers' list.")
    return payload


def collect_years_from_csv(summary_csv: Path) -> set[int]:
    years: set[int] = set()
    if not summary_csv.exists():
        return years
    with summary_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw = (row.get("year") or "").strip()
            if not raw:
                continue
            try:
                years.add(int(raw))
            except ValueError:
                continue
    return years


def collect_years_from_rasters(rasters_dir: Path, filename_regex: str) -> set[int]:
    years: set[int] = set()
    if not rasters_dir.exists():
        return years
    pattern = re.compile(filename_regex)
    for path in rasters_dir.glob("*.tif"):
        match = pattern.search(path.name)
        if not match:
            continue
        raw = match.group("year")
        try:
            years.add(int(raw))
        except ValueError:
            continue
    return years


def find_template_layer(layers: list[dict[str, Any]]) -> dict[str, Any] | None:
    for layer in layers:
        if layer.get("id") == "lst-planegg":
            return layer
    return None


def build_entry(year: int, template: dict[str, Any] | None, id_prefix: str, relative_path_template: str) -> dict[str, Any]:
    base_legend = {
        "type": "continuous",
        "palette": [
            "#313695",
            "#4575b4",
            "#74add1",
            "#abd9e9",
            "#e0f3f8",
            "#fee090",
            "#fdae61",
            "#f46d43",
            "#d73027",
        ],
        "labels": ["cooler", "warmer"],
    }

    source = template.get("source") if template else "Landsat 8/9 Collection 2 Level 2 (LANDSAT/LC08-09/C02/T1_L2), Google Earth Engine"
    attribution = template.get("attribution") if template else "USGS/NASA Landsat, processed via Google Earth Engine"
    native_crs = template.get("native_crs") if template else "EPSG:4326"
    nodata = template.get("nodata") if template and template.get("nodata") is not None else 0
    min_zoom = template.get("min_zoom", 8) if template else 8
    max_zoom = template.get("max_zoom", 18) if template else 18

    return {
        "id": f"{id_prefix}-{year}",
        "title": f"Relative Summer LST Anomaly {year}",
        "short_title": f"LST anomaly {year}",
        "description": f"Relative summer LST anomaly for Planegg ({year} summer mean anomaly around Planegg mean, °C).",
        "layer_type": "raster",
        "thematic_group": "Heat",
        "area": "planegg",
        "storage_backend": "local",
        "relative_path": relative_path_template.format(year=year),
        "data_format": "geotiff",
        "source": source,
        "attribution": attribution,
        "units": "°C",
        "value_type": "continuous",
        "native_crs": native_crs,
        "acquisition_date": f"{year}-08-31",
        "temporal_start": f"{year}-06-01",
        "temporal_end": f"{year}-08-31",
        "temporal_group": "relative_summer_lst",
        "temporal_metric": "anomaly_degC",
        "temporal_year": year,
        "spatial_resolution": 30,
        "nodata": nodata,
        "value_range": {"minimum": -5, "maximum": 5},
        "default_visible": False,
        "default_opacity": 0.75,
        "default_order": 120 + (year % 100),
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "inspectable": True,
        "selectable": True,
        "style": {
            "color_scale": "temperature",
            "interpolation": "linear",
            "opacity": 0.75,
        },
        "legend": template.get("legend", base_legend) if template else base_legend,
        "analysis_capabilities": ["point_value", "area_statistics"],
        "tags": ["heat", "lst", "landsat", "relative-summer-lst", "planegg", "timeseries"],
        "is_demo": False,
    }


def main() -> int:
    args = parse_args()
    catalog_path = args.catalog.resolve()
    summary_csv = args.summary_csv.resolve()
    rasters_dir = args.rasters_dir.resolve()

    payload = load_catalog(catalog_path)
    layers: list[dict[str, Any]] = payload["layers"]

    years = set()
    years |= collect_years_from_csv(summary_csv)
    years |= collect_years_from_rasters(rasters_dir, args.filename_regex)

    if not years:
        print("No years found. Provide a yearly summary CSV and/or matching raster files.")
        return 1

    template = find_template_layer(layers)
    existing_index: dict[str, int] = {str(layer.get("id")): idx for idx, layer in enumerate(layers)}

    created_ids: list[str] = []
    updated_ids: list[str] = []
    skipped_ids: list[str] = []

    for year in sorted(years):
        entry = build_entry(year, template, args.id_prefix, args.relative_path_template)
        layer_id = entry["id"]
        idx = existing_index.get(layer_id)
        if idx is None:
            layers.append(entry)
            created_ids.append(layer_id)
            continue
        if args.overwrite_existing:
            layers[idx] = entry
            updated_ids.append(layer_id)
        else:
            skipped_ids.append(layer_id)

    print("Relative summer LST registration preview")
    print(f"- Catalog: {catalog_path}")
    print(f"- Summary CSV: {summary_csv} ({'found' if summary_csv.exists() else 'missing'})")
    print(f"- Rasters dir: {rasters_dir} ({'found' if rasters_dir.exists() else 'missing'})")
    print(f"- Years: {', '.join(str(y) for y in sorted(years))}")
    print(f"- Create: {len(created_ids)}")
    print(f"- Update: {len(updated_ids)}")
    print(f"- Skip: {len(skipped_ids)}")

    if created_ids:
        print("  Created ids:", ", ".join(created_ids))
    if updated_ids:
        print("  Updated ids:", ", ".join(updated_ids))
    if skipped_ids:
        print("  Skipped ids:", ", ".join(skipped_ids))

    if not args.apply:
        print("Dry-run only. Re-run with --apply to write catalog changes.")
        return 0

    with catalog_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True, width=120)

    print("Catalog updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
