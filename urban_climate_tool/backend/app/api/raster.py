from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.errors import LayerNotFoundError, LayerUnavailableError
from app.services.catalog_service import CatalogService
from app.services.raster_service import RasterService

router = APIRouter()
catalog_service = CatalogService()
raster_service = RasterService(catalog_service)


@router.get("/tiles/{layer_id}/{z}/{x}/{y}.png")
def get_raster_tile(layer_id: str, z: int, x: int, y: int) -> Response:
    try:
        tile_bytes, content_type = raster_service.get_tile(layer_id, z, x, y)
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=tile_bytes,
        media_type=content_type,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/rasters/{layer_id}/point")
def sample_raster_point(layer_id: str, lon: float = Query(...), lat: float = Query(...)) -> dict[str, Any]:
    try:
        return raster_service.sample_point(layer_id, lon, lat)
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/terrain/status")
def terrain_status(source: str = Query(default="dem")) -> dict[str, Any]:
    sources = raster_service.terrain_sources_available()
    return {
        "available": raster_service.terrain_available(source),
        "source": source,
        "sources": sources,
    }


@router.get("/terrain/{z}/{x}/{y}.png")
def get_terrain_tile(z: int, x: int, y: int, source: str = Query(default="dem")) -> Response:
    try:
        tile_bytes, content_type = raster_service.get_terrain_tile(z, x, y, source=source)
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=tile_bytes,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
