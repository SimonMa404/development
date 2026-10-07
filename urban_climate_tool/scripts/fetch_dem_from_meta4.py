"""Download 1m DEM raster tiles from a .meta4 file, validate checksums, mosaic,
and clip to the Planegg buffered ROI.

Expected output:
    storage/rasters/processed/planegg/dem_1m.tif

Usage:
    python scripts/fetch_dem_from_meta4.py --meta4 "09184138 (1).meta4"
    python scripts/fetch_dem_from_meta4.py --meta4 path/to/dem.meta4 --force
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge

from meta4_importer import download_entries, filter_entries_by_extension, parse_meta4

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "storage" / "rasters" / "source" / "dem_1m"
PROCESSED_DIR = REPO_ROOT / "storage" / "rasters" / "processed" / "planegg"
OUTPUT_PATH = PROCESSED_DIR / "dem_1m.tif"
BOUNDARY_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"

def build_dem_mosaic_clipped(tile_paths: list[Path], output_path: Path) -> None:
    if not BOUNDARY_PATH.exists():
        raise FileNotFoundError(f"Boundary file not found: {BOUNDARY_PATH}")

    boundary = gpd.read_file(BOUNDARY_PATH)
    srcs = [rasterio.open(path) for path in tile_paths]
    try:
        if not srcs:
            raise RuntimeError("No DEM source rasters available for mosaicking.")

        boundary_projected = boundary.to_crs(srcs[0].crs)
        mosaic, transform = merge(srcs)

        meta = srcs[0].meta.copy()
        meta.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": transform,
                "compress": "lzw",
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
                "count": 1,
            }
        )

        temp_mosaic = output_path.with_suffix(".mosaic_tmp.tif")
        with rasterio.open(temp_mosaic, "w", **meta) as dst:
            dst.write(mosaic)

        with rasterio.open(temp_mosaic) as src:
            clipped, clipped_transform = mask(src, boundary_projected.geometry, crop=True)
            clipped_meta = src.meta.copy()
            clipped_meta.update(
                {
                    "height": clipped.shape[1],
                    "width": clipped.shape[2],
                    "transform": clipped_transform,
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **clipped_meta) as dst:
            dst.write(clipped)

        temp_mosaic.unlink(missing_ok=True)
        print(f"[ok] wrote DEM: {output_path}")
    finally:
        for src in srcs:
            src.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta4", required=True, help="Path to DEM .meta4 file")
    parser.add_argument("--force", action="store_true", help="Re-download even if local file validates")
    parser.add_argument(
        "--accept-ext",
        default=".tif,.tiff",
        help="Comma-separated extensions to download/process (default: .tif,.tiff)",
    )
    args = parser.parse_args()

    meta4_path = Path(args.meta4)
    if not meta4_path.is_absolute():
        meta4_path = (REPO_ROOT / meta4_path).resolve()

    if not meta4_path.exists():
        raise SystemExit(f"Meta4 file not found: {meta4_path}")

    accepted_ext = tuple(ext.strip().lower() for ext in args.accept_ext.split(",") if ext.strip())

    entries = parse_meta4(meta4_path)
    if not entries:
        raise SystemExit("No downloadable files found in meta4.")

    dem_entries = filter_entries_by_extension(entries, accepted_ext)
    if not dem_entries:
        sample = ", ".join(str(e["name"]) for e in entries[:5])
        raise SystemExit(
            "No DEM raster tiles matched accepted extensions "
            f"{accepted_ext}. First entries are: {sample}"
        )

    downloaded = download_entries(dem_entries, dest_dir=RAW_DIR, force=args.force)

    # Ensure only raster files are used in mosaic.
    raster_files = [p for p in downloaded if p.suffix.lower() in {".tif", ".tiff"}]
    if not raster_files:
        names = ", ".join(p.name for p in downloaded)
        raise SystemExit(f"Downloaded files are not GeoTIFF rasters: {names}")

    build_dem_mosaic_clipped(raster_files, OUTPUT_PATH)


if __name__ == "__main__":
    main()
