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
        "--forest-lulc-raster",
        type=Path,
        default=Path("storage/rasters/processed/planegg/lulc.tif"),
        help="Land-cover raster used to identify very large forest cores for batching.",
    )
    parser.add_argument(
        "--forest-probability-raster",
        type=Path,
        default=None,
        help="Optional tree/forest probability raster (0-1 or 0-100) for forest-core filtering.",
    )
    parser.add_argument(
        "--forest-probability-threshold",
        type=float,
        default=0.6,
        help="Minimum forest probability to treat pixel as forest core (default: 0.6).",
    )
    parser.add_argument(
        "--forest-classes",
        type=str,
        default="1",
        help="Comma-separated class IDs treated as forest in LULC (Dynamic World trees=1).",
    )
    parser.add_argument(
        "--forest-min-patch-area-ha",
        type=float,
        default=15.0,
        help="Only forest patches larger than this area (hectares) are batched as forest.",
    )
    parser.add_argument(
        "--forest-edge-buffer-m",
        type=float,
        default=60.0,
        help="Negative buffer from forest edges (meters); trees near non-forest remain individual.",
    )
    parser.add_argument(
        "--forest-batch-cell-size-m",
        type=float,
        default=220.0,
        help="Batch/aggregation cell size for forest trees (meters).",
    )
    parser.add_argument(
        "--forest-min-features-per-patch",
        type=int,
        default=50,
        help="Minimum tree features in a forest batch-cell before canopy union aggregation.",
    )
    parser.add_argument(
        "--forest-height-quantile",
        type=float,
        default=0.9,
        help="Height quantile for aggregated forest canopy patch elevation (0.5-1.0).",
    )
    parser.add_argument(
        "--working-scale",
        type=float,
        default=1.0,
        help="Coarsening factor for ray-casting grid. 1.0 = full 1m detail (highest quality, slower).",
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
    parser.add_argument(
        "--tree-crown-scale",
        type=float,
        default=1.25,
        help="Scale factor for tree canopy footprint size (Option B realism tuning).",
    )
    parser.add_argument(
        "--no-preserve-tree-shells",
        action="store_true",
        help="Disable layered canopy shell preservation and collapse each tree to one canopy polygon.",
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
    if not args.boundary.exists():
        logger.error(f"Boundary not found: {args.boundary}")
        logger.error("Shade generation is boundary-clipped by design. Provide a valid Planegg boundary file.")
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
        boundary_geojson=args.boundary,
        tree_canopy_buffer_m=args.tree_canopy_buffer,
        forest_lulc_raster_path=args.forest_lulc_raster if args.forest_lulc_raster.exists() else None,
        forest_probability_raster_path=(
            args.forest_probability_raster
            if args.forest_probability_raster and args.forest_probability_raster.exists()
            else None
        ),
        forest_classes=args.forest_classes,
        forest_probability_threshold=args.forest_probability_threshold,
        min_forest_patch_area_m2=args.forest_min_patch_area_ha * 10_000.0,
        forest_edge_buffer_m=args.forest_edge_buffer_m,
        forest_batch_cell_size_m=args.forest_batch_cell_size_m,
        forest_min_features_per_patch=args.forest_min_features_per_patch,
        forest_height_quantile=args.forest_height_quantile,
        tree_crown_scale=args.tree_crown_scale,
        preserve_tree_shell_layers=not args.no_preserve_tree_shells,
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
    sun_hours_ground_id = f"sun-hours-ground-{date_str}"
    shade_hours_ground_id = f"shade-hours-ground-{date_str}"
    shade_fraction_ground_id = f"shade-fraction-ground-{date_str}"
    simulation_times = [t.strip() for t in args.times.split(",") if t.strip()]

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

    if sun_hours_ground_id not in existing_ids:
        layers_to_add.append({
            "id": sun_hours_ground_id,
            "title": f"Ground Sun Hours - {args.date}",
            "short_title": "Ground Sun Hours",
            "description": f"Ground-level hours of direct sunlight on {args.date}",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/sun_hours_ground_{args.date}.tif",
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
            "default_order": 44,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "solar", "sun-hours", "ground", "modelling", "planegg"],
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

    if shade_hours_ground_id not in existing_ids:
        layers_to_add.append({
            "id": shade_hours_ground_id,
            "title": f"Ground Shade Hours - {args.date}",
            "short_title": "Ground Shade Hours",
            "description": f"Ground-level hours of shade on {args.date}",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_hours_ground_{args.date}.tif",
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
            "default_order": 45,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "ground", "modelling", "planegg"],
            "is_demo": False,
            "style": {
                "color_scale": "shade_sun_hours",
                "interpolation": "nearest",
                "opacity": 0.7,
            },
            "legend": {
                "type": "continuous",
                "palette": ["#f8fafc", "#cbd5e1", "#60a5fa", "#2563eb", "#0f172a"],
                "labels": ["0 h", "4.5 h", "9 h"],
            },
        })

    if shade_fraction_ground_id not in existing_ids:
        layers_to_add.append({
            "id": shade_fraction_ground_id,
            "title": f"Ground Shade Fraction - {args.date}",
            "short_title": "Ground Shade Fraction",
            "description": f"Ground-level fraction of day in shade on {args.date}",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_fraction_ground_{args.date}.tif",
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
            "default_order": 46,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "ground", "modelling", "planegg"],
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

    # Register single-time shade layers for each simulated hour.
    # These layers are binary: 0=sunlit, 1=shaded.
    for idx, time_str in enumerate(simulation_times):
        time_key = time_str.replace(":", "")
        hour_layer_id = f"shade-overpass-{date_str}-{time_key}"
        if hour_layer_id in existing_ids:
            continue

        layers_to_add.append({
            "id": hour_layer_id,
            "title": f"Shade at {time_str} - {args.date}",
            "short_title": f"Shade {time_str}",
            "description": f"Shade state at {time_str} on {args.date} (0=sunlit, 1=shaded)",
            "layer_type": "raster",
            "thematic_group": "shade",
            "area": "planegg",
            "storage_backend": "local",
            "relative_path": f"rasters/derived/planegg/shade/shade_overpass_{args.date}_{time_key}.tif",
            "data_format": "geotiff",
            "source": "Urban Climate Tool shade model",
            "units": "shade_intensity",
            "value_type": "continuous",
            "native_crs": "EPSG:25832",
            "analysis_capabilities": ["point_value", "area_statistics"],
            "spatial_resolution": 1,
            "nodata": -9999,
            "value_range": {"minimum": 0, "maximum": 1},
            "default_visible": False,
            "default_opacity": 0.75,
            "default_order": 60 + idx,
            "min_zoom": 11,
            "max_zoom": 20,
            "inspectable": True,
            "selectable": True,
            "tags": ["shade", "solar", "overpass", "hourly", "planegg"],
            "is_demo": False,
            "style": {
                "color_scale": "shade_overpass",
                "interpolation": "nearest",
                "opacity": 0.75,
            },
            "legend": {
                "type": "continuous",
                "palette": ["#ffffff", "#d4d4d8", "#52525b", "#000000"],
                "labels": ["Transparent (sunlit)", "Medium shade", "Full shade"],
            },
        })

        ground_hour_layer_id = f"shade-ground-overpass-{date_str}-{time_key}"
        if ground_hour_layer_id not in existing_ids:
            layers_to_add.append({
                "id": ground_hour_layer_id,
                "title": f"Ground Shade at {time_str} - {args.date}",
                "short_title": f"Ground Shade {time_str}",
                "description": f"Ground-level shade state at {time_str} on {args.date} (0=sunlit, 1=shaded)",
                "layer_type": "raster",
                "thematic_group": "shade",
                "area": "planegg",
                "storage_backend": "local",
                "relative_path": f"rasters/derived/planegg/shade/shade_ground_overpass_{args.date}_{time_key}.tif",
                "data_format": "geotiff",
                "source": "Urban Climate Tool shade model",
                "units": "shade_intensity",
                "value_type": "continuous",
                "native_crs": "EPSG:25832",
                "analysis_capabilities": ["point_value", "area_statistics"],
                "spatial_resolution": 1,
                "nodata": -9999,
                "value_range": {"minimum": 0, "maximum": 1},
                "default_visible": False,
                "default_opacity": 0.75,
                "default_order": 90 + idx,
                "min_zoom": 11,
                "max_zoom": 20,
                "inspectable": True,
                "selectable": True,
                "tags": ["shade", "ground", "solar", "overpass", "hourly", "planegg"],
                "is_demo": False,
                "style": {
                    "color_scale": "shade_overpass",
                    "interpolation": "nearest",
                    "opacity": 0.75,
                },
                "legend": {
                    "type": "continuous",
                    "palette": ["#ffffff", "#d4d4d8", "#52525b", "#000000"],
                    "labels": ["Transparent (sunlit)", "Medium shade", "Full shade"],
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
    logger.info(
        "Forest batching: classes=%s, min_patch=%.1f ha, edge_buffer=%.1f m, cell=%.1f m",
        args.forest_classes,
        args.forest_min_patch_area_ha,
        args.forest_edge_buffer_m,
        args.forest_batch_cell_size_m,
    )
    logger.info(f"Tree crown scale: {args.tree_crown_scale:.2f}x")
    logger.info(f"Preserve tree shells: {not args.no_preserve_tree_shells}")
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
            dem_path=args.dem if args.dem.exists() else None,
            boundary_geojson=args.boundary,
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
        logger.info(f"  - {args.output_dir}/shade_fraction_ground_{args.date}.tif")
        logger.info("")
        logger.info("View in frontend at: Shade & Solar > select layer")
        logger.info("")

    except Exception as e:
        logger.error(f"Failed to compute shade: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
