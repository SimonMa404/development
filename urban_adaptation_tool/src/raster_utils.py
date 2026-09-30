from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import numpy as np
import rasterio
from rasterio.windows import Window


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_tiff_files(directory: str | Path) -> List[Path]:
    directory = Path(directory)
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.tif") if p.is_file())


def read_raster(path: str | Path):
    path = Path(path)
    with rasterio.open(path) as src:
        arr = src.read(1)
        bounds = src.bounds
        crs = src.crs
        profile = src.profile.copy()
        return {
            "array": arr,
            "bounds": bounds,
            "crs": crs,
            "profile": profile,
            "shape": arr.shape,
        }


def mask_nodata(array: np.ndarray, nodata: float | None = None) -> np.ndarray:
    if nodata is not None:
        array = np.where(array == nodata, np.nan, array)
    return array


def normalize_array(array: np.ndarray, low: float | None = None, high: float | None = None) -> np.ndarray:
    arr = array.astype(np.float32)
    arr = np.nan_to_num(arr, nan=0.0)
    if low is None:
        low = float(np.min(arr))
    if high is None:
        high = float(np.max(arr))
    if high == low:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - low) / (high - low)


def class_percentage_summary(class_array: np.ndarray, class_ids: Iterable[int]) -> dict[int, float]:
    valid = class_array[np.isfinite(class_array)]
    total = valid.size
    if total == 0:
        return {int(class_id): 0.0 for class_id in class_ids}

    results = {}
    for class_id in class_ids:
        count = np.sum(valid == class_id)
        results[int(class_id)] = (count / total) * 100.0
    return results


def write_raster(path: str | Path, array: np.ndarray, profile: dict) -> Path:
    out_path = Path(path)
    ensure_dir(out_path.parent)
    profile = profile.copy()
    profile.update(dtype=rasterio.float32, nodata=np.nan, count=1)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(array.astype(rasterio.float32), 1)
    return out_path
