"""
Shade modelling service for computing solar exposure and shadow casting.

## Modelling approach

This service computes shade and sun exposure layers by:

1. **Surface Model (DSM)**: Combines DEM (terrain) + building heights + tree canopy heights
   into a single obstruction surface at 1m resolution.

2. **Solar Position**: Uses pvlib to compute sun position (azimuth, elevation) for each
   timestamp in the simulation period.

3. **Shadow Casting**: For each timestamp, ray-casts from each pixel towards the sun
   direction. If the ray hits a higher surface, the pixel is shaded; otherwise sunlit.

4. **Tree Transmissivity**: Tree canopies are modelled as semi-transparent. Instead of
   being fully opaque, a fraction of direct sunlight passes through (e.g., 20%).
   This is applied separately from buildings, which are treated as fully opaque.

5. **Aggregation**: Results from multiple timestamps are combined into:
   - Daily sun hours: count of sunlit timesteps per day
   - Daily shade hours: count of shaded timesteps per day
   - Single-time shade fraction: shade state at a specific time (e.g., Landsat overpass)

## Inputs

- `dem_path`: Path to 1m DEM GeoTIFF (terrain elevation)
- `buildings_geojson`: Path to buildings vector with `roof_height` property
- `trees_geojson`: Path to trees vector with `height`, `base_height`, `canopy_base` properties
- `date`: Target date (e.g., 2023-07-21 for summer reference day)
- `timezone`: Local timezone for sun calculations (e.g., 'Europe/Berlin')
- `times`: List of times to simulate (e.g., hourly 10:00-18:00)
- `tree_transmissivity`: Fraction of direct sunlight passing through tree canopy (0-1, default 0.2)

## Outputs

- `sun_hours_daily`: GeoTIFF with count of sunlit hours
- `shade_hours_daily`: GeoTIFF with count of shaded hours
- `shade_overpass_{timestamp}`: GeoTIFF with shade state at specific time (0=sunlit, 1=shaded)

## Limitations

- Trees modelled as point-buffered circular canopies; actual crowns are more complex
- Building footprints used; roof slope/azimuth not modelled
- Transmissivity is uniform; no LAI or species-specific variation in phase 1
- Ray-casting is approximate; not a full radiosity or BRF model
- No atmospheric scattering; direct sun only
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from shapely.geometry import Point, Polygon, shape
import geopandas as gpd

try:
    import pvlib
except ImportError:
    pvlib = None

logger = logging.getLogger(__name__)


class ShadeService:
    """Compute shade and sun exposure rasters from DEM, buildings, and trees."""

    def __init__(self):
        if pvlib is None:
            raise RuntimeError("pvlib is required for shade modelling. Install with: pip install pvlib")

    def build_dsm_with_obstruction_layers(
        self,
        dem_path: Path,
        buildings_geojson: Path,
        trees_geojson: Path,
        output_dsm_path: Path,
        output_tree_canopy_path: Path | None = None,
    ) -> None:
        """
        Build a Digital Surface Model (DSM) by combining:
        - DEM (ground elevation)
        - Building roof heights
        - Tree canopy heights (stored separately for transmissivity modelling)

        Args:
            dem_path: Path to 1m DEM GeoTIFF
            buildings_geojson: Path to buildings vector
            trees_geojson: Path to trees vector
            output_dsm_path: Path to write combined DSM GeoTIFF
            output_tree_canopy_path: Optional path to write tree-only canopy heights
        """
        logger.info("Building DSM from DEM, buildings, and trees...")

        # Load DEM as base
        with rasterio.open(dem_path) as dem_src:
            dem = dem_src.read(1).astype(np.float32)
            dem_transform = dem_src.transform
            dem_crs = dem_src.crs
            dem_nodata = dem_src.nodata
            height, width = int(dem.shape[0]), int(dem.shape[1])

        logger.info(f"DEM loaded: {width}x{height}, CRS={dem_crs}")

        dsm = dem.copy()
        tree_canopy = np.zeros_like(dem)

        # Add buildings
        if buildings_geojson.exists():
            logger.info(f"Adding buildings from {buildings_geojson}")
            gdf_buildings = gpd.read_file(buildings_geojson)
            if gdf_buildings.crs != dem_crs:
                gdf_buildings = gdf_buildings.to_crs(dem_crs)

            for idx, row in gdf_buildings.iterrows():
                roof_height = row.get("roof_height")
                if roof_height is None or (isinstance(roof_height, str) and roof_height == ""):
                    roof_height = row.get("height", 6.0)
                else:
                    try:
                        roof_height = float(roof_height)
                    except (ValueError, TypeError):
                        roof_height = row.get("height", 6.0)

                if roof_height is None or roof_height <= 0:
                    roof_height = 6.0

                geom = row.geometry
                building_mask = rasterize(
                    [(geom, 1)],
                    out_shape=(height, width),
                    transform=dem_transform,
                    fill=0,
                    dtype=np.uint8,
                )
                dsm = np.where(building_mask > 0, np.maximum(dsm, roof_height), dsm)

            logger.info(f"Added {len(gdf_buildings)} buildings to DSM")

        # Add trees (separately for transmissivity)
        if trees_geojson.exists():
            logger.info(f"Adding trees from {trees_geojson}")
            gdf_trees = gpd.read_file(trees_geojson)
            if gdf_trees.crs != dem_crs:
                gdf_trees = gdf_trees.to_crs(dem_crs)

            # Only process canopy polygons/shells, not point features
            tree_features = []
            for idx, row in gdf_trees.iterrows():
                tree_part = row.get("tree_part", "")
                if tree_part == "point":
                    continue  # Skip point markers

                tree_height = row.get("height")
                canopy_base = row.get("canopy_base", 1.5)
                canopy_shell_top = row.get("canopy_shell_top")

                if tree_height is None or tree_height <= 0:
                    tree_height = 12.0
                if canopy_shell_top is None or canopy_shell_top <= 0:
                    canopy_shell_top = tree_height

                tree_features.append((row.geometry, canopy_shell_top))

            for geom, canopy_height in tree_features:
                mask = rasterize(
                    [(geom, 1)],
                    out_shape=(height, width),
                    transform=dem_transform,
                    fill=0,
                    dtype=np.uint8,
                )
                tree_canopy = np.where(mask > 0, np.maximum(tree_canopy, canopy_height), tree_canopy)
                dsm = np.where(mask > 0, np.maximum(dsm, canopy_height), dsm)

            logger.info(f"Added tree canopies to DSM")

        # Write DSM
        output_dsm_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            output_dsm_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=np.float32,
            transform=dem_transform,
            crs=dem_crs,
            nodata=dem_nodata if dem_nodata is not None else 0.0,
        ) as dst:
            dst.write(dsm, 1)
            logger.info(f"DSM written to {output_dsm_path}")

        # Optionally write tree-only canopy layer
        if output_tree_canopy_path:
            output_tree_canopy_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(
                output_tree_canopy_path,
                "w",
                driver="GTiff",
                height=height,
                width=width,
                count=1,
                dtype=np.float32,
                transform=dem_transform,
                crs=dem_crs,
                nodata=0.0,
            ) as dst:
                dst.write(tree_canopy, 1)
                logger.info(f"Tree canopy layer written to {output_tree_canopy_path}")

    def compute_shade_rasters(
        self,
        dem_path: Path,
        dsm_path: Path,
        tree_canopy_path: Path | None,
        output_dir: Path,
        date: str = "2023-07-21",
        timezone: str = "Europe/Berlin",
        times: list[str] | None = None,
        tree_transmissivity: float = 0.2,
    ) -> dict[str, Path]:
        """
        Compute shade and sun hour rasters for a given date.

        Args:
            dem_path: Path to DEM GeoTIFF
            dsm_path: Path to DSM GeoTIFF
            tree_canopy_path: Optional path to tree-only canopy layer
            output_dir: Directory to write output rasters
            date: Date string (YYYY-MM-DD)
            timezone: Timezone for solar calculations
            times: List of time strings (HH:MM) to simulate. Default: hourly 10:00-18:00
            tree_transmissivity: Fraction of direct sun passing through tree (0-1)

        Returns:
            Dict mapping output names to paths
        """
        if times is None:
            times = [f"{h:02d}:00" for h in range(10, 19)]  # 10:00 to 18:00

        logger.info(f"Computing shade rasters for {date}, timezone={timezone}")
        logger.info(f"Simulation times: {', '.join(times)}")
        logger.info(f"Tree transmissivity: {tree_transmissivity}")

        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = {}

        # Load DSM and tree canopy
        with rasterio.open(dsm_path) as dsm_src:
            dsm = dsm_src.read(1).astype(np.float32)
            dsm_transform = dsm_src.transform
            dsm_crs = dsm_src.crs
            dsm_nodata = dsm_src.nodata

        tree_canopy = None
        if tree_canopy_path and tree_canopy_path.exists():
            with rasterio.open(tree_canopy_path) as tree_src:
                tree_canopy = tree_src.read(1).astype(np.float32)

        height, width = dsm.shape
        logger.info(f"DSM shape: {width}x{height}")

        # Initialize accumulators
        sun_hours = np.zeros((height, width), dtype=np.uint16)
        shade_hours = np.zeros((height, width), dtype=np.uint16)
        first_shade_map = None

        # Process each time
        for time_idx, time_str in enumerate(times):
            hour, minute = map(int, time_str.split(":"))
            datetime_obj = datetime.strptime(f"{date} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")

            # Calculate sun position
            location = pvlib.location.Location(latitude=48.09, longitude=11.42, tz=timezone)
            solar_position = location.get_solarposition(datetime_obj)
            azimuth = float(solar_position["azimuth"].iloc[0])
            elevation = float(solar_position["elevation"].iloc[0])

            logger.info(f"  {time_str}: azimuth={azimuth:.1f}°, elevation={elevation:.1f}°")

            if elevation <= 0:
                logger.info(f"    Sun below horizon, all pixels shaded")
                shade_hours += 1
                continue

            # Compute shade map for this timestamp
            shade_map = self._compute_shade_map(
                dsm,
                tree_canopy,
                azimuth,
                elevation,
                tree_transmissivity,
            )

            # Accumulate
            sun_hours += (shade_map == 0).astype(np.uint16)
            shade_hours += (shade_map > 0).astype(np.uint16)

            # Save first shade map for overpass-time output
            if first_shade_map is None:
                first_shade_map = shade_map.copy()

        # Write sun hours
        sun_hours_path = output_dir / f"sun_hours_{date}.tif"
        self._write_raster(sun_hours, dsm_transform, dsm_crs, sun_hours_path)
        outputs["sun_hours"] = sun_hours_path

        # Write shade hours
        shade_hours_path = output_dir / f"shade_hours_{date}.tif"
        self._write_raster(shade_hours, dsm_transform, dsm_crs, shade_hours_path)
        outputs["shade_hours"] = shade_hours_path

        # Write shade percentage
        shade_pct = np.zeros_like(shade_hours, dtype=np.uint8)
        total_times = len(times)
        if total_times > 0:
            shade_pct = (shade_hours * 100 // total_times).astype(np.uint8)
        shade_pct_path = output_dir / f"shade_fraction_{date}.tif"
        self._write_raster(shade_pct, dsm_transform, dsm_crs, shade_pct_path)
        outputs["shade_fraction"] = shade_pct_path

        # Write first overpass shade map
        if first_shade_map is not None:
            overpass_path = output_dir / f"shade_overpass_{date}_{times[0].replace(':', '')}.tif"
            self._write_raster(first_shade_map, dsm_transform, dsm_crs, overpass_path)
            outputs["shade_overpass"] = overpass_path

        logger.info(f"Shade computation complete. Output rasters:")
        for name, path in outputs.items():
            logger.info(f"  {name}: {path}")

        return outputs

    def _compute_shade_map(
        self,
        dsm: np.ndarray,
        tree_canopy: np.ndarray | None,
        azimuth: float,
        elevation: float,
        tree_transmissivity: float,
    ) -> np.ndarray:
        """
        Compute shade map for a single timestamp.

        For each pixel, check if a ray towards the sun hits a higher surface.
        If tree canopy is present, apply transmissivity attenuation.

        Returns:
            Array where 0 = sunlit, 1 = shaded by opaque object,
            0 < value < 1 = partial shade through trees
        """
        height, width = dsm.shape
        shade_map = np.zeros_like(dsm, dtype=np.float32)

        # Convert azimuth and elevation to radians
        az_rad = np.radians(azimuth)
        el_rad = np.radians(elevation)

        # Direction vector for sun ray (normalized)
        # Azimuth is measured clockwise from north; convert to standard math angles
        dx = np.sin(az_rad)
        dy = np.cos(az_rad)

        # For each pixel, march a ray towards the sun and check obstruction
        for y in range(height):
            for x in range(width):
                z0 = dsm[y, x]
                if not np.isfinite(z0) or z0 < -1000:
                    continue  # Skip invalid pixels

                # Check if any point along the ray is higher than expected at z0
                shaded = False
                tree_shaded = False

                # Ray march: step from pixel towards sun direction
                # Distance along ray needed for ray to clear horizon
                tan_elevation = np.tan(el_rad)

                # Sample points along the ray
                max_dist = max(height, width) * 2  # Ray length
                step_size = 1.0  # Sample every 1m

                for dist in np.arange(step_size, max_dist, step_size):
                    # Projected position along ray
                    px = x + dx * dist
                    py = y + dy * dist

                    # Check bounds
                    if px < 0 or px >= width or py < 0 or py >= height:
                        break

                    px_int, py_int = int(px), int(py)
                    if px_int < 0 or px_int >= width or py_int < 0 or py_int >= height:
                        break

                    z_sample = dsm[py_int, px_int]
                    if not np.isfinite(z_sample) or z_sample < -1000:
                        continue

                    # Height that ray reaches at this distance
                    ray_z = z0 + dist * tan_elevation

                    if z_sample > ray_z:
                        # Ray is blocked
                        # Check if block is from tree or opaque building
                        is_tree_only = False
                        if tree_canopy is not None:
                            tree_z = tree_canopy[py_int, px_int]
                            if tree_z > 0 and z_sample - tree_z < 0.1:  # Mostly tree, not building
                                is_tree_only = True

                        if is_tree_only:
                            tree_shaded = True
                        else:
                            shaded = True
                            break

                # Apply transmissivity
                if shaded:
                    shade_map[y, x] = 1.0
                elif tree_shaded:
                    shade_map[y, x] = 1.0 - tree_transmissivity
                # else: stays 0.0 (sunlit)

        return shade_map

    @staticmethod
    def _write_raster(
        data: np.ndarray,
        transform,
        crs,
        output_path: Path,
    ) -> None:
        """Write a raster array to GeoTIFF."""
        height, width = data.shape
        dtype = data.dtype

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            output_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=dtype,
            transform=transform,
            crs=crs,
            nodata=0,
        ) as dst:
            dst.write(data, 1)
