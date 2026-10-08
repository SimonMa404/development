from __future__ import annotations

import csv
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.errors import LayerNotFoundError
from app.schemas.catalog import LayerCatalogEntry
from app.schemas.layers import (
    LayerDetail,
    LulcChangeSeriesPoint,
    LulcChangeSeriesResponse,
    TemporalLayerSeriesPoint,
    TemporalLayerSeriesResponse,
)
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
        temporal_start=layer.temporal_start,
        temporal_end=layer.temporal_end,
        temporal_group=layer.temporal_group,
        temporal_metric=layer.temporal_metric,
        temporal_year=layer.temporal_year,
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


def _read_yearly_csv_summary(csv_path: Path) -> dict[int, dict[str, float | int | str | None]]:
    if not csv_path.exists() or not csv_path.is_file():
        return {}

    rows_by_year: dict[int, dict[str, float | int | str | None]] = {}
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_year = (row.get("year") or "").strip()
            if not raw_year:
                continue
            try:
                year = int(raw_year)
            except ValueError:
                continue

            def _to_float(value: str | None) -> float | None:
                if value is None:
                    return None
                value = value.strip()
                if not value:
                    return None
                try:
                    return float(value)
                except ValueError:
                    return None

            def _to_int(value: str | None) -> int | None:
                if value is None:
                    return None
                value = value.strip()
                if not value:
                    return None
                try:
                    return int(float(value))
                except ValueError:
                    return None

            rows_by_year[year] = {
                "layer_id": (row.get("layer_id") or "").strip() or None,
                "mean_anomaly_deg_c": _to_float(row.get("mean_anomaly_degC") or row.get("mean_anomaly_deg_c") or row.get("anomaly_mean_degC")),
                "mean_scene_lst_deg_c": _to_float(row.get("mean_lst_degC") or row.get("mean_scene_lst_degC") or row.get("mean_lst_deg_c")),
                "n_scenes": _to_int(row.get("n_scenes") or row.get("scene_count") or row.get("valid_scenes")),
            }
    return rows_by_year


def _infer_year(layer: LayerCatalogEntry) -> int | None:
    if layer.temporal_year is not None:
        return layer.temporal_year
    if layer.acquisition_date and len(layer.acquisition_date) >= 4 and layer.acquisition_date[:4].isdigit():
        return int(layer.acquisition_date[:4])
    if layer.temporal_end and len(layer.temporal_end) >= 4 and layer.temporal_end[:4].isdigit():
        return int(layer.temporal_end[:4])
    match = re.search(r"(19|20)\d{2}", layer.id)
    if match:
        return int(match.group(0))
    return None


def _read_lulc_area_csv(csv_path: Path) -> dict[int, dict[str, float | str | None]]:
    if not csv_path.exists() or not csv_path.is_file():
        return {}

    by_year: dict[int, dict[str, float | str | None]] = {}
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_year = (row.get("year") or "").strip()
            if not raw_year:
                continue
            try:
                year = int(raw_year)
            except ValueError:
                continue

            class_index = (row.get("class_index") or "").strip()
            class_label = (row.get("class_label") or "").strip().lower()
            try:
                area_ha = float((row.get("area_ha") or "").strip())
            except ValueError:
                area_ha = 0.0

            entry = by_year.setdefault(year, {"built_area_hectares": 0.0, "total_area_hectares": 0.0, "class_areas_hectares": {}})
            entry["total_area_hectares"] = float(entry["total_area_hectares"] or 0.0) + area_ha
            class_areas = entry.setdefault("class_areas_hectares", {})
            if isinstance(class_areas, dict):
                class_areas[str(class_index)] = area_ha

            if class_index == "6" or class_label == "built area":
                entry["built_area_hectares"] = area_ha

    return by_year


