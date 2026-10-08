#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "layers.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    payload = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    layers: list[dict[str, Any]] = payload.get("layers", [])

    existing_ids = {str(layer.get("id")) for layer in layers}
    created = []

    for year in range(args.start_year, args.end_year + 1):
        layer_id = f"lulc-planegg-{year}"
        if layer_id in existing_ids:
            continue
        layers.append(
            {
                "id": layer_id,
                "title": f"Planegg Land Cover Classes {year}",
                "short_title": f"LULC {year}",
                "description": f"Dominant land-cover class (annual mode composite, {year}) from Google Dynamic World V1.",
                "layer_type": "raster",
                "thematic_group": "Land Cover",
                "area": "planegg",
                "storage_backend": "local",
                "relative_path": f"rasters/derived/planegg/lulc_yearly/lulc_{year}.tif",
                "data_format": "geotiff",
                "source": "Google Dynamic World V1 (GOOGLE/DYNAMICWORLD/V1), Google Earth Engine",
                "attribution": "Google Dynamic World, processed via Google Earth Engine",
                "units": "class",
                "value_type": "categorical",
                "native_crs": "EPSG:4326",
                "acquisition_date": f"{year}-12-31",
                "temporal_start": f"{year}-01-01",
                "temporal_end": f"{year}-12-31",
                "temporal_group": "lulc_yearly",
                "temporal_metric": "dominant_class",
                "temporal_year": year,
                "spatial_resolution": 10,
                "nodata": -2147483648,
                "value_range": {"minimum": 0, "maximum": 8},
                "default_visible": False,
                "default_opacity": 0.8,
                "default_order": 210 + (year - args.start_year),
                "min_zoom": 8,
                "max_zoom": 18,
                "inspectable": True,
                "selectable": True,
                "style": {
                    "color_scale": "categorical",
                    "interpolation": "nearest",
                    "opacity": 0.8,
                },
                "legend": {
                    "type": "categorical",
                    "palette": [
                        "#419BDF",
                        "#397D49",
                        "#88B053",
                        "#7A87C6",
                        "#E49635",
                        "#DFC35A",
                        "#C4281B",
                        "#A59B8F",
                        "#B39FE1",
                    ],
                    "labels": [
                        "Water",
                        "Trees",
                        "Grass",
                        "Flooded vegetation",
                        "Crops",
                        "Shrub & scrub",
                        "Built area",
                        "Bare ground",
                        "Snow & ice",
                    ],
                },
                "analysis_capabilities": ["point_value", "area_statistics"],
                "tags": ["land-cover", "lulc", "dynamic-world", "planegg", "timeseries"],
                "is_demo": False,
            }
        )
        created.append(layer_id)

    print(f"Will create {len(created)} LULC yearly layers.")
    if created:
        print(", ".join(created))

    if args.apply:
        payload["layers"] = layers
        CATALOG.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")
        print("Catalog updated.")
    else:
        print("Dry run. Re-run with --apply.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
