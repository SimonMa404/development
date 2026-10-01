from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.errors import LayerUnavailableError
from app.repositories.local_vector import LocalVectorRepository
from app.services.catalog_service import CatalogService


class VectorService:
    def __init__(self, catalog_service: CatalogService | None = None):
        self.catalog_service = catalog_service or CatalogService()
        self.repository = LocalVectorRepository(settings.data_root_path)

    def get_vector(self, layer_id: str, bbox: list[float] | None = None) -> dict[str, Any]:
        layer = self.catalog_service.get_by_id(layer_id)
        if layer.layer_type != "vector":
            raise LayerUnavailableError(f"Layer '{layer_id}' is not a vector layer.")
        return self.repository.read_geojson(layer.relative_path, bbox=bbox)
