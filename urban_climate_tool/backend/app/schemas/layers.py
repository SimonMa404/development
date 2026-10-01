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
    spatial_resolution: float | int | None = None
    nodata: float | int | None = None
    value_range: dict[str, float | int] | None = None
    min_zoom: int = 0
    max_zoom: int = 20
    style: dict[str, object] | None = None
    legend: dict[str, object] | None = None
    analysis_capabilities: list[str] = Field(default_factory=list)
