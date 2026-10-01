from __future__ import annotations

from pathlib import Path

import rasterio
from rio_tiler.io import Reader

from app.repositories.base import LocalRepository


class LocalRasterRepository(LocalRepository):
    def raster_path(self, relative_path: str) -> Path:
        path = self.resolve_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"Raster not found: {relative_path}")
        return path

    def preview_reader(self, relative_path: str):
        return Reader(self.raster_path(relative_path))

    def read_metadata(self, relative_path: str) -> dict:
        with rasterio.open(self.raster_path(relative_path)) as dataset:
            return {
                "width": dataset.width,
                "height": dataset.height,
                "count": dataset.count,
                "crs": str(dataset.crs) if dataset.crs else None,
                "bounds": dataset.bounds,
                "transform": dataset.transform,
                "nodata": dataset.nodata,
                "dtype": dataset.dtypes[0],
            }
