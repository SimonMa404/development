from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.errors import LayerNotFoundError, LayerUnavailableError
from app.services.catalog_service import CatalogService
from app.services.vector_service import VectorService

router = APIRouter()


@router.get("/vectors/{layer_id}")
def get_vector_layer(
    layer_id: str,
    bbox: list[float] | None = Query(default=None),
) -> Any:
    service = VectorService(CatalogService())
    try:
        if bbox is None:
            path = service.get_vector_path(layer_id)
            if path.suffix.lower() == ".geojson":
                return FileResponse(path, media_type="application/geo+json")
        return service.get_vector(layer_id, bbox=bbox)
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
