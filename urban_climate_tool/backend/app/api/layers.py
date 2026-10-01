from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.errors import LayerNotFoundError
from app.schemas.catalog import LayerCatalogEntry
from app.schemas.layers import LayerDetail
from app.services.catalog_service import CatalogService

router = APIRouter()


def _to_layer_detail(layer: LayerCatalogEntry, available: bool) -> LayerDetail:
    return LayerDetail(
        id=layer.id,
        title=layer.title,
        short_title=layer.short_title,
        description=layer.description,
        layer_type=layer.layer_type,
        thematic_group=layer.thematic_group,
        area=layer.area,
        storage_backend=layer.storage_backend,
        relative_path=layer.relative_path,
        data_format=layer.data_format,
        source=layer.source,
        attribution=layer.attribution,
        units=layer.units,
        value_type=layer.value_type,
        native_crs=layer.native_crs,
        bounds=layer.bounds,
        acquisition_date=layer.acquisition_date,
        spatial_resolution=layer.spatial_resolution,
        nodata=layer.nodata,
        value_range=layer.value_range.model_dump() if layer.value_range else None,
        default_visible=layer.default_visible,
        default_opacity=layer.default_opacity,
        default_order=layer.default_order,
        min_zoom=layer.min_zoom,
        max_zoom=layer.max_zoom,
        inspectable=layer.inspectable,
        selectable=layer.selectable,
        style=layer.style.model_dump() if layer.style else None,
        legend=layer.legend.model_dump() if layer.legend else None,
        analysis_capabilities=layer.analysis_capabilities,
        tags=layer.tags,
        is_demo=layer.is_demo,
        available=available,
    )


@router.get("/layers", response_model=list[LayerDetail])
def list_layers(
    layer_type: str | None = Query(default=None),
    thematic_group: str | None = Query(default=None),
    availability: str | None = Query(default=None),
    tag: str | None = Query(default=None),
) -> list[LayerDetail]:
    service = CatalogService()
    layers = service.get_all()
    filtered: list[LayerDetail] = []
    for layer in layers:
        available = (settings.data_root_path / layer.relative_path).exists()
        if layer_type and layer.layer_type != layer_type:
            continue
        if thematic_group and layer.thematic_group != thematic_group:
            continue
        if availability == "available" and not available:
            continue
        if availability == "unavailable" and available:
            continue
        if tag and tag not in layer.tags:
            continue
        filtered.append(_to_layer_detail(layer, available))
    return filtered


@router.get("/layers/{layer_id}", response_model=LayerDetail)
def get_layer(layer_id: str) -> LayerDetail:
    service = CatalogService()
    try:
        layer = service.get_by_id(layer_id)
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    available = (settings.data_root_path / layer.relative_path).exists()
    return _to_layer_detail(layer, available)
