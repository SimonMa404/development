from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.errors import LayerNotFoundError, LayerUnavailableError
from app.schemas.analysis import (
    AreaStatisticsRequest,
    AreaStatisticsResponse,
    BuildingContextRequest,
    BuildingContextResponse,
    BuildingOverviewRequest,
    BuildingOverviewResponse,
    HeatVulnerabilityRequest,
    HeatVulnerabilityResponse,
)
from app.services.catalog_service import CatalogService
from app.services.statistics_service import StatisticsService

router = APIRouter()


@router.post("/analysis/area-statistics", response_model=AreaStatisticsResponse)
def area_statistics(payload: AreaStatisticsRequest) -> AreaStatisticsResponse:
    service = StatisticsService(CatalogService())
    try:
        results = service.area_statistics(payload.geometry, payload.layer_ids)
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AreaStatisticsResponse(results=results)


@router.post("/analysis/building-context", response_model=BuildingContextResponse)
def building_context(payload: BuildingContextRequest) -> BuildingContextResponse:
    service = StatisticsService(CatalogService())
    try:
        results = service.building_context_statistics(
            geometry=payload.geometry,
            layer_ids=payload.layer_ids,
            buildings_layer_id=payload.buildings_layer_id,
            buffer_meters=payload.buffer_meters,
        )
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BuildingContextResponse(results=results)


@router.post("/analysis/buildings-overview", response_model=BuildingOverviewResponse)
def buildings_overview(payload: BuildingOverviewRequest) -> BuildingOverviewResponse:
    service = StatisticsService(CatalogService())
    try:
        results = service.buildings_overview_statistics(
            layer_ids=payload.layer_ids,
            buildings_layer_id=payload.buildings_layer_id,
        )
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BuildingOverviewResponse(results=results)


@router.post("/analysis/heat-vulnerability", response_model=HeatVulnerabilityResponse)
def heat_vulnerability(payload: HeatVulnerabilityRequest) -> HeatVulnerabilityResponse:
    service = StatisticsService(CatalogService())
    try:
        result = service.heat_vulnerability(
            geometry=payload.geometry,
            census_layer_id=payload.census_layer_id,
            lst_layer_id=payload.lst_layer_id,
            ndvi_layer_id=payload.ndvi_layer_id,
        )
    except LayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LayerUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HeatVulnerabilityResponse(result=result)
