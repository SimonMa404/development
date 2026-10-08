#!/usr/bin/env python3
"""
Generate shade and sun hour rasters for Planegg (Phase 2).

This assumes DSM has already been built with generate_dsm_only.py.
If DSM doesn't exist, it will be built first (slower).

Usage:
    # Use pre-built DSM (fast)
    python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --register

    # With custom times (3 key times + interpolation)
    python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --times 08:00,12:00,18:00 --register

    # Regenerate DSM
    python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --rebuild-dsm --register
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.shade_service_optimized import ShadeServiceOptimized


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate shade and sun hour rasters (Phase 2 - fast mode)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default="2023-07-21",
        help="Target date (YYYY-MM-DD) for simulation. Default: 2023-07-21 (summer reference day)",
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
        help="Comma-separated times to simulate (HH:MM). For fast runs, use 08:00,12:00,18:00",
    )
    parser.add_argument(
        "--tree-transmissivity",
        type=float,
        default=0.2,
        help="Fraction of sunlight passing through tree canopy (0-1). Default: 0.2 (20%%)",
    )
    parser.add_argument(
        "--tree-canopy-buffer",
        type=float,
        default=1.5,
        help="Additional buffer (meters) applied to tree canopy polygons in DSM build. Improves canopy edge shading.",
    )
    parser.add_argument(
        "--working-scale",
        type=float,
        default=2.0,
        help="Coarsening factor for ray-casting grid. 1.0 = full 1m detail (slow), 2.0 = high quality default.",
    )
    parser.add_argument(
        "--max-shadow-distance",
        type=int,
        default=250,
        help="Maximum shadow ray marching distance in meters. Higher captures longer shadows but increases runtime.",
    )
    parser.add_argument(
        "--dem",
        type=Path,
        default=Path("storage/rasters/processed/planegg/dem_1m.tif"),
        help="Path to DEM GeoTIFF",
    )
    parser.add_argument(
        "--dsm",
        type=Path,
        default=Path("storage/rasters/derived/planegg/dsm_1m.tif"),
        help="Path to pre-built DSM. If not found, will build it.",
    )
    parser.add_argument(
        "--buildings",
        type=Path,
        default=Path("storage/vectors/processed/planegg/buildings_3d.geojson"),
        help="Path to buildings GeoJSON",
    )
    parser.add_argument(
        "--buildings-raster",
        type=Path,
        default=Path("storage/rasters/derived/planegg/building_heights_1m.tif"),
        help="Path to cached building height raster",
    )
    parser.add_argument(
        "--trees",
        type=Path,
        default=Path("storage/vectors/processed/planegg/trees.geojson"),
        help="Path to trees GeoJSON",
    )
    parser.add_argument(
        "--canopy",
        type=Path,
        default=Path("storage/rasters/derived/planegg/tree_canopy_1m.tif"),
        help="Path to tree canopy raster",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("storage/vectors/processed/planegg/boundary.geojson"),
        help="Path to Planegg boundary GeoJSON (clips modelling extent to municipality)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("storage/rasters/derived/planegg/shade"),
        help="Directory to write shade rasters",
    )
    parser.add_argument(
        "--rebuild-dsm",
        action="store_true",
        help="Force rebuild DSM even if it exists",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register layers in catalog",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("catalog/layers.yaml"),
        help="Path to catalog",
    )

    return parser.parse_args()


def validate_inputs(args):
    """Check that all input files exist."""
    if not args.dem.exists():
        logger.error(f"DEM not found: {args.dem}")
        return False
    if not args.buildings.exists():
        logger.error(f"Buildings not found: {args.buildings}")
        return False
    if not args.trees.exists():
        logger.error(f"Trees not found: {args.trees}")
        return False
    return True


def ensure_dsm(args):
    """Build DSM if it doesn't exist or if rebuild requested."""
    if args.dsm.exists() and not args.rebuild_dsm:
        logger.info(f"Using existing DSM: {args.dsm}")
        return

    logger.info("Building DSM (this may take a few minutes on first run)...")
    service = ShadeServiceOptimized()
    service.build_dsm_with_obstruction_layers(
        dem_path=args.dem,
        buildings_geojson=args.buildings,
        trees_geojson=args.trees,
        output_dsm_path=args.dsm,
        output_building_heights_path=args.buildings_raster,
        output_tree_canopy_path=args.canopy,
        boundary_geojson=args.boundary if args.boundary.exists() else None,
        tree_canopy_buffer_m=args.tree_canopy_buffer,
    )
    logger.info(f"✓ DSM ready: {args.dsm}")


