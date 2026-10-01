from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.errors import LayerNotFoundError, LayerUnavailableError
from app.services.catalog_service import CatalogService
from app.services.vector_service import VectorService

router = APIRouter()


@router.get("/vectors/{layer_id}")
def get_vector_layer(
    layer_id: str,
    bbox: list[float] | None = Query(default=None),
) -> dict[str, Any]:
    service = VectorService(CatalogService())
    try:
        return service.get_vector(layer_id, bbox=bbox)
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
