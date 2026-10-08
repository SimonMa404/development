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
