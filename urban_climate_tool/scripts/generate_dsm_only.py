#!/usr/bin/env python3
"""
Generate Digital Surface Model (DSM) for Planegg.

This is Phase 1 of shade generation. The DSM is reusable for all shade calculations,
so generating it once saves significant time on subsequent shade runs.

TIMING EXPECTATIONS:
  - First run: 3-5 minutes (vectorized building + tree rasterization)
  - Includes progress checkpoints to verify intermediate results

Usage:
    python scripts/generate_dsm_only.py
    python scripts/generate_dsm_only.py --dem storage/rasters/processed/planegg/dem_1m.tif
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.shade_service_optimized import ShadeServiceOptimized


def main():
    parser = argparse.ArgumentParser(
        description="Generate Digital Surface Model (DSM) for Planegg",
    )
    parser.add_argument(
        "--dem",
        type=Path,
        default=Path("storage/rasters/processed/planegg/dem_1m.tif"),
        help="Path to DEM GeoTIFF",
    )
    parser.add_argument(
        "--buildings",
        type=Path,
        default=Path("storage/vectors/processed/planegg/buildings_3d.geojson"),
        help="Path to buildings GeoJSON",
    )
    parser.add_argument(
        "--trees",
        type=Path,
        default=Path("storage/vectors/processed/planegg/trees.geojson"),
        help="Path to trees GeoJSON",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("storage/vectors/processed/planegg/boundary.geojson"),
        help="Path to Planegg boundary GeoJSON (clips modelling extent to municipality)",
    )
    parser.add_argument(
        "--output-dsm",
        type=Path,
        default=Path("storage/rasters/derived/planegg/dsm_1m.tif"),
        help="Path to write DSM",
    )
    parser.add_argument(
        "--output-buildings",
        type=Path,
        default=Path("storage/rasters/derived/planegg/building_heights_1m.tif"),
        help="Path to write cached building height raster",
    )
    parser.add_argument(
        "--output-canopy",
        type=Path,
        default=Path("storage/rasters/derived/planegg/tree_canopy_1m.tif"),
        help="Path to write tree canopy layer",
    )
    parser.add_argument(
        "--forest-lulc-raster",
        type=Path,
        default=Path("storage/rasters/processed/planegg/lulc.tif"),
        help="Land-cover raster used to identify large forest cores (Dynamic World class raster).",
    )
    parser.add_argument(
        "--forest-probability-raster",
        type=Path,
        default=None,
        help="Optional tree/forest probability raster (0-1 or 0-100) to refine forest-core selection.",
    )
    parser.add_argument(
        "--forest-probability-threshold",
        type=float,
        default=0.6,
        help="Minimum forest probability for forest-core batching (default: 0.6).",
    )
    parser.add_argument(
        "--forest-classes",
        type=str,
        default="1",
        help="Comma-separated class ids treated as forest in LULC (Dynamic World trees=1).",
    )
    parser.add_argument(
        "--forest-min-patch-area-ha",
        type=float,
        default=15.0,
        help="Only forest patches larger than this area (ha) are eligible for forest batching.",
    )
    parser.add_argument(
        "--forest-edge-buffer-m",
        type=float,
        default=60.0,
        help="Negative buffer (m) on large forest patches; trees near non-forest edges stay individual.",
    )
    parser.add_argument(
        "--forest-batch-cell-size-m",
        type=float,
        default=220.0,
        help="Spatial cell size (m) for forest patch aggregation.",
    )
    parser.add_argument(
        "--forest-min-features-per-patch",
        type=int,
        default=50,
        help="Minimum tree canopies per forest batch cell before geometry aggregation.",
    )
    parser.add_argument(
        "--forest-height-quantile",
        type=float,
        default=0.9,
        help="Canopy height quantile used for aggregated forest patches (0.5-1.0).",
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

    args = parser.parse_args()

    # Validate inputs
    if not args.dem.exists():
        logger.error(f"DEM not found: {args.dem}")
        sys.exit(1)
    if not args.buildings.exists():
        logger.error(f"Buildings not found: {args.buildings}")
        sys.exit(1)
    if not args.trees.exists():
        logger.error(f"Trees not found: {args.trees}")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("Urban Climate Tool - DSM Generation (Phase 1)")
    logger.info("=" * 70)
    logger.info(f"DEM: {args.dem}")
    logger.info(f"Buildings: {args.buildings}")
    logger.info(f"Trees: {args.trees}")
    logger.info(f"Boundary: {args.boundary}")
    logger.info(
        "Forest batching: classes=%s, min_patch=%.1f ha, edge_buffer=%.1f m, cell=%.1f m",
        args.forest_classes,
        args.forest_min_patch_area_ha,
        args.forest_edge_buffer_m,
        args.forest_batch_cell_size_m,
    )
    logger.info(f"Tree crown scale: {args.tree_crown_scale:.2f}x")
    logger.info(f"Preserve tree shells: {not args.no_preserve_tree_shells}")
    logger.info(f"Output DSM: {args.output_dsm}")
    logger.info("")

    try:
        service = ShadeServiceOptimized()
        service.build_dsm_with_obstruction_layers(
            dem_path=args.dem,
            buildings_geojson=args.buildings,
            trees_geojson=args.trees,
            output_dsm_path=args.output_dsm,
            output_building_heights_path=args.output_buildings,
            output_tree_canopy_path=args.output_canopy,
            boundary_geojson=args.boundary if args.boundary.exists() else None,
            forest_lulc_raster_path=args.forest_lulc_raster if args.forest_lulc_raster and args.forest_lulc_raster.exists() else None,
            forest_probability_raster_path=(
                args.forest_probability_raster
                if args.forest_probability_raster and args.forest_probability_raster.exists()
                else None
            ),
            forest_probability_threshold=args.forest_probability_threshold,
            forest_classes=args.forest_classes,
            min_forest_patch_area_m2=args.forest_min_patch_area_ha * 10_000.0,
            forest_edge_buffer_m=args.forest_edge_buffer_m,
            forest_batch_cell_size_m=args.forest_batch_cell_size_m,
            forest_min_features_per_patch=args.forest_min_features_per_patch,
            forest_height_quantile=args.forest_height_quantile,
            tree_crown_scale=args.tree_crown_scale,
            preserve_tree_shell_layers=not args.no_preserve_tree_shells,
        )
        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ DSM Generation Complete!")
        logger.info("=" * 70)
        logger.info(f"DSM saved to: {args.output_dsm}")
        logger.info(f"Building raster saved to: {args.output_buildings}")
        logger.info(f"Tree canopy saved to: {args.output_canopy}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Generate shade rasters:")
        logger.info(f"     python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --register")
        logger.info("")

    except Exception as e:
        logger.error(f"Failed to generate DSM: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
