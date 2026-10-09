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


class BuildingStatisticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    layer_id: str = "buildings-3d-planegg"


class BuildingStatisticsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    building_count: int
    area_hectares: float
    building_density_per_hectare: float | None = None
    mean_height: float | None = None
    median_height: float | None = None
    maximum_height: float | None = None
    minimum_height: float | None = None


class BuildingStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: BuildingStatisticsResult


class ElevationStatisticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    layer_id: str = "dsm-planegg"


class ElevationStatisticsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    units: str | None = None
    area_hectares: float
    minimum_elevation: float | None = None
    mean_elevation: float | None = None
    median_elevation: float | None = None
    maximum_elevation: float | None = None
    stddev_elevation: float | None = None


class ElevationStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: ElevationStatisticsResult


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


class PopulationCategorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    population: float | None = None
    share: float | None = None


class VulnerabilitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_cells: int
    total_population: float | None = None
    missing_population: float | None = None
    elderly_population: float | None = None
    elderly_share: float | None = None
    children_population: float | None = None
    children_share: float | None = None
    missing_elderly_population: float | None = None
    missing_children_population: float | None = None
    population_categories: list[PopulationCategorySummary] | None = None


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


class LandUseCompositionClass(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    feature_count: int
    area_m2: float
    area_hectares: float
    share_of_selected_pct: float
    share_of_covered_pct: float


class LandUseCompositionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_area_m2: float
    selected_area_hectares: float
    covered_area_m2: float
    covered_area_hectares: float
    covered_share_pct: float
    uncovered_area_m2: float
    uncovered_area_hectares: float


class LandUseCompositionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    title: str | None = None
    category_field: str
    summary: LandUseCompositionSummary
    classes: list[LandUseCompositionClass]


class LandUseCompositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: dict
    layer_id: str = "nutzung-planegg"
    category_field: str = "nutzart"


class LandUseCompositionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: LandUseCompositionResult


class PointSampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    longitude: float
    latitude: float
    sampled_value: float | None = None
    units: str | None = None
    valid: bool = True
    nodata: bool = False


class TransitionMatrixCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_class_index: int
    from_class_label: str
    from_class_color: str
    to_class_index: int
    to_class_label: str
    to_class_color: str
    pixel_count: int
    area_hectares: float
    share_pct: float
    confidence_level: str
    confidence_color: str


class ChangeDetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_layer_id: str
    to_layer_id: str
    from_year: int
    to_year: int
    title: str | None = None
    total_area_hectares: float
    changed_area_hectares: float
    changed_share_pct: float
    uncertainty_share_pct: float
    certainty_by_level_pct: dict[str, float] = Field(default_factory=dict)
    changed_areas_geojson: dict | None = None
    transitions: list[TransitionMatrixCell]


class ChangeDetectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_layer_id: str
    to_layer_id: str


class ChangeDetectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: ChangeDetectionResult