def register_shade_layers(args):
    """Add shade layers to catalog."""
    logger.info("Registering shade layers in catalog...")

    catalog_path = args.catalog
    with open(catalog_path) as f:
        catalog = yaml.safe_load(f)

    date_str = args.date.replace("-", "")

    # Layer IDs
    sun_hours_id = f"sun-hours-{date_str}"
    shade_hours_id = f"shade-hours-{date_str}"
    shade_fraction_id = f"shade-fraction-{date_str}"

    # Check if already registered
    existing_ids = {layer["id"] for layer in catalog.get("layers", [])}

    layers_to_add = []

    if sun_hours_id not in existing_ids:
        layers_to_add.append({
            "id": sun_hours_id,
            "title": f"Sun Hours - {args.date}",
            "short_title": "Sun Hours",
            "description": f"Hours of direct sunlight on {args.date}",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/sun_hours_{args.date}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade model",
            "units": "hours",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "analysis_capabilities": ["point_value", "area_statistics"],
            "spatial_resolution": 1,
            "nodata": 0,
            "value_range": {"minimum": 0, "maximum": 9},
            "default_visible": False,
            "default_opacity": 0.7,
            "default_order": 41,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "solar", "sun-hours", "modelling", "planegg"],
            "is_demo": False,
            "style": {
                "color_scale": "shade_sun_hours",
                "interpolation": "nearest",
                "opacity": 0.7,
            },
            "legend": {
                "type": "continuous",
                "palette": ["#0f172a", "#1d4ed8", "#22d3ee", "#fde047", "#f97316", "#dc2626"],
                "labels": ["0 h", "4.5 h", "9 h"],
            },
        })

    if shade_hours_id not in existing_ids:
        layers_to_add.append({
            "id": shade_hours_id,
            "title": f"Shade Hours - {args.date}",
            "short_title": "Shade Hours",
            "description": f"Hours of shade on {args.date}",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_hours_{args.date}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade model",
            "units": "hours",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "analysis_capabilities": ["point_value", "area_statistics"],
            "spatial_resolution": 1,
            "nodata": 0,
            "value_range": {"minimum": 0, "maximum": 9},
            "default_visible": False,
            "default_opacity": 0.7,
            "default_order": 42,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "modelling", "planegg"],
            "is_demo": False,
            "style": {
                "color_scale": "shade_shade_hours",
                "interpolation": "nearest",
                "opacity": 0.7,
            },
            "legend": {
                "type": "continuous",
                "palette": ["#f8fafc", "#cbd5e1", "#60a5fa", "#2563eb", "#0f172a"],
                "labels": ["0 h", "4.5 h", "9 h"],
            },
        })

    if shade_fraction_id not in existing_ids:
        layers_to_add.append({
            "id": shade_fraction_id,
            "title": f"Shade Fraction - {args.date}",
            "short_title": "Shade Fraction",
            "description": f"Fraction of day in shade on {args.date}",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_fraction_{args.date}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade model",
            "units": "fraction",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "analysis_capabilities": ["point_value", "area_statistics"],
            "spatial_resolution": 1,
            "nodata": 0,
            "value_range": {"minimum": 0, "maximum": 1},
            "default_visible": False,
            "default_opacity": 0.7,
            "default_order": 43,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "modelling", "planegg"],
            "is_demo": False,
            "style": {
                "color_scale": "shade_fraction",
                "interpolation": "nearest",
                "opacity": 0.7,
            },
            "legend": {
                "type": "continuous",
                "palette": ["#f8fafc", "#cbd5e1", "#60a5fa", "#2563eb", "#0f172a"],
                "labels": ["0%", "50%", "100%"],
            },
        })

    if layers_to_add:
        catalog["layers"].extend(layers_to_add)
        with open(catalog_path, "w") as f:
            yaml.dump(catalog, f, default_flow_style=False, sort_keys=False)
        logger.info(f"✓ Registered {len(layers_to_add)} new layers in catalog")
    else:
        logger.info("All layers already registered")


def main():
    args = parse_args()

    logger.info("=" * 70)
    logger.info("Urban Climate Tool - Shade Generation (Phase 2 - Fast Mode)")
    logger.info("=" * 70)
    logger.info(f"Date: {args.date}")
    logger.info(f"Times: {args.times}")
    logger.info(f"Tree transmissivity: {args.tree_transmissivity * 100:.0f}%")
    logger.info(f"Tree canopy buffer: {args.tree_canopy_buffer:.2f} m")
    logger.info(f"Working scale: {args.working_scale}x")
    logger.info(f"Max shadow distance: {args.max_shadow_distance} m")
    logger.info(f"Timezone: {args.timezone}")
    logger.info("")

    # Validate
    if not validate_inputs(args):
        sys.exit(1)

    # Ensure DSM exists
    ensure_dsm(args)

    logger.info("")
    logger.info("=" * 70)
    logger.info("PHASE 2: Computing Shade Rasters")
    logger.info("=" * 70)

    try:
        times = [t.strip() for t in args.times.split(",")]

        service = ShadeServiceOptimized()
        service.compute_shade_rasters(
            dsm_path=args.dsm,
            output_dir=args.output_dir,
            date=args.date,
            timezone=args.timezone,
            times=times,
            tree_transmissivity=args.tree_transmissivity,
            tree_canopy_path=args.canopy if args.canopy.exists() else None,
            boundary_geojson=args.boundary if args.boundary.exists() else None,
            working_scale=args.working_scale,
            max_shadow_distance_m=args.max_shadow_distance,
        )

        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ Shade Generation Complete!")
        logger.info("=" * 70)

        if args.register:
            register_shade_layers(args)

        logger.info("")
        logger.info("Output files:")
        logger.info(f"  - {args.output_dir}/sun_hours_{args.date}.tif")
        logger.info(f"  - {args.output_dir}/shade_hours_{args.date}.tif")
        logger.info(f"  - {args.output_dir}/shade_fraction_{args.date}.tif")
        logger.info("")
        logger.info("View in frontend at: Shade & Solar > select layer")
        logger.info("")

    except Exception as e:
        logger.error(f"Failed to compute shade: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
