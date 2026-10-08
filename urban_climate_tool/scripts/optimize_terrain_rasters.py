#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANEGG = ROOT / "storage" / "rasters" / "processed" / "planegg"

DEM_IN = PLANEGG / "dem_1m.tif"
DOM_IN = PLANEGG / "dom_20cm.tif"

DEM_OUT = PLANEGG / "dem_1m_terrain_cog.tif"
DOM_OUT = PLANEGG / "dom_terrain_1m_cog.tif"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def build_dem_cog(dem_in: Path, dem_out: Path, overwrite: bool) -> None:
    if dem_out.exists() and not overwrite:
        print(f"Skip existing {dem_out}")
        return

    if dem_out.exists() and overwrite:
        dem_out.unlink()

    run(
        [
            "gdal_translate",
            str(dem_in),
            str(dem_out),
            "-of",
            "COG",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "PREDICTOR=3",
            "-co",
            "BLOCKSIZE=512",
            "-co",
            "NUM_THREADS=ALL_CPUS",
            "-co",
            "BIGTIFF=IF_SAFER",
            "-co",
            "RESAMPLING=BILINEAR",
            "-co",
            "OVERVIEWS=AUTO",
        ]
    )


def build_dom_cog(dom_in: Path, dom_out: Path, overwrite: bool, target_resolution_m: float) -> None:
    if dom_out.exists() and not overwrite:
        print(f"Skip existing {dom_out}")
        return

    if dom_out.exists() and overwrite:
        dom_out.unlink()

    tmp_resampled = dom_out.with_suffix(".tmp_resampled.tif")
    if tmp_resampled.exists():
        tmp_resampled.unlink()

    try:
        run(
            [
                "gdalwarp",
                str(dom_in),
                str(tmp_resampled),
                "-r",
                "bilinear",
                "-tr",
                str(target_resolution_m),
                str(target_resolution_m),
                "-multi",
                "-wo",
                "NUM_THREADS=ALL_CPUS",
                "-co",
                "TILED=YES",
                "-co",
                "BLOCKXSIZE=512",
                "-co",
                "BLOCKYSIZE=512",
                "-co",
                "COMPRESS=DEFLATE",
                "-co",
                "PREDICTOR=3",
                "-co",
                "BIGTIFF=IF_SAFER",
            ]
        )

        run(
            [
                "gdal_translate",
                str(tmp_resampled),
                str(dom_out),
                "-of",
                "COG",
                "-co",
                "COMPRESS=DEFLATE",
                "-co",
                "PREDICTOR=3",
                "-co",
                "BLOCKSIZE=512",
                "-co",
                "NUM_THREADS=ALL_CPUS",
                "-co",
                "BIGTIFF=IF_SAFER",
                "-co",
                "RESAMPLING=BILINEAR",
                "-co",
                "OVERVIEWS=AUTO",
            ]
        )
    finally:
        if tmp_resampled.exists():
            tmp_resampled.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create terrain-optimized COG rasters for DEM/DOM.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dom-target-resolution", type=float, default=1.0, help="Output DOM terrain resolution in meters (default: 1.0)")
    args = parser.parse_args()

    if not DEM_IN.exists():
        raise FileNotFoundError(f"Missing DEM input: {DEM_IN}")
    if not DOM_IN.exists():
        raise FileNotFoundError(f"Missing DOM input: {DOM_IN}")

    build_dem_cog(DEM_IN, DEM_OUT, args.overwrite)
    build_dom_cog(DOM_IN, DOM_OUT, args.overwrite, args.dom_target_resolution)

    print("Done.")
    print(f"DEM optimized: {DEM_OUT}")
    print(f"DOM optimized: {DOM_OUT}")


if __name__ == "__main__":
    main()
