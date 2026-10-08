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
        layer_id = f"rgb-sentinel-planegg-{year}"
        if layer_id in existing_ids:
            continue

        layers.append(
            {
                "id": layer_id,
                "title": f"Planegg Sentinel-2 RGB Composite {year}",
                "short_title": f"RGB {year}",
                "description": f"Sentinel-2 true-color yearly median composite ({year}-04-01 to {year}-10-31), aligned with Dynamic World LULC season.",
                "layer_type": "raster",
                "thematic_group": "Basemap",
                "area": "planegg",
                "storage_backend": "local",
                "relative_path": f"rasters/derived/planegg/rgb_yearly/rgb_{year}.tif",
                "data_format": "geotiff",
                "source": "Sentinel-2 SR Harmonized (COPERNICUS/S2_SR_HARMONIZED), Google Earth Engine",
                "attribution": "Copernicus Sentinel-2 / ESA, processed via Google Earth Engine",
                "units": "RGB reflectance",
                "value_type": "rgb",
                "native_crs": "EPSG:4326",
                "acquisition_date": f"{year}-10-31",
                "temporal_start": f"{year}-04-01",
                "temporal_end": f"{year}-10-31",
                "temporal_group": "rgb_yearly",
                "temporal_metric": "median_reflectance",
                "temporal_year": year,
                "spatial_resolution": 10,
                "nodata": 0,
                "default_visible": False,
                "default_opacity": 0.75,
                "default_order": 260 + (year - args.start_year),
                "min_zoom": 8,
                "max_zoom": 18,
                "inspectable": False,
                "selectable": False,
                "style": {
                    "color_scale": "rgb",
                    "interpolation": "linear",
                    "opacity": 0.75,
                },
                "legend": {
                    "type": "categorical",
                    "palette": ["#000000"],
                    "labels": ["True-color imagery"],
                },
                "analysis_capabilities": [],
                "tags": ["rgb", "sentinel-rgb", "sentinel-2", "planegg", "timeseries"],
                "is_demo": False,
            }
        )
        created.append(layer_id)

    print(f"Will create {len(created)} Sentinel RGB yearly layers.")
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
