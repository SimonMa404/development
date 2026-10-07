"""Import RGB 20cm raster from a meta4 delivery into processed storage.

Usage:
  python scripts/fetch_rgb_from_meta4.py --meta4 "data/09184138_RGB20cm.meta4"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from import_raster_from_meta4 import REPO_ROOT, build_mosaic_clipped
from meta4_importer import download_entries, filter_entries_by_extension, parse_meta4

RAW_DIR = REPO_ROOT / "storage" / "rasters" / "source" / "rgb_20cm"
OUTPUT_PATH = REPO_ROOT / "storage" / "rasters" / "processed" / "planegg" / "rgb_20cm.tif"
BOUNDARY_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta4", required=True, help="Path to RGB .meta4 file")
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

    rgb_entries = filter_entries_by_extension(entries, accepted_ext)
    if not rgb_entries:
        sample = ", ".join(str(entry["name"]) for entry in entries[:5])
        raise SystemExit(
            "No RGB raster tiles matched accepted extensions "
            f"{accepted_ext}. First entries are: {sample}"
        )

    downloaded = download_entries(rgb_entries, dest_dir=RAW_DIR, force=args.force)
    raster_files = [path for path in downloaded if path.suffix.lower() in {".tif", ".tiff"}]
    if not raster_files:
        names = ", ".join(path.name for path in downloaded)
        raise SystemExit(f"Downloaded files are not GeoTIFF rasters: {names}")

    build_mosaic_clipped(raster_files, output_path=OUTPUT_PATH, boundary_path=BOUNDARY_PATH)


if __name__ == "__main__":
    main()