@router.get("/layers/time-series/lst-relative-summer", response_model=TemporalLayerSeriesResponse)
def list_relative_summer_lst_series(
    include_unavailable: bool = Query(default=False),
    csv_relative_path: str = Query(default="rasters/derived/planegg/relative_summer_lst/yearly_summary.csv"),
) -> TemporalLayerSeriesResponse:
    service = CatalogService()
    csv_path = (settings.data_root_path / csv_relative_path).resolve()
    root = settings.data_root_path.resolve()
    if not str(csv_path).startswith(str(root)):
        raise HTTPException(status_code=400, detail="csv_relative_path resolves outside DATA_ROOT")

    csv_rows = _read_yearly_csv_summary(csv_path)
    candidates = [
        layer
        for layer in service.get_all()
        if layer.layer_type == "raster"
        and (
            layer.temporal_group == "relative_summer_lst"
            or "relative-summer-lst" in layer.tags
            or layer.id.startswith("lst-relative-summer-")
        )
    ]

    points_by_year: dict[int, TemporalLayerSeriesPoint] = {}

    for layer in candidates:
        available = (settings.data_root_path / layer.relative_path).exists()
        if not include_unavailable and not available:
            continue

        year = _infer_year(layer)
        if year is None:
            continue

        summary = csv_rows.get(year, {})
        points_by_year[year] = TemporalLayerSeriesPoint(
            year=year,
            layer_id=layer.id,
            title=layer.short_title or layer.title,
            units=layer.units,
            mean_anomaly_deg_c=summary.get("mean_anomaly_deg_c") if summary else None,
            n_scenes=summary.get("n_scenes") if summary else None,
            mean_scene_lst_deg_c=summary.get("mean_scene_lst_deg_c") if summary else None,
            available=available,
        )

    # Merge CSV-only years so the time series can still be explored before all rasters are registered.
    for year, summary in sorted(csv_rows.items()):
        if year in points_by_year:
            continue
        points_by_year[year] = TemporalLayerSeriesPoint(
            year=year,
            layer_id=str(summary.get("layer_id") or f"lst-relative-summer-{year}"),
            title=f"Relative summer LST {year}",
            units="°C",
            mean_anomaly_deg_c=summary.get("mean_anomaly_deg_c") if summary else None,
            n_scenes=summary.get("n_scenes") if summary else None,
            mean_scene_lst_deg_c=summary.get("mean_scene_lst_deg_c") if summary else None,
            available=False,
        )

    points = list(points_by_year.values())

    points.sort(key=lambda item: item.year)
    return TemporalLayerSeriesResponse(
        metric="relative_summer_lst_anomaly",
        temporal_group="relative_summer_lst",
        csv_relative_path=csv_relative_path if csv_path.exists() else None,
        points=points,
    )


@router.get("/layers/time-series/lulc-change", response_model=LulcChangeSeriesResponse)
def list_lulc_change_series(
    include_unavailable: bool = Query(default=False),
    csv_relative_path: str = Query(default="rasters/derived/planegg/lulc_yearly/yearly_class_area.csv"),
) -> LulcChangeSeriesResponse:
    service = CatalogService()
    csv_path = (settings.data_root_path / csv_relative_path).resolve()
    root = settings.data_root_path.resolve()
    if not str(csv_path).startswith(str(root)):
        raise HTTPException(status_code=400, detail="csv_relative_path resolves outside DATA_ROOT")

    area_rows = _read_lulc_area_csv(csv_path)
    candidates = [
        layer
        for layer in service.get_all()
        if layer.layer_type == "raster"
        and (
            layer.temporal_group == "lulc_yearly"
            or "lulc" in layer.tags
            or layer.id.startswith("lulc-planegg-")
        )
    ]

    points_by_year: dict[int, LulcChangeSeriesPoint] = {}
    for layer in candidates:
        year = _infer_year(layer)
        if year is None:
            continue
        available = (settings.data_root_path / layer.relative_path).exists()
        if not include_unavailable and not available:
            continue
        area_entry = area_rows.get(year, {})
        points_by_year[year] = LulcChangeSeriesPoint(
            year=year,
            layer_id=layer.id,
            title=layer.short_title or layer.title,
            built_area_hectares=float(area_entry.get("built_area_hectares")) if area_entry else None,
            total_area_hectares=float(area_entry.get("total_area_hectares")) if area_entry else None,
            class_areas_hectares=area_entry.get("class_areas_hectares") if area_entry else None,
            available=available,
        )

    for year, area_entry in sorted(area_rows.items()):
        if year in points_by_year:
            continue
        points_by_year[year] = LulcChangeSeriesPoint(
            year=year,
            layer_id=f"lulc-planegg-{year}",
            title=f"LULC {year}",
            built_area_hectares=float(area_entry.get("built_area_hectares")) if area_entry else None,
            total_area_hectares=float(area_entry.get("total_area_hectares")) if area_entry else None,
            class_areas_hectares=area_entry.get("class_areas_hectares") if area_entry else None,
            available=False,
        )

    points = sorted(points_by_year.values(), key=lambda item: item.year)
    return LulcChangeSeriesResponse(
        metric="lulc_built_area",
        temporal_group="lulc_yearly",
        csv_relative_path=csv_relative_path if csv_path.exists() else None,
        points=points,
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
