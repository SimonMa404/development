from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LegendSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    palette: list[str]
    labels: list[str] | None = None


class ValueRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum: float | int
    maximum: float | int


class StyleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color_scale: str | None = None
    interpolation: str | None = None
    opacity: float | None = None


class LayerCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    short_title: str | None = None
    description: str | None = None
    layer_type: str
    thematic_group: str | None = None
    area: str | None = None
    storage_backend: str = "local"
    relative_path: str
    data_format: str
    source: str | None = None
    attribution: str | None = None
    units: str | None = None
    value_type: str | None = None
    native_crs: str | None = None
    bounds: dict[str, float] | None = None
    acquisition_date: str | None = None
    temporal_start: str | None = None
    temporal_end: str | None = None
    temporal_group: str | None = None
    temporal_metric: str | None = None
    temporal_year: int | None = None
    spatial_resolution: float | int | None = None
    nodata: float | int | None = None
    value_range: ValueRange | None = None
    default_visible: bool = False
    default_opacity: float = 1.0
    default_order: int = 0
    min_zoom: int = 0
    max_zoom: int = 20
    inspectable: bool = False
    selectable: bool = False
    style: StyleSpec | None = None
    legend: LegendSpec | None = None
    analysis_capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_demo: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Layer id is required.")
        return value.strip()

    @field_validator("layer_type")
    @classmethod
    def validate_layer_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"raster", "vector", "point"}:
            raise ValueError("Layer type must be raster, vector, or point.")
        return normalized

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if not value or value.startswith("/"):
            raise ValueError("relative_path must be relative to DATA_ROOT.")
        return value.strip().replace("\\", "/")


class LayerCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layers: list[LayerCatalogEntry]

    @field_validator("layers")
    @classmethod
    def validate_unique_ids(cls, value: list[LayerCatalogEntry]) -> list[LayerCatalogEntry]:
        seen: set[str] = set()
        for layer in value:
            if layer.id in seen:
                raise ValueError(f"Duplicate layer id: {layer.id}")
            seen.add(layer.id)
        return value
