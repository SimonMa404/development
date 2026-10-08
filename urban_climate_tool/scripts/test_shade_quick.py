#!/usr/bin/env python3
"""
Quick test: Generate shade for a subset of data to verify pipeline works.
This runs in ~30 seconds total to validate the full workflow.

Usage:
    python scripts/test_shade_quick.py
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.shade_service_optimized import ShadeServiceOptimized


def main():
    logger.info("=" * 70)
    logger.info("Quick Test: Shade Modelling Pipeline")
    logger.info("=" * 70)

    dsm_path = Path("storage/rasters/derived/planegg/dsm_1m.tif")
    canopy_path = Path("storage/rasters/derived/planegg/tree_canopy_1m.tif")
    output_dir = Path("storage/rasters/derived/planegg/shade")

    # Check if DSM exists
    if not dsm_path.exists():
        logger.error(f"DSM not found: {dsm_path}")
        logger.info("Run this first:")
        logger.info("  python scripts/generate_dsm_only.py")
        sys.exit(1)

    logger.info(f"\n✓ DSM found: {dsm_path}")
    logger.info(f"  Size: {dsm_path.stat().st_size / (1024*1024):.1f} MB")

    logger.info("\n" + "=" * 70)
    logger.info("Phase 2: Computing shade rasters (quick test)")
    logger.info("=" * 70)

    try:
        service = ShadeServiceOptimized()
        
        # Quick test with 3 timestamps (fast)
        service.compute_shade_rasters(
            dsm_path=dsm_path,
            output_dir=output_dir,
            date="2023-07-21",
            times=["10:00", "12:00", "18:00"],  # Just 3 for speed
            tree_transmissivity=0.2,
            tree_canopy_path=canopy_path if canopy_path.exists() else None,
        )

        logger.info("\n" + "=" * 70)
        logger.info("✓ SUCCESS: Shade pipeline works!")
        logger.info("=" * 70)
        logger.info(f"\nOutput files:")
        for f in output_dir.glob("*.tif"):
            logger.info(f"  - {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")

        logger.info(f"\nNext: Run full shade generation with 9 timestamps:")
        logger.info(f"  python scripts/generate_shade_rasters_phase2.py --date 2023-07-21 --register")

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
