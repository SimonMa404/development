"""Extract the Planegg municipality boundary from the VG250 (BKG) geopackage.

This is a one-off extraction script: it reads the official German
administrative-boundary dataset (VG250, Gemeinde level), isolates the
Planegg polygon, and writes two permanent, lightweight GeoJSON outputs:

- storage/vectors/processed/planegg/boundary.geojson
    The exact municipal boundary polygon (EPSG:4326).
- storage/vectors/processed/planegg/boundary_buffered.geojson
    The same polygon buffered by BUFFER_METERS (computed in the
    projected CRS EPSG:25832, then reprojected to EPSG:4326). Used as
    the region-of-interest for raster exports so derived layers extend
    slightly beyond the municipal edge for visual context.

The source geopackage (data/boundaries/vg250/...) is large and is not
tracked in git (see .gitignore) - re-download it from
https://gdz.bkg.bund.de if needed. This script only needs to be run
once; its outputs are the durable artifacts used by the rest of the
pipeline.

Usage:
    python scripts/extract_planegg_boundary.py [--buffer-meters 500] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

pd.set_option("future.infer_string", False)

REPO_ROOT = Path(__file__).resolve().parents[1]
GPKG_PATH = REPO_ROOT / "data" / "boundaries" / "vg250" / "vg250_ebenen_0101" / "DE_VG250.gpkg"
GEM_LAYER = "vg250_gem"
OUTPUT_DIR = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg"

MUNICIPALITY_NAME = "Planegg"
DEFAULT_BUFFER_METERS = 500
PROJECTED_CRS = "EPSG:25832"
OUTPUT_CRS = "EPSG:4326"


def load_planegg(gpkg_path: Path) -> gpd.GeoDataFrame:
    if not gpkg_path.exists():
        raise FileNotFoundError(
            f"VG250 geopackage not found at {gpkg_path}. "
            "Download it from https://gdz.bkg.bund.de and place it there."
        )

    gdf = gpd.read_file(gpkg_path, layer=GEM_LAYER)
    match = gdf[gdf["GEN"].str.contains(MUNICIPALITY_NAME, case=False, na=False)]

    if match.empty:
        raise ValueError(f"No municipality matching '{MUNICIPALITY_NAME}' found in {GEM_LAYER}.")
    if len(match) > 1:
        print("Multiple matches found, attributes:", file=sys.stderr)
        print(match[["GEN", "BEZ", "ARS", "AGS", "NUTS"]].to_string(), file=sys.stderr)
        raise ValueError(
            f"Ambiguous match for '{MUNICIPALITY_NAME}' ({len(match)} rows). "
            "Refine the filter (e.g. by ARS/AGS) before proceeding."
        )

    row = match.iloc[0]
    print(f"Matched: GEN={row['GEN']!r} BEZ={row['BEZ']!r} ARS={row['ARS']!r} AGS={row['AGS']!r} NUTS={row['NUTS']!r}")
    return match


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buffer-meters", type=float, default=DEFAULT_BUFFER_METERS)
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs.")
    args = parser.parse_args()

    boundary_path = OUTPUT_DIR / "boundary.geojson"
    buffered_path = OUTPUT_DIR / "boundary_buffered.geojson"

    if boundary_path.exists() and buffered_path.exists() and not args.force:
        print(f"Outputs already exist at {OUTPUT_DIR} (use --force to regenerate). Skipping.")
        return

    match = load_planegg(GPKG_PATH)

    # Ensure we are working in the projected CRS for accurate area/buffer math.
    match_projected = match.to_crs(PROJECTED_CRS)
    exact_geom = match_projected.geometry.iloc[0]
    buffered_geom = exact_geom.buffer(args.buffer_meters)

    exact_gdf = gpd.GeoDataFrame(
        {"name": [MUNICIPALITY_NAME], "ags": [str(match.iloc[0]["AGS"])], "source": ["BKG VG250"]},
        geometry=[exact_geom],
        crs=PROJECTED_CRS,
    ).to_crs(OUTPUT_CRS)

    buffered_gdf = gpd.GeoDataFrame(
        {
            "name": [f"{MUNICIPALITY_NAME} (buffered {args.buffer_meters:.0f}m)"],
            "ags": [str(match.iloc[0]["AGS"])],
            "buffer_meters": [float(args.buffer_meters)],
            "source": ["BKG VG250"],
        },
        geometry=[buffered_geom],
        crs=PROJECTED_CRS,
    ).to_crs(OUTPUT_CRS)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    exact_gdf.to_file(boundary_path, driver="GeoJSON")
    buffered_gdf.to_file(buffered_path, driver="GeoJSON")

    exact_bounds = exact_gdf.total_bounds
    buffered_bounds = buffered_gdf.total_bounds

    print(f"Wrote {boundary_path}")
    print(f"  bounds (lon/lat): {exact_bounds.tolist()}")
    print(f"Wrote {buffered_path} (buffer={args.buffer_meters}m)")
    print(f"  bounds (lon/lat): {buffered_bounds.tolist()}")


if __name__ == "__main__":
    main()
