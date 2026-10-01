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
        gdf = gpd.read_file(path)
        if bbox:
            minx, miny, maxx, maxy = bbox
            gdf = gdf.cx[minx:maxx, miny:maxy]
        return gdf.__geo_interface__
