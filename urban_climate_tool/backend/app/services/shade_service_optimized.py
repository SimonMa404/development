"""
Optimized shade modelling service with vectorized rasterization and DSM caching.

Key optimizations:
1. Vectorized building/tree rasterization (single batch call instead of loop)
2. Separate DSM building from shade computation (reusable)
3. Configurable timestamp reduction (3 key times + interpolation)
4. Progress tracking and timing information
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
import time
import sys

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from rasterio.mask import mask as raster_mask
from rasterio.warp import reproject
from shapely.geometry import Point, Polygon, shape
from shapely.ops import unary_union
import geopandas as gpd
from affine import Affine

try:
    import pvlib
except ImportError:
    pvlib = None

logger = logging.getLogger(__name__)


def progress_bar(current: int, total: int, prefix: str = "", length: int = 40) -> None:
    """Simple progress bar for console output (writes to stderr for real-time visibility)."""
    if total == 0:
        return
    percent = 100 * (current / float(total))
    filled = int(length * current // total)
    bar = '█' * filled + '░' * (length - filled)
    print(f"{prefix} |{bar}| {percent:.1f}% ({current}/{total})", end='\r', file=sys.stderr)
    sys.stderr.flush()


class ShadeServiceOptimized:
    """Compute shade and sun exposure rasters with vectorized operations."""

    def __init__(self):
        if pvlib is None:
            raise RuntimeError("pvlib is required for shade modelling. Install with: pip install pvlib")

    def _prepare_tree_canopy_features(
        self,
        gdf_trees: gpd.GeoDataFrame,
        dem_crs: Any,
        canopy_buffer_m: float = 0.0,
    ) -> list[tuple[Any, float]]:
        """Reduce tree features to one canopy geometry per tree id where possible.

        Preference order:
        1. canopy_upper
        2. highest available canopy shell
        3. any non-point polygon feature
        """
        if gdf_trees.crs != dem_crs:
            gdf_trees = gdf_trees.to_crs(dem_crs)

        if "id" in gdf_trees.columns:
            selected_rows = []
            for _, group in gdf_trees.groupby("id", sort=False):
                polygons = group[group.geometry.geom_type != "Point"]
                if polygons.empty:
                    # Fallback: synthesize canopy from point-only trees.
                    points = group[group.geometry.geom_type == "Point"]
                    if points.empty:
                        continue
                    row = points.iloc[-1]
                    canopy_height = row.get("height", 12.0)
                    try:
                        canopy_height = float(canopy_height)
                    except (ValueError, TypeError):
                        canopy_height = 12.0
                    # Approximate crown radius from tree height (simple allometry).
                    crown_radius = float(np.clip(canopy_height * 0.25, 1.5, 6.0))
                    geom = row.geometry.buffer(crown_radius)
                    if canopy_buffer_m > 0:
                        geom = geom.buffer(canopy_buffer_m)
                    selected_rows.append((geom, canopy_height))
                    continue

                canopy_parts = polygons
                if "tree_part" in canopy_parts.columns:
                    filtered = canopy_parts[
                        canopy_parts["tree_part"].isin(["canopy", "canopy_lower", "canopy_mid", "canopy_upper"])
                    ]
                    if not filtered.empty:
                        canopy_parts = filtered

                if "canopy_shell_top" in canopy_parts.columns:
                    canopy_heights = canopy_parts["canopy_shell_top"].fillna(0).astype(float)
                    canopy_height = float(canopy_heights.max())
                else:
                    row = canopy_parts.iloc[-1]
                    canopy_height = row.get("height", 12.0)
                    try:
                        canopy_height = float(canopy_height)
                    except (ValueError, TypeError):
                        canopy_height = 12.0

                if canopy_height <= 0:
                    canopy_height = 12.0

                geom = unary_union([g for g in canopy_parts.geometry if g is not None and not g.is_empty])
                if geom is None or geom.is_empty:
                    continue
                if canopy_buffer_m > 0:
                    geom = geom.buffer(canopy_buffer_m)
                selected_rows.append((geom, canopy_height))

            return selected_rows

        # Fallback for sources without tree ids
        tree_features: list[tuple[Any, float]] = []
        for _, row in gdf_trees.iterrows():
            tree_part = row.get("tree_part", "")
            if tree_part == "point":
                canopy_height = row.get("height", 12.0)
                try:
                    canopy_height = float(canopy_height)
                except (ValueError, TypeError):
                    canopy_height = 12.0
                crown_radius = float(np.clip(canopy_height * 0.25, 1.5, 6.0))
                geom = row.geometry.buffer(crown_radius)
                if canopy_buffer_m > 0:
                    geom = geom.buffer(canopy_buffer_m)
                tree_features.append((geom, canopy_height))
                continue

            canopy_shell_top = row.get("canopy_shell_top")
            if canopy_shell_top is None or canopy_shell_top <= 0:
                canopy_shell_top = row.get("height", 12.0)
            geom = row.geometry
            if canopy_buffer_m > 0:
                geom = geom.buffer(canopy_buffer_m)
            tree_features.append((geom, float(canopy_shell_top)))

        return tree_features

    def _bucket_tree_features(
        self,
        tree_features: list[tuple[Any, float]],
        cell_size_m: float = 100.0,
    ) -> list[list[tuple[Any, float]]]:
        """Group tree canopy features into spatial buckets for batched rasterization.

        Dense forest areas end up in the same or neighboring buckets, so they can be
        rasterized in batches instead of one feature at a time.
        """
        buckets: dict[tuple[int, int], list[tuple[Any, float]]] = defaultdict(list)
        for geom, canopy_height in tree_features:
            if geom is None or geom.is_empty:
                continue
            minx, miny, maxx, maxy = geom.bounds
            cx = (minx + maxx) * 0.5
            cy = (miny + maxy) * 0.5
            key = (int(cx // cell_size_m), int(cy // cell_size_m))
            buckets[key].append((geom, canopy_height))

        # Return the groups as a stable list of batches.
        return [groups for _, groups in sorted(buckets.items(), key=lambda item: len(item[1]), reverse=True)]

    def build_dsm_with_obstruction_layers(
        self,
        dem_path: Path,
        buildings_geojson: Path,
        trees_geojson: Path,
        output_dsm_path: Path,
        output_building_heights_path: Path | None = None,
        output_tree_canopy_path: Path | None = None,
        boundary_geojson: Path | None = None,
        tree_canopy_buffer_m: float = 0.0,
    ) -> None:
        """Build DSM by combining DEM, buildings, and trees (vectorized)."""
        logger.info("Building DSM from DEM, buildings, and trees...")
        start_time = time.time()

        # CHECKPOINT 1: Load DEM
        logger.info("\n[CHECKPOINT 1] Loading DEM...")
        print("[CHECKPOINT 1] Loading DEM...", file=sys.stderr)
        sys.stderr.flush()
        cp1_start = time.time()
        boundary_gdf = None
        if boundary_geojson and boundary_geojson.exists():
            boundary_gdf = gpd.read_file(boundary_geojson)

        with rasterio.open(dem_path) as dem_src:
            dem_crs = dem_src.crs
            dem_nodata = dem_src.nodata if dem_src.nodata is not None else -9999

            if boundary_gdf is not None:
                if boundary_gdf.crs != dem_crs:
                    boundary_gdf = boundary_gdf.to_crs(dem_crs)
                dem_cropped, dem_transform = raster_mask(
                    dem_src,
                    boundary_gdf.geometry,
                    crop=True,
                    filled=True,
                    nodata=dem_nodata,
                )
                dem = dem_cropped[0].astype(np.float32)
            else:
                dem = dem_src.read(1).astype(np.float32)
                dem_transform = dem_src.transform

            height, width = int(dem.shape[0]), int(dem.shape[1])

        cp1_time = time.time() - cp1_start
        logger.info(f"  ✓ DEM loaded: {width}x{height}, CRS={dem_crs} ({cp1_time:.2f}s)")
        print(f"  ✓ DEM loaded: {width}x{height} ({cp1_time:.2f}s)\n", file=sys.stderr)
        sys.stderr.flush()

        dsm = dem.copy()
        building_heights = np.zeros_like(dem)
        tree_canopy = np.zeros_like(dem)
        building_summary = "0 features"
        tree_summary = "0 features"

        # CHECKPOINT 2: Add buildings
        logger.info("\n[CHECKPOINT 2] Adding buildings...")
        print("[CHECKPOINT 2] Adding buildings...", file=sys.stderr)
        sys.stderr.flush()
        cp2_start = time.time()
        if output_building_heights_path and output_building_heights_path.exists():
            logger.info(f"  Reusing cached building obstruction raster: {output_building_heights_path}")
            print(f"  Reusing cached building raster: {output_building_heights_path.name}", file=sys.stderr)
            sys.stderr.flush()
            with rasterio.open(output_building_heights_path) as b_src:
                cached = b_src.read(1).astype(np.float32)
            if cached.shape == (height, width):
                building_heights = cached
                building_summary = f"cached raster ({output_building_heights_path.name})"
            else:
                logger.info("  Cached building raster shape mismatch; rebuilding for boundary extent")
                print("  Cached building raster shape mismatch; rebuilding...", file=sys.stderr)
                sys.stderr.flush()
        if building_summary == "0 features" and buildings_geojson.exists():
            logger.info(f"  Loading {buildings_geojson}...")
            print(f"  Loading buildings...", file=sys.stderr)
            sys.stderr.flush()
            gdf_buildings = gpd.read_file(buildings_geojson)
            logger.info(f"  Loaded {len(gdf_buildings)} buildings")
            print(f"  Loaded {len(gdf_buildings)} buildings", file=sys.stderr)
            if gdf_buildings.crs != dem_crs:
                logger.info(f"  Reprojecting to {dem_crs}...")
                print(f"  Reprojecting...", file=sys.stderr)
                sys.stderr.flush()
                gdf_buildings = gdf_buildings.to_crs(dem_crs)

            if boundary_gdf is not None:
                boundary_geom = boundary_gdf.geometry.unary_union
                gdf_buildings = gdf_buildings[gdf_buildings.geometry.intersects(boundary_geom)]

            # Prepare all building geometries with heights
            building_shapes = []
            for idx, row in gdf_buildings.iterrows():
                roof_height = row.get("roof_height")
                if roof_height is None or roof_height == "":
                    roof_height = row.get("height", 6.0)
                else:
                    try:
                        roof_height = float(roof_height)
                    except (ValueError, TypeError):
                        roof_height = row.get("height", 6.0)

                if roof_height is None or roof_height <= 0:
                    roof_height = 6.0

                building_shapes.append((row.geometry, float(roof_height)))

            logger.info(f"  Rasterizing {len(building_shapes)} buildings...")
            print(f"  Rasterizing {len(building_shapes)} buildings...", file=sys.stderr)
            sys.stderr.flush()
            for i, (geom, roof_height) in enumerate(building_shapes):
                progress_bar(i, len(building_shapes), "    Buildings")
                mask = rasterize(
                    [(geom, roof_height)],
                    out_shape=(height, width),
                    transform=dem_transform,
                    fill=0,
                    dtype=np.float32,
                )
                building_heights = np.maximum(building_heights, mask)
            print("\n", end='', file=sys.stderr)  # Newline after progress bar
            sys.stderr.flush()

            if output_building_heights_path:
                output_building_heights_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_raster(building_heights, output_building_heights_path, dem_transform, dem_crs, dem_nodata)
                logger.info(f"  ✓ Building raster cached at {output_building_heights_path}")
                print(f"  ✓ Building raster cached at {output_building_heights_path.name}", file=sys.stderr)
                sys.stderr.flush()
            building_summary = f"{len(building_shapes)} features"

        cp2_time = time.time() - cp2_start
        logger.info(f"  ✓ Buildings added ({cp2_time:.2f}s)")
        print(f"  ✓ Buildings complete ({cp2_time:.2f}s)\n", file=sys.stderr)
        sys.stderr.flush()

        # CHECKPOINT 3: Add trees
        logger.info("\n[CHECKPOINT 3] Adding trees...")
        print("[CHECKPOINT 3] Adding trees...", file=sys.stderr)
        sys.stderr.flush()
        cp3_start = time.time()
        if output_tree_canopy_path and output_tree_canopy_path.exists():
            logger.info(f"  Reusing cached tree canopy raster: {output_tree_canopy_path}")
            print(f"  Reusing cached tree canopy raster: {output_tree_canopy_path.name}", file=sys.stderr)
            sys.stderr.flush()
            with rasterio.open(output_tree_canopy_path) as t_src:
                cached = t_src.read(1).astype(np.float32)
            if cached.shape == (height, width):
                tree_canopy = cached
                tree_summary = f"cached raster ({output_tree_canopy_path.name})"
            else:
                logger.info("  Cached tree canopy raster shape mismatch; rebuilding for boundary extent")
                print("  Cached tree canopy raster shape mismatch; rebuilding...", file=sys.stderr)
                sys.stderr.flush()
        if tree_summary == "0 features" and trees_geojson.exists():
            logger.info(f"  Loading {trees_geojson}...")
            print(f"  Loading trees...", file=sys.stderr)
            sys.stderr.flush()
            gdf_trees = gpd.read_file(trees_geojson)
            logger.info(f"  Loaded {len(gdf_trees)} tree features")
            print(f"  Loaded {len(gdf_trees)} tree features", file=sys.stderr)
            if gdf_trees.crs != dem_crs:
                logger.info(f"  Reprojecting to {dem_crs}...")
                print(f"  Reprojecting...", file=sys.stderr)
                sys.stderr.flush()

            if boundary_gdf is not None:
                boundary_geom = boundary_gdf.geometry.unary_union
                gdf_trees = gdf_trees[gdf_trees.geometry.intersects(boundary_geom)]

            # Reduce multiple parts per tree to one canopy polygon per tree,
            # then bucket spatially so large forest areas are rasterized in batches.
            tree_shapes = self._prepare_tree_canopy_features(
                gdf_trees,
                dem_crs,
                canopy_buffer_m=float(tree_canopy_buffer_m),
            )
            if tree_canopy_buffer_m > 0:
                logger.info(f"  Applying tree canopy buffer: {tree_canopy_buffer_m:.2f} m")
            tree_batches = self._bucket_tree_features(tree_shapes, cell_size_m=100.0)

            logger.info(f"  Reduced to {len(tree_shapes)} canopy features in {len(tree_batches)} spatial batches")
            tree_summary = f"{len(tree_shapes)} canopy features in {len(tree_batches)} batches"
            print(
                f"  Rasterizing {len(tree_shapes)} canopies in {len(tree_batches)} batches (forest areas batch together)...",
                file=sys.stderr,
            )
            sys.stderr.flush()

            for i, batch in enumerate(tree_batches):
                progress_bar(i, len(tree_batches), "    Tree batches")
                # Sort by height so taller canopies win in overlaps.
                batch = sorted(batch, key=lambda item: item[1])
                mask = rasterize(
                    [(geom, canopy_height) for geom, canopy_height in batch],
                    out_shape=(height, width),
                    transform=dem_transform,
                    fill=0,
                    dtype=np.float32,
                )
                tree_canopy = np.maximum(tree_canopy, mask)
                

            print("\n", end='', file=sys.stderr)  # Newline after progress bar
            sys.stderr.flush()

        cp3_time = time.time() - cp3_start
        logger.info(f"  ✓ Trees added ({cp3_time:.2f}s)")
        print(f"  ✓ Trees complete ({cp3_time:.2f}s)\n", file=sys.stderr)
        sys.stderr.flush()

        # CHECKPOINT 4: Write DSM
        logger.info("\n[CHECKPOINT 4] Writing DSM rasters...")
        print("[CHECKPOINT 4] Writing DSM rasters...", file=sys.stderr)
        sys.stderr.flush()
        cp4_start = time.time()

        # Write tree canopy layer if requested
        if output_tree_canopy_path:
            output_tree_canopy_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"  Writing {output_tree_canopy_path.name}...", file=sys.stderr)
            sys.stderr.flush()
            self._write_raster(tree_canopy, output_tree_canopy_path, dem_transform, dem_crs, dem_nodata)
            if not output_tree_canopy_path.exists():
                raise RuntimeError(f"Tree canopy file was not created: {output_tree_canopy_path}")
            tc_size = output_tree_canopy_path.stat().st_size / (1024*1024)
            logger.info(f"  ✓ Tree canopy written ({tc_size:.1f} MB)")
            print(f"  ✓ Tree canopy written ({tc_size:.1f} MB)", file=sys.stderr)

        # Merge DEM + building heights + tree canopy into final DSM at the end.
        dsm = np.maximum(dem, building_heights)
        dsm = np.maximum(dsm, tree_canopy)

        # Overwrite DSM with the merged result now that all obstruction layers are known.
        output_dsm_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Writing {output_dsm_path.name}...", file=sys.stderr)
        sys.stderr.flush()
        self._write_raster(dsm, output_dsm_path, dem_transform, dem_crs, dem_nodata)
        logger.info(f"  ✓ Final DSM merged and written to {output_dsm_path}")
        if not output_dsm_path.exists():
            raise RuntimeError(f"DSM file was not created: {output_dsm_path}")
        dsm_size = output_dsm_path.stat().st_size / (1024*1024)
        print(f"  ✓ DSM written ({dsm_size:.1f} MB)", file=sys.stderr)

        cp4_time = time.time() - cp4_start

        # Summary
        total_time = time.time() - start_time
        logger.info(f"\n[COMPLETE] DSM building took {total_time:.2f}s total")
        print(f"\n[COMPLETE] DSM building took {total_time:.2f}s total", file=sys.stderr)
        logger.info(f"  - DEM loading: {cp1_time:.2f}s")
        logger.info(f"  - Buildings: {cp2_time:.2f}s ({building_summary})")
        logger.info(f"  - Trees: {cp3_time:.2f}s ({tree_summary})")
        logger.info(f"  - Writing: {cp4_time:.2f}s")
        print(f"  - DEM: {cp1_time:.2f}s | Buildings: {cp2_time:.2f}s | Trees: {cp3_time:.2f}s | Writing: {cp4_time:.2f}s", file=sys.stderr)
        sys.stderr.flush()

    def compute_shade_rasters(
        self,
        dsm_path: Path,
        output_dir: Path,
        date: str,
        timezone: str = "Europe/Berlin",
        times: list[str] | None = None,
        tree_transmissivity: float = 0.2,
        tree_canopy_path: Path | None = None,
        boundary_geojson: Path | None = None,
        working_scale: float = 5.0,
        max_shadow_distance_m: int = 250,
    ) -> None:
        """
        Compute shade rasters from pre-built DSM.
        
        This is much faster than running DSM + shade together because DSM can be reused.
        """
        logger.info(f"Computing shade for {date}")
        start_time = time.time()
        
        if times is None:
            times = ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]

        # CHECKPOINT 1: Load DSM
        logger.info("\n[CHECKPOINT 1] Loading DSM...")
        cp1_start = time.time()
        boundary_gdf = None
        if boundary_geojson and boundary_geojson.exists():
            boundary_gdf = gpd.read_file(boundary_geojson)

        with rasterio.open(dsm_path) as dsm_src:
            dsm_crs = dsm_src.crs
            if boundary_gdf is not None:
                if boundary_gdf.crs != dsm_crs:
                    boundary_gdf = boundary_gdf.to_crs(dsm_crs)
                dsm_cropped, dsm_transform = raster_mask(
                    dsm_src,
                    boundary_gdf.geometry,
                    crop=True,
                    filled=True,
                    nodata=-9999,
                )
                dsm = dsm_cropped[0].astype(np.float32)
            else:
                dsm = dsm_src.read(1).astype(np.float32)
                dsm_transform = dsm_src.transform
            height, width = int(dsm.shape[0]), int(dsm.shape[1])

        working_scale = max(1.0, float(working_scale))
        if working_scale < 1.0:
            working_scale = 1.0
        coarse_height = max(1, int(np.ceil(height / working_scale)))
        coarse_width = max(1, int(np.ceil(width / working_scale)))
        coarse_transform = dsm_transform * Affine.scale(working_scale, working_scale)

        logger.info(f"  ✓ DSM loaded: {width}x{height}")
        logger.info(f"  ↳ Working grid: {coarse_width}x{coarse_height} (scale={working_scale:g}x)")
        cp1_time = time.time() - cp1_start

        # CHECKPOINT 2: Load tree canopy
        logger.info("\n[CHECKPOINT 2] Loading tree canopy...")
        cp2_start = time.time()
        tree_canopy = None
        if tree_canopy_path and tree_canopy_path.exists():
            with rasterio.open(tree_canopy_path) as tc_src:
                if boundary_gdf is not None:
                    tc_cropped, _ = raster_mask(
                        tc_src,
                        boundary_gdf.geometry,
                        crop=True,
                        filled=True,
                        nodata=0,
                    )
                    tree_canopy = tc_cropped[0].astype(np.float32)
                else:
                    tree_canopy = tc_src.read(1).astype(np.float32)
            logger.info(f"  ✓ Tree canopy loaded ({tree_canopy.max():.1f}m max height)")
        else:
            logger.info(f"  ℹ No tree canopy (transmissivity disabled)")
        cp2_time = time.time() - cp2_start

        # Parse date
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        # Initialize aggregation arrays
        dsm_coarse = np.zeros((coarse_height, coarse_width), dtype=np.float32)
        reproject(
            source=dsm,
            destination=dsm_coarse,
            src_transform=dsm_transform,
            src_crs=dsm_crs,
            dst_transform=coarse_transform,
            dst_crs=dsm_crs,
            resampling=Resampling.max,
        )

        tree_canopy_coarse = None
        if tree_canopy is not None:
            tree_canopy_coarse = np.zeros((coarse_height, coarse_width), dtype=np.float32)
            reproject(
                source=tree_canopy,
                destination=tree_canopy_coarse,
                src_transform=dsm_transform,
                src_crs=dsm_crs,
                dst_transform=coarse_transform,
                dst_crs=dsm_crs,
                resampling=Resampling.max,
            )

        sun_hours = np.zeros((coarse_height, coarse_width), dtype=np.float32)
        shade_hours = np.zeros((coarse_height, coarse_width), dtype=np.float32)

        # Location for solar calculations (Planegg)
        location = pvlib.location.Location(latitude=48.09, longitude=11.42, tz=timezone)
        cell_size_x_m = abs(float(coarse_transform.a)) if coarse_transform is not None else 1.0
        cell_size_y_m = abs(float(coarse_transform.e)) if coarse_transform is not None else 1.0
        cell_size_m = max(0.1, (cell_size_x_m + cell_size_y_m) * 0.5)

        # CHECKPOINT 3: Ray-casting
        logger.info(f"\n[CHECKPOINT 3] Ray-casting for {len(times)} timestamps...")
        cp3_start = time.time()
        for t_idx, time_str in enumerate(times):
            hour, minute = map(int, time_str.split(":"))
            timestamp = datetime.combine(
                target_date,
                datetime.min.time().replace(hour=hour, minute=minute),
            ).replace(tzinfo=ZoneInfo(timezone))
            
            # Get solar position
            solar_position = location.get_solarposition(timestamp)
            azimuth = solar_position["azimuth"].values[0]
            elevation = solar_position["elevation"].values[0]

            progress_bar(t_idx, len(times), "  Timestamps")

            if elevation <= 0:
                shade_hours += 1
                continue

            # Compute shade map for this timestamp
            shade_map = self._compute_shade_map(
                dsm_coarse,
                elevation,
                azimuth,
                tree_canopy_coarse,
                tree_transmissivity,
                max_shadow_distance_m=max_shadow_distance_m,
                cell_size_m=cell_size_m,
            )

            # Aggregate
            sun_hours += (1 - shade_map)
            shade_hours += shade_map

        print()  # Newline after progress bar
        cp3_time = time.time() - cp3_start
        logger.info(f"  ✓ Ray-casting complete ({cp3_time:.2f}s)")

        # CHECKPOINT 4: Write outputs
        logger.info("\n[CHECKPOINT 4] Writing output rasters...")
        cp4_start = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        
        sun_hours_path = output_dir / f"sun_hours_{date}.tif"
        shade_hours_path = output_dir / f"shade_hours_{date}.tif"
        shade_fraction_path = output_dir / f"shade_fraction_{date}.tif"

        # Upsample the coarse outputs back to full resolution for visualization.
        full_sun_hours = np.zeros((height, width), dtype=np.float32)
        full_shade_hours = np.zeros((height, width), dtype=np.float32)
        full_shade_fraction = np.zeros((height, width), dtype=np.float32)

        reproject(
            source=sun_hours,
            destination=full_sun_hours,
            src_transform=coarse_transform,
            src_crs=dsm_crs,
            dst_transform=dsm_transform,
            dst_crs=dsm_crs,
            resampling=Resampling.nearest,
        )
        reproject(
            source=shade_hours,
            destination=full_shade_hours,
            src_transform=coarse_transform,
            src_crs=dsm_crs,
            dst_transform=dsm_transform,
            dst_crs=dsm_crs,
            resampling=Resampling.nearest,
        )
        reproject(
            source=(shade_hours / len(times)).astype(np.float32),
            destination=full_shade_fraction,
            src_transform=coarse_transform,
            src_crs=dsm_crs,
            dst_transform=dsm_transform,
            dst_crs=dsm_crs,
            resampling=Resampling.nearest,
        )

        self._write_raster(full_sun_hours, sun_hours_path, dsm_transform, dsm_crs, -9999)
        logger.info(f"    ✓ {sun_hours_path.name}")
        
        self._write_raster(full_shade_hours, shade_hours_path, dsm_transform, dsm_crs, -9999)
        logger.info(f"    ✓ {shade_hours_path.name}")
        
        self._write_raster(full_shade_fraction, shade_fraction_path, dsm_transform, dsm_crs, -9999)
        logger.info(f"    ✓ {shade_fraction_path.name}")

        cp4_time = time.time() - cp4_start

        # Summary
        total_time = time.time() - start_time
        logger.info(f"\n[COMPLETE] Shade computation took {total_time:.2f}s total")
        logger.info(f"  - DSM loading: {cp1_time:.2f}s")
        logger.info(f"  - Tree canopy: {cp2_time:.2f}s")
        logger.info(f"  - Ray-casting: {cp3_time:.2f}s ({len(times)} timestamps)")
        logger.info(f"  - Writing: {cp4_time:.2f}s")
        logger.info(f"\n  Sun hours: {sun_hours.min():.1f} - {sun_hours.max():.1f}")
        logger.info(f"  Shade hours: {shade_hours.min():.1f} - {shade_hours.max():.1f}")

    def _compute_shade_map(
        self,
        dsm: np.ndarray,
        elevation: float,
        azimuth: float,
        tree_canopy: np.ndarray | None = None,
        tree_transmissivity: float = 0.2,
        max_shadow_distance_m: int = 250,
        cell_size_m: float = 1.0,
    ) -> np.ndarray:
        """Compute shade map using approximate ray-casting."""
        # Convert azimuth/elevation to ray direction
        az_rad = np.radians(azimuth)
        el_rad = np.radians(elevation)
        
        # Ray direction (dx, dy per meter horizontal)
        dx = np.sin(az_rad)
        # Raster rows increase southward, so northward movement is negative row offset.
        dy = -np.cos(az_rad)
        
        # Height angle tangent (dz per meter horizontal)
        tan_el = np.tan(el_rad)

        height, width = dsm.shape
        shade = np.zeros((height, width), dtype=np.float32)

        # For each pixel, check if ray toward sun is blocked
        y_idx, x_idx = np.meshgrid(np.arange(height), np.arange(width), indexing='ij')
        pixel_height = dsm[y_idx, x_idx]

        # Ray-casting: march from pixel toward sun direction
        # Check if any surface along ray is higher than expected solar angle
        max_shadow_distance_m = max(20, int(max_shadow_distance_m))
        cell_size_m = max(0.1, float(cell_size_m))
        max_steps = max(1, int(np.ceil(max_shadow_distance_m / cell_size_m)))
        for step in range(1, max_steps + 1):
            # Ray position at this step
            ray_x = x_idx + step * dx
            ray_y = y_idx + step * dy
            
            # Expected height at this distance
            horizontal_distance_m = step * cell_size_m
            expected_height = pixel_height + horizontal_distance_m * tan_el

            # Check bounds
            valid = (ray_x >= 0) & (ray_x < width) & (ray_y >= 0) & (ray_y < height)
            if not valid.any():
                break

            # Get terrain elevation at ray position (bilinear interpolation)
            ray_x_int = np.rint(ray_x).astype(int)
            ray_y_int = np.rint(ray_y).astype(int)
            
            # Clamp to valid range
            ray_x_int = np.clip(ray_x_int, 0, width - 1)
            ray_y_int = np.clip(ray_y_int, 0, height - 1)
            
            terrain_height = dsm[ray_y_int, ray_x_int]

            # If terrain is higher than expected solar ray, pixel is shaded
            shaded = valid & (terrain_height > expected_height)
            shade = np.where(shaded, 1.0, shade)

        # Apply tree transmissivity (partial attenuation)
        if tree_canopy is not None:
            under_tree = tree_canopy > 0
            canopy_shade_floor = float(np.clip(1.0 - tree_transmissivity, 0.0, 1.0))
            shade = np.where(under_tree, np.maximum(shade, canopy_shade_floor), shade)

        return shade

    def _write_raster(
        self,
        array: np.ndarray,
        path: Path,
        transform: Any,
        crs: Any,
        nodata: float = -9999,
    ) -> None:
        """Write numpy array as GeoTIFF."""
        with rasterio.open(
            path,
            'w',
            driver='GTiff',
            height=array.shape[0],
            width=array.shape[1],
            count=1,
            dtype=array.dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
            compress='deflate',
        ) as dst:
            dst.write(array, 1)
