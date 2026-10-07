from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Histogram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bin_edges: list[float]
    counts: list[int]


class ClassBreakdownItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_index: int
    label: str
    color: str
    count: int
    percentage: float


class StatsBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    minimum: float
    maximum: float
    mean: float
    median: float
    stddev: float
    histogram: Histogram | None = None
    class_breakdown: list[ClassBreakdownItem] | None = None


class LayerAreaStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    units: str | None = None
    value_type: str | None = None
    legend: dict | None = None
    value_range: dict | None = None
    selected: StatsBlock
    baseline: StatsBlock


class AreaStatisticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    layer_ids: list[str] = Field(default_factory=list)


class AreaStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[LayerAreaStatistics]


class TreeStatisticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    layer_id: str = "trees-3d-planegg"


class TreeStatisticsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    tree_count: int
    area_hectares: float
    tree_density_per_hectare: float | None = None
    mean_height: float | None = None
    median_height: float | None = None
    maximum_height: float | None = None
    minimum_height: float | None = None
    mean_ground_elevation: float | None = None


class TreeStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: TreeStatisticsResult


class BuildingContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    layer_ids: list[str] = Field(default_factory=list)
    buildings_layer_id: str = "buildings-3d-planegg"
    buffer_meters: float = 15.0


class BuildingContextLayerStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    units: str | None = None
    value_type: str | None = None
    legend: dict | None = None
    value_range: dict | None = None
    selected: StatsBlock
    average_building: StatsBlock


class BuildingContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[BuildingContextLayerStatistics]


class BuildingOverviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_ids: list[str] = Field(default_factory=list)
    buildings_layer_id: str = "buildings-3d-planegg"


class BuildingOverviewLayerStatistics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    units: str | None = None
    value_type: str | None = None
    legend: dict | None = None
    value_range: dict | None = None
    buildings: StatsBlock


class BuildingOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[BuildingOverviewLayerStatistics]


class HeatExposureBin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    minimum_c: float | None = None
    maximum_c: float | None = None
    population: float | None = None
    elderly_population: float | None = None
    children_population: float | None = None


class VulnerabilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_cells: int
    total_population: float | None = None
    elderly_population: float | None = None
    elderly_share: float | None = None
    children_population: float | None = None
    children_share: float | None = None
    missing_elderly_population: float | None = None
    missing_children_population: float | None = None


class HeatVulnerabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_layer_id: str
    lst_layer_id: str | None = None
    ndvi_layer_id: str | None = None
    summary: VulnerabilitySummary
    lst_exposure_bins: list[HeatExposureBin] | None = None
    ndvi_exposure_bins: list[HeatExposureBin] | None = None


class HeatVulnerabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    census_layer_id: str = "census-2022-100m-planegg"
    lst_layer_id: str | None = "lst-planegg"
    ndvi_layer_id: str | None = None


class HeatVulnerabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: HeatVulnerabilityResult


class PointSampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    longitude: float
    latitude: float
    sampled_value: float | None = None
    units: str | None = None
    valid: bool = True
    nodata: bool = False
