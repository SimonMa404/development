"""Fetch and prepare Zensus 2022 100m indicators for the Planegg ROI.

Downloads (or reuses cached copies of) selected parquet files from
https://github.com/JsLth/z22data (directory: z22_data_100m), applies an
efficient bounding-box prefilter in EPSG:3035, then keeps complete 100m cells
whose centroids fall inside the ROI polygon.

Outputs:
  - storage/vectors/processed/planegg/census_2022_100m.geojson
  - storage/vectors/processed/planegg/census_2022_100m.parquet

The script preserves missing/disclosure-controlled values as null and does not
coerce them to zero.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests
from pyarrow import dataset as ds
from shapely.geometry import box

REPO_ROOT = Path(__file__).resolve().parents[1]

ROI_PATH = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg" / "boundary_buffered.geojson"

SOURCE_DIR = REPO_ROOT / "storage" / "vectors" / "source" / "census_2022_100m"
OUTPUT_DIR = REPO_ROOT / "storage" / "vectors" / "processed" / "planegg"

OUTPUT_GEOJSON = OUTPUT_DIR / "census_2022_100m.geojson"
OUTPUT_PARQUET = OUTPUT_DIR / "census_2022_100m.parquet"

BASE_URL = "https://raw.githubusercontent.com/JsLth/z22data/main/z22_data_100m"

FILES = {
    "population": "population_0.parquet",
    "elderly_share": "age_from_65_0.parquet",
    "children_share": "age_under_18_0.parquet",
}

CRS_LAEA = "EPSG:3035"
CRS_WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class GridSchema:
    x_col: str
    y_col: str
    value_col: str


def _download_if_missing(url: str, target: Path, force: bool) -> None:
    if target.exists() and not force:
        print(f"Using cached file: {target}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with target.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1_048_576):
                if chunk:
                    fh.write(chunk)

    print(f"Saved {target} ({target.stat().st_size:,} bytes)")


def _detect_schema(parquet_path: Path) -> GridSchema:
    schema = pq.read_schema(parquet_path)
    names = list(schema.names)
    lower_to_original = {name.lower(): name for name in names}

    x_candidates = ["x", "x_coord", "xcoord", "x_mp_100m", "x_mp"]
    y_candidates = ["y", "y_coord", "ycoord", "y_mp_100m", "y_mp"]

    x_col = next((lower_to_original[name] for name in x_candidates if name in lower_to_original), None)
    y_col = next((lower_to_original[name] for name in y_candidates if name in lower_to_original), None)

    if x_col is None or y_col is None:
        raise ValueError(f"Could not detect x/y columns in {parquet_path.name}. Available columns: {names}")

    ignored = {x_col, y_col, "id", "cell_id", "index", "idx"}
    value_candidates = [name for name in names if name not in ignored]
    if not value_candidates:
        raise ValueError(f"Could not detect value column in {parquet_path.name}. Available columns: {names}")

    return GridSchema(x_col=x_col, y_col=y_col, value_col=value_candidates[0])


def _read_bbox_filtered(path: Path, schema: GridSchema, bounds_3035: tuple[float, float, float, float]) -> pd.DataFrame:
    minx, miny, maxx, maxy = bounds_3035
    padding = 100.0

    dataset = ds.dataset(path, format="parquet")
    filt = (
        (ds.field(schema.x_col) >= (minx - padding))
        & (ds.field(schema.x_col) <= (maxx + padding))
        & (ds.field(schema.y_col) >= (miny - padding))
        & (ds.field(schema.y_col) <= (maxy + padding))
    )

    table = dataset.to_table(columns=[schema.x_col, schema.y_col, schema.value_col], filter=filt)
    frame = table.to_pandas()
    frame = frame.rename(columns={schema.x_col: "x", schema.y_col: "y", schema.value_col: "value"})
    return frame


def _guess_coordinate_origin(frames: Iterable[pd.DataFrame]) -> str:
    residues: list[float] = []
    for frame in frames:
        if frame.empty:
            continue
        residues.extend(((frame["x"].to_numpy(dtype=float) % 100.0)).tolist())
        residues.extend(((frame["y"].to_numpy(dtype=float) % 100.0)).tolist())
        if len(residues) > 1000:
            break

    if not residues:
        return "center"

    median_residue = float(np.median(residues))
    return "center" if abs(median_residue - 50.0) <= abs(median_residue - 0.0) else "lower-left"


def _grid_box(x: float, y: float, origin: str):
    if origin == "center":
        return box(x - 50.0, y - 50.0, x + 50.0, y + 50.0)
    return box(x, y, x + 100.0, y + 100.0)


def _coerce_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for col in columns:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _normalize_share(series: pd.Series) -> pd.Series:
    out = series.copy()
    mask = out.notna() & (out > 1.0) & (out <= 100.0)
    out.loc[mask] = out.loc[mask] / 100.0
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-download", action="store_true", help="Re-download source parquet files.")
    parser.add_argument("--force-write", action="store_true", help="Overwrite processed outputs.")
    args = parser.parse_args()

    if (OUTPUT_GEOJSON.exists() or OUTPUT_PARQUET.exists()) and not args.force_write:
        print("Processed Census outputs already exist. Use --force-write to regenerate.")
        return

    if not ROI_PATH.exists():
        raise FileNotFoundError(f"ROI file not found: {ROI_PATH}. Run boundary extraction first.")

    roi = gpd.read_file(ROI_PATH)
    if roi.empty:
        raise ValueError(f"ROI file has no features: {ROI_PATH}")

    roi_3035 = roi.to_crs(CRS_LAEA)
    roi_union = roi_3035.geometry.union_all() if hasattr(roi_3035.geometry, "union_all") else roi_3035.geometry.unary_union
    bounds_3035 = tuple(float(v) for v in roi_union.bounds)

    print(f"ROI bounds (EPSG:3035): {bounds_3035}")

    local_files: dict[str, Path] = {}
    for key, filename in FILES.items():
        local_path = SOURCE_DIR / filename
        _download_if_missing(f"{BASE_URL}/{filename}", local_path, force=args.force_download)
        local_files[key] = local_path

    loaded: dict[str, pd.DataFrame] = {}
    for key, path in local_files.items():
        schema = _detect_schema(path)
        frame = _read_bbox_filtered(path, schema=schema, bounds_3035=bounds_3035)
        loaded[key] = frame
        print(f"Loaded {key}: {len(frame):,} bbox-filtered rows")

    origin = _guess_coordinate_origin(loaded.values())
    print(f"Detected coordinate origin: {origin}")

    merged = loaded["population"].rename(columns={"value": "population"})
    merged = merged.merge(
        loaded["elderly_share"].rename(columns={"value": "elderly_share"}),
        on=["x", "y"],
        how="left",
    )
    merged = merged.merge(
        loaded["children_share"].rename(columns={"value": "children_share"}),
        on=["x", "y"],
        how="left",
    )

    merged = _coerce_numeric(merged, ["x", "y", "population", "elderly_share", "children_share"])
    merged["elderly_share"] = _normalize_share(merged["elderly_share"])
    merged["children_share"] = _normalize_share(merged["children_share"])

    geometry = [_grid_box(float(x), float(y), origin=origin) for x, y in zip(merged["x"].to_numpy(), merged["y"].to_numpy())]
    gdf = gpd.GeoDataFrame(merged, geometry=geometry, crs=CRS_LAEA)

    centroids = gdf.geometry.centroid
    centroid_inside = centroids.apply(roi_union.covers)
    selected = gdf.loc[centroid_inside].copy()

    selected["elderly_count"] = selected["population"] * selected["elderly_share"]
    selected["children_count"] = selected["population"] * selected["children_share"]

    selected["source"] = "German Census 2022 (Zensus 2022) via z22data"

    selected_wgs84 = selected.to_crs(CRS_WGS84)
    for col in selected_wgs84.select_dtypes(include=["string"]).columns:
        selected_wgs84[col] = selected_wgs84[col].astype(object)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selected_wgs84.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
    selected_wgs84.to_parquet(OUTPUT_PARQUET)

    print(f"Wrote {OUTPUT_GEOJSON} ({len(selected_wgs84):,} cells)")
    print(f"Wrote {OUTPUT_PARQUET} ({len(selected_wgs84):,} cells)")


if __name__ == "__main__":
    main()
