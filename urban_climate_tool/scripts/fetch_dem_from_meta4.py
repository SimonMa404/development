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
import hashlib
import sys
from pathlib import Path

import geopandas as gpd
import requests
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from lxml import etree

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "storage" / "rasters" / "source" / "dem_1m"
PROCESSED_DIR = REPO_ROOT / "storage" / "rasters" / "processed" / "planegg"
OUTPUT_PATH = PROCESSED_DIR / "dem_1m.tif"
BOUNDARY_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"

META_NS = {"m": "urn:ietf:params:xml:ns:metalink"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_meta4(meta4_path: Path) -> list[dict[str, object]]:
    root = etree.fromstring(meta4_path.read_bytes())
    entries: list[dict[str, object]] = []

    for file_elem in root.xpath("//m:file", namespaces=META_NS):
        name = file_elem.get("name")
        if not name:
            continue
        size_elem = file_elem.find("m:size", namespaces=META_NS)
        hash_elem = file_elem.find("m:hash[@type='sha-256']", namespaces=META_NS)
        url_elems = file_elem.findall("m:url", namespaces=META_NS)

        if size_elem is None or hash_elem is None or not hash_elem.text:
            continue

        urls = [u.text.strip() for u in url_elems if u.text and u.text.strip()]
        if not urls:
            continue

        entries.append(
            {
                "name": name,
                "size": int(size_elem.text),
                "sha256": hash_elem.text.strip().lower(),
                "urls": urls,
            }
        )

    return entries


def validate_download(path: Path, expected_size: int, expected_sha256: str) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size != expected_size:
        return False
    return file_sha256(path) == expected_sha256


def download_entry(entry: dict[str, object], force: bool = False) -> Path:
    name = str(entry["name"])
    expected_size = int(entry["size"])
    expected_sha256 = str(entry["sha256"])
    urls = list(entry["urls"])  # type: ignore[arg-type]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / name

    if dest.exists() and not force and validate_download(dest, expected_size, expected_sha256):
        print(f"[skip] {name} already valid")
        return dest

    for url in urls:
        print(f"[download] {name} <- {url}")
        try:
            with requests.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)
                tmp.rename(dest)
            if validate_download(dest, expected_size, expected_sha256):
                print(f"  -> ok ({dest.stat().st_size / 1e6:.1f} MB)")
                return dest
            print(f"  !! validation failed for {name} from {url}", file=sys.stderr)
        except requests.RequestException as exc:
            print(f"  !! failed {url}: {exc}", file=sys.stderr)

    raise RuntimeError(f"Failed to download valid file for {name}")


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

    dem_entries = [e for e in entries if str(e["name"]).lower().endswith(accepted_ext)]
    if not dem_entries:
        sample = ", ".join(str(e["name"]) for e in entries[:5])
        raise SystemExit(
            "No DEM raster tiles matched accepted extensions "
            f"{accepted_ext}. First entries are: {sample}"
        )

    downloaded: list[Path] = []
    for entry in dem_entries:
        downloaded.append(download_entry(entry, force=args.force))

    # Ensure only raster files are used in mosaic.
    raster_files = [p for p in downloaded if p.suffix.lower() in {".tif", ".tiff"}]
    if not raster_files:
        names = ", ".join(p.name for p in downloaded)
        raise SystemExit(f"Downloaded files are not GeoTIFF rasters: {names}")

    build_dem_mosaic_clipped(raster_files, OUTPUT_PATH)


if __name__ == "__main__":
    main()
