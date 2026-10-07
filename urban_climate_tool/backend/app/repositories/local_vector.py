from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from app.repositories.base import LocalRepository


class LocalVectorRepository(LocalRepository):
    def vector_path(self, relative_path: str) -> Path:
        path = self.resolve_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(f"Vector file not found: {relative_path}")
        return path

    def read_geojson(self, relative_path: str, bbox: list[float] | None = None) -> dict:
        path = self.vector_path(relative_path)
        gdf = self.read_frame(relative_path, bbox=bbox)
        return gdf.__geo_interface__

    def read_frame(self, relative_path: str, bbox: list[float] | None = None) -> gpd.GeoDataFrame:
        path = self.vector_path(relative_path)
        suffix = path.suffix.lower()
        bounds = tuple(bbox) if bbox and len(bbox) == 4 else None

        if suffix in {".parquet", ".geoparquet"}:
            try:
                return gpd.read_parquet(path, bbox=bounds)
            except TypeError:
                gdf = gpd.read_parquet(path)
        else:
            try:
                return gpd.read_file(path, bbox=bounds)
            except TypeError:
                gdf = gpd.read_file(path)

        if bounds:
            minx, miny, maxx, maxy = bounds
            gdf = gdf.cx[minx:maxx, miny:maxy]
        return gdf
