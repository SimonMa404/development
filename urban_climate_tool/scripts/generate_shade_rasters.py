#!/usr/bin/env python3
"""
Generate shade and sun hour rasters for Planegg.

This script orchestrates the shade modelling pipeline:
1. Builds a DSM from DEM, buildings, and trees
2. Computes solar position for each timestamp
3. Casts shadows and accumulates shade/sun hours
4. Registers outputs in the catalog

Usage:
    python scripts/generate_shade_rasters.py [--date YYYY-MM-DD] [--register]

Example:
    python scripts/generate_shade_rasters.py --date 2023-07-21 --register
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import sys
import yaml

# Add backend to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.shade_service import ShadeService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate shade and sun hour rasters for Planegg.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2023-07-21",
        help="Target date (YYYY-MM-DD) for summer reference day. Default: 2023-07-21",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="Europe/Berlin",
        help="Timezone for solar calculations. Default: Europe/Berlin",
    )
    parser.add_argument(
        "--times",
        type=str,
        default="10:00,11:00,12:00,13:00,14:00,15:00,16:00,17:00,18:00",
        help="Comma-separated times to simulate (HH:MM). Default: 10:00-18:00 hourly",
    )
    parser.add_argument(
        "--tree-transmissivity",
        type=float,
        default=0.2,
        help="Fraction of direct sunlight passing through trees (0-1). Default: 0.2 (20%% pass through)",
    )
    parser.add_argument(
        "--dem",
        type=Path,
        default=REPO_ROOT / "storage" / "rasters" / "processed" / "planegg" / "dem_1m.tif",
        help="Path to DEM GeoTIFF.",
    )
    parser.add_argument(
        "--buildings",
        type=Path,
        default=REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "buildings_3d.geojson",
        help="Path to buildings GeoJSON.",
    )
    parser.add_argument(
        "--trees",
        type=Path,
        default=REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "trees.geojson",
        help="Path to trees GeoJSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "storage" / "rasters" / "derived" / "planegg" / "shade",
        help="Output directory for shade rasters.",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register outputs in catalog/layers.yaml.",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=REPO_ROOT / "catalog" / "layers.yaml",
        help="Path to catalog YAML.",
    )
    return parser.parse_args()


def validate_inputs(dem: Path, buildings: Path, trees: Path) -> bool:
    """Check that all required input files exist."""
    missing = []
    for path, name in [(dem, "DEM"), (buildings, "buildings"), (trees, "trees")]:
        if not path.exists():
            missing.append(f"{name}: {path}")
    if missing:
        logger.error("Missing input files:")
        for msg in missing:
            logger.error(f"  {msg}")
        return False
    return True


def register_shade_layers(
    output_dir: Path,
    catalog_path: Path,
    date: str,
) -> None:
    """Register generated shade rasters in the catalog."""
    logger.info(f"Registering shade layers in {catalog_path}")

    if not catalog_path.exists():
        logger.error(f"Catalog not found: {catalog_path}")
        return

    with catalog_path.open("r", encoding="utf-8") as f:
        catalog = yaml.safe_load(f) or {"layers": []}

    if "layers" not in catalog:
        catalog["layers"] = []

    layers_to_add = [
        {
            "id": f"shade-sun-hours-{date.replace('-', '')}",
            "title": f"Daily Sun Hours {date}",
            "short_title": f"Sun Hours {date}",
            "description": f"Hours of direct sunlight per day, summer reference day {date}.",
            "layer_type": "raster",
            "thematic_group": "Shade & Solar",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/sun_hours_{date}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade modelling (pvlib + DSM ray-casting)",
            "attribution": "DEM (BayernWolke), CityGML buildings, OpenData trees",
            "units": "hours",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "acquisition_date": date,
            "spatial_resolution": 1,
            "nodata": 0,
            "value_range": {"minimum": 0, "maximum": 8},
            "default_visible": False,
            "default_opacity": 0.75,
            "default_order": 50,
            "min_zoom": 8,
            "max_zoom": 18,
            "inspectable": True,
            "selectable": True,
            "style": {
                "color_scale": "shade_sun_hours",
                "interpolation": "linear",
                "opacity": 0.75,
            },
            "legend": {
                "type": "continuous",
                "palette": [
                    "#1a1a1a",
                    "#404040",
                    "#808080",
                    "#ffff00",
                    "#ffcc00",
                    "#ff9900",
                    "#ff6600",
                    "#ff3300",
                ],
                "labels": ["0 hours", "8+ hours"],
            },
            "analysis_capabilities": ["point_value", "area_statistics"],
            "tags": ["shade", "solar", "sun-hours", "planegg"],
            "is_demo": False,
        },
        {
            "id": f"shade-shade-hours-{date.replace('-', '')}",
            "title": f"Daily Shade Hours {date}",
            "short_title": f"Shade Hours {date}",
            "description": f"Hours of shade (buildings or trees) per day, summer reference day {date}.",
            "layer_type": "raster",
            "thematic_group": "Shade & Solar",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_hours_{date}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade modelling (pvlib + DSM ray-casting)",
            "attribution": "DEM (BayernWolke), CityGML buildings, OpenData trees",
            "units": "hours",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "acquisition_date": date,
            "spatial_resolution": 1,
            "nodata": 0,
            "value_range": {"minimum": 0, "maximum": 8},
            "default_visible": False,
            "default_opacity": 0.75,
            "default_order": 51,
            "min_zoom": 8,
            "max_zoom": 18,
            "inspectable": True,
            "selectable": True,
            "style": {
                "color_scale": "shade_hours",
                "interpolation": "linear",
                "opacity": 0.75,
            },
            "legend": {
                "type": "continuous",
                "palette": [
                    "#ff6600",
                    "#ff9900",
                    "#ffcc00",
                    "#ffff00",
                    "#808080",
                    "#404040",
                    "#1a1a1a",
                ],
                "labels": ["0 hours", "8+ hours"],
            },
            "analysis_capabilities": ["point_value", "area_statistics"],
            "tags": ["shade", "solar", "shade-hours", "planegg"],
            "is_demo": False,
        },
        {
            "id": f"shade-fraction-{date.replace('-', '')}",
            "title": f"Shade Fraction {date}",
            "short_title": f"Shade % {date}",
            "description": f"Percentage of time in shade during daylight hours, summer reference day {date}.",
            "layer_type": "raster",
            "thematic_group": "Shade & Solar",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_fraction_{date}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade modelling (pvlib + DSM ray-casting)",
            "attribution": "DEM (BayernWolke), CityGML buildings, OpenData trees",
            "units": "%",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "acquisition_date": date,
            "spatial_resolution": 1,
            "nodata": 0,
            "value_range": {"minimum": 0, "maximum": 100},
            "default_visible": False,
            "default_opacity": 0.75,
            "default_order": 52,
            "min_zoom": 8,
            "max_zoom": 18,
            "inspectable": True,
            "selectable": True,
            "style": {
                "color_scale": "shade_fraction",
                "interpolation": "linear",
                "opacity": 0.75,
            },
            "legend": {
                "type": "continuous",
                "palette": [
                    "#ffff00",
                    "#ffcc00",
                    "#ff9900",
                    "#ff6600",
                    "#ff3300",
                    "#1a1a1a",
                ],
                "labels": ["0%", "100%"],
            },
            "analysis_capabilities": ["point_value", "area_statistics"],
            "tags": ["shade", "solar", "shade-fraction", "planegg"],
            "is_demo": False,
        },
    ]

    # Add or update layers
    existing_ids = {layer.get("id") for layer in catalog["layers"]}
    for new_layer in layers_to_add:
        if new_layer["id"] not in existing_ids:
            catalog["layers"].append(new_layer)
            logger.info(f"  Added: {new_layer['id']}")
        else:
            logger.info(f"  Skipped (already exists): {new_layer['id']}")

    # Write updated catalog
    with catalog_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(catalog, f, sort_keys=False, allow_unicode=True, width=120)

    logger.info(f"Catalog updated: {catalog_path}")


def main() -> int:
    args = parse_args()

    logger.info("="*70)
    logger.info("Urban Climate Tool - Shade Raster Generation")
    logger.info("="*70)
    logger.info(f"Date: {args.date}")
    logger.info(f"Times: {args.times}")
    logger.info(f"Tree transmissivity: {args.tree_transmissivity * 100:.0f}%")
    logger.info(f"Timezone: {args.timezone}")

    # Validate inputs
    if not validate_inputs(args.dem, args.buildings, args.trees):
        return 1

    # Initialize service
    try:
        service = ShadeService()
    except RuntimeError as e:
        logger.error(f"Failed to initialize shade service: {e}")
        return 1

    # Step 1: Build DSM
    logger.info("\n" + "="*70)
    logger.info("STEP 1: Building Digital Surface Model (DSM)")
    logger.info("="*70)
    dsm_path = args.output_dir / "dsm_1m.tif"
    tree_canopy_path = args.output_dir / "tree_canopy_1m.tif"

    try:
        service.build_dsm_with_obstruction_layers(
            dem_path=args.dem,
            buildings_geojson=args.buildings,
            trees_geojson=args.trees,
            output_dsm_path=dsm_path,
            output_tree_canopy_path=tree_canopy_path,
        )
    except Exception as e:
        logger.error(f"Failed to build DSM: {e}", exc_info=True)
        return 1

    # Step 2: Compute shade rasters
    logger.info("\n" + "="*70)
    logger.info("STEP 2: Computing Shade Rasters")
    logger.info("="*70)

    times = args.times.split(",")
    try:
        outputs = service.compute_shade_rasters(
            dem_path=args.dem,
            dsm_path=dsm_path,
            tree_canopy_path=tree_canopy_path,
            output_dir=args.output_dir,
            date=args.date,
            timezone=args.timezone,
            times=times,
            tree_transmissivity=args.tree_transmissivity,
        )
    except Exception as e:
        logger.error(f"Failed to compute shade rasters: {e}", exc_info=True)
        return 1

    logger.info(f"\nGenerated outputs:")
    for name, path in outputs.items():
        if path.exists():
            size_mb = path.stat().st_size / 1024 / 1024
            logger.info(f"  {name}: {path} ({size_mb:.1f} MB)")

    # Step 3: Register (optional)
    if args.register:
        logger.info("\n" + "="*70)
        logger.info("STEP 3: Registering Shade Layers in Catalog")
        logger.info("="*70)
        register_shade_layers(args.output_dir, args.catalog, args.date)

    logger.info("\n" + "="*70)
    logger.info("Shade generation complete!")
    logger.info("="*70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
