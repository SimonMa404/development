from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LayerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    short_title: str | None = None
    description: str | None = None
    layer_type: str
    thematic_group: str | None = None
    area: str | None = None
    source: str | None = None
    attribution: str | None = None
    units: str | None = None
    native_crs: str | None = None
    default_visible: bool = False
    default_opacity: float = 1.0
    default_order: int = 0
    inspectable: bool = False
    selectable: bool = False
    available: bool = True
    tags: list[str] = Field(default_factory=list)
    is_demo: bool = False


class LayerDetail(LayerSummary):
    model_config = ConfigDict(extra="forbid")

    storage_backend: str = "local"
    relative_path: str | None = None
    data_format: str | None = None
    value_type: str | None = None
    bounds: dict[str, float] | None = None
    acquisition_date: str | None = None
    temporal_start: str | None = None
    temporal_end: str | None = None
    temporal_group: str | None = None
    temporal_metric: str | None = None
    temporal_year: int | None = None
    spatial_resolution: float | int | None = None
    nodata: float | int | None = None
    value_range: dict[str, float | int] | None = None
    min_zoom: int = 0
    max_zoom: int = 20
    style: dict[str, object] | None = None
    legend: dict[str, object] | None = None
    analysis_capabilities: list[str] = Field(default_factory=list)


class TemporalLayerSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    layer_id: str
    title: str
    units: str | None = None
    mean_anomaly_deg_c: float | None = None
    n_scenes: int | None = None
    mean_scene_lst_deg_c: float | None = None
    available: bool = True


class TemporalLayerSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    temporal_group: str
    csv_relative_path: str | None = None
    points: list[TemporalLayerSeriesPoint] = Field(default_factory=list)


class LulcChangeSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    layer_id: str
    title: str
    built_area_hectares: float | None = None
    total_area_hectares: float | None = None
    class_areas_hectares: dict[str, float] | None = None
    available: bool = True


class LulcChangeSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    temporal_group: str
    csv_relative_path: str | None = None
    points: list[LulcChangeSeriesPoint] = Field(default_factory=list)
