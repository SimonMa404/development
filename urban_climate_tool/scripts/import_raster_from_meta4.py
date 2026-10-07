"""Generic importer for raster tile deliveries distributed via .meta4 files.

Workflow:
1) Parse .meta4 entries
2) Download and checksum-validate files
3) Mosaic GeoTIFF tiles
4) Clip to Planegg buffered ROI

Usage examples:
  python scripts/import_raster_from_meta4.py \
    --meta4 "data/09184138 (4).meta4" \
    --raw-subdir dom_20cm \
    --output storage/rasters/processed/planegg/dom_20cm.tif

  python scripts/import_raster_from_meta4.py \
    --meta4 "data/09184138_RGB20cm.meta4" \
    --raw-subdir rgb_20cm \
    --output storage/rasters/processed/planegg/rgb_20cm.tif
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge

from meta4_importer import download_entries, filter_entries_by_extension, parse_meta4

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOUNDARY = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"


def build_mosaic_clipped(tile_paths: list[Path], output_path: Path, boundary_path: Path) -> None:
    if shutil.which("gdalbuildvrt") and shutil.which("gdalwarp"):
        _build_mosaic_clipped_gdal(tile_paths, output_path=output_path, boundary_path=boundary_path)
        return

    _build_mosaic_clipped_rasterio(tile_paths, output_path=output_path, boundary_path=boundary_path)


def _build_mosaic_clipped_gdal(tile_paths: list[Path], output_path: Path, boundary_path: Path) -> None:
    if not boundary_path.exists():
        raise FileNotFoundError(f"Boundary file not found: {boundary_path}")
    if not tile_paths:
        raise RuntimeError("No source rasters available for mosaicking.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(prefix="meta4_mosaic_", suffix=".vrt", delete=False) as tmp_vrt:
        vrt_path = Path(tmp_vrt.name)

    try:
        subprocess.run(
            ["gdalbuildvrt", str(vrt_path), *[str(path) for path in tile_paths]],
            check=True,
        )
        subprocess.run(
            [
                "gdalwarp",
                "-of",
                "GTiff",
                "-co",
                "COMPRESS=LZW",
                "-co",
                "TILED=YES",
                "-co",
                "BIGTIFF=IF_SAFER",
                "-cutline",
                str(boundary_path),
                "-crop_to_cutline",
                str(vrt_path),
                str(output_path),
            ],
            check=True,
        )
        print(f"[ok] wrote raster: {output_path}")
    finally:
        vrt_path.unlink(missing_ok=True)


def _build_mosaic_clipped_rasterio(tile_paths: list[Path], output_path: Path, boundary_path: Path) -> None:
    if not boundary_path.exists():
        raise FileNotFoundError(f"Boundary file not found: {boundary_path}")

    boundary = gpd.read_file(boundary_path)
    srcs = [rasterio.open(path) for path in tile_paths]
    try:
        if not srcs:
            raise RuntimeError("No source rasters available for mosaicking.")

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
                "count": mosaic.shape[0],
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
                    "count": clipped.shape[0],
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_path, "w", **clipped_meta) as dst:
            dst.write(clipped)

        temp_mosaic.unlink(missing_ok=True)
        print(f"[ok] wrote raster: {output_path}")
    finally:
        for src in srcs:
            src.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta4", required=True, help="Path to .meta4 file")
    parser.add_argument("--raw-subdir", required=True, help="Subdirectory under storage/rasters/source for raw downloads")
    parser.add_argument("--output", required=True, help="Output GeoTIFF path (relative to repo root or absolute)")
    parser.add_argument("--boundary", default=str(DEFAULT_BOUNDARY), help="Boundary GeoJSON for clipping")
    parser.add_argument("--force", action="store_true", help="Re-download even if checksum-valid files exist")
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

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (REPO_ROOT / output_path).resolve()

    boundary_path = Path(args.boundary)
    if not boundary_path.is_absolute():
        boundary_path = (REPO_ROOT / boundary_path).resolve()

    accepted_ext = tuple(ext.strip().lower() for ext in args.accept_ext.split(",") if ext.strip())

    entries = parse_meta4(meta4_path)
    if not entries:
        raise SystemExit("No downloadable files found in meta4.")

    raster_entries = filter_entries_by_extension(entries, accepted_ext)
    if not raster_entries:
        sample = ", ".join(str(entry["name"]) for entry in entries[:5])
        raise SystemExit(
            "No raster files matched accepted extensions "
            f"{accepted_ext}. First entries are: {sample}"
        )

    raw_dir = REPO_ROOT / "storage" / "rasters" / "source" / args.raw_subdir
    downloaded = download_entries(raster_entries, dest_dir=raw_dir, force=args.force)

    raster_files = [path for path in downloaded if path.suffix.lower() in {".tif", ".tiff"}]
    if not raster_files:
        names = ", ".join(path.name for path in downloaded)
        raise SystemExit(f"Downloaded files are not GeoTIFF rasters: {names}")

    build_mosaic_clipped(raster_files, output_path=output_path, boundary_path=boundary_path)


if __name__ == "__main__":
    main()
