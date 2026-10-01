from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.services.catalog_service import CatalogService

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    catalog_service = CatalogService()
    layers = catalog_service.get_all()
    available = catalog_service.get_available_layers()
    return {
        "status": "ok",
        "catalog_status": "loaded",
        "registered_layers": len(layers),
        "available_layers": len(available),
        "data_root": settings.data_root_path.as_posix(),
    }
