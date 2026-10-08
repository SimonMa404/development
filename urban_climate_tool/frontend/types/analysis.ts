export type PolygonGeometry = {
  type: "Polygon";
  coordinates: number[][][];
};

export type Histogram = {
  bin_edges: number[];
  counts: number[];
};

export type ClassBreakdownItem = {
  class_index: number;
  label: string;
  color: string;
  count: number;
  percentage: number;
};

export type StatsBlock = {
  count: number;
  minimum: number;
  maximum: number;
  mean: number;
  median: number;
  stddev: number;
  histogram?: Histogram | null;
  class_breakdown?: ClassBreakdownItem[] | null;
};

export type LayerAreaStatistics = {
  layer_id: string;
  title?: string;
  units?: string;
  value_type?: string;
  legend?: { type: string; palette: string[]; labels?: string[] } | null;
  value_range?: { minimum: number; maximum: number } | null;
  selected: StatsBlock;
  baseline: StatsBlock;
};

export type AreaStatisticsResponse = {
  results: LayerAreaStatistics[];
};

export type TreeStatisticsResult = {
  layer_id: string;
  title?: string;
  tree_count: number;
  area_hectares: number;
  tree_density_per_hectare?: number | null;
  mean_height?: number | null;
  median_height?: number | null;
  maximum_height?: number | null;
  minimum_height?: number | null;
  mean_ground_elevation?: number | null;
};

export type TreeStatisticsRequest = {
  geometry: PolygonGeometry;
  layer_id?: string;
};

export type TreeStatisticsResponse = {
  result: TreeStatisticsResult;
};

export type AreaStatisticsRequest = {
  geometry: PolygonGeometry;
  layer_ids: string[];
};

export type BuildingContextLayerStatistics = {
  layer_id: string;
  title?: string;
  units?: string;
  value_type?: string;
  legend?: { type: string; palette: string[]; labels?: string[] } | null;
  value_range?: { minimum: number; maximum: number } | null;
  selected: StatsBlock;
  average_building: StatsBlock;
};

export type BuildingContextRequest = {
  geometry: Record<string, unknown>;
  layer_ids: string[];
  buildings_layer_id?: string;
  buffer_meters?: number;
};

export type BuildingContextResponse = {
  results: BuildingContextLayerStatistics[];
};

export type BuildingOverviewLayerStatistics = {
  layer_id: string;
  title?: string;
  units?: string;
  value_type?: string;
  legend?: { type: string; palette: string[]; labels?: string[] } | null;
  value_range?: { minimum: number; maximum: number } | null;
  buildings: StatsBlock;
};

export type BuildingOverviewRequest = {
  layer_ids: string[];
  buildings_layer_id?: string;
};

export type BuildingOverviewResponse = {
  results: BuildingOverviewLayerStatistics[];
};

export type HeatExposureBin = {
  label: string;
  minimum_c?: number | null;
  maximum_c?: number | null;
  population?: number | null;
  elderly_population?: number | null;
  children_population?: number | null;
};

export type VulnerabilitySummary = {
  census_cells: number;
  total_population?: number | null;
  elderly_population?: number | null;
  elderly_share?: number | null;
  children_population?: number | null;
  children_share?: number | null;
  missing_elderly_population?: number | null;
  missing_children_population?: number | null;
};

export type HeatVulnerabilityResult = {
  census_layer_id: string;
  lst_layer_id?: string | null;
  ndvi_layer_id?: string | null;
  summary: VulnerabilitySummary;
  lst_exposure_bins?: HeatExposureBin[] | null;
  ndvi_exposure_bins?: HeatExposureBin[] | null;
};

export type HeatVulnerabilityRequest = {
  geometry: PolygonGeometry;
  census_layer_id?: string;
  lst_layer_id?: string | null;
  ndvi_layer_id?: string | null;
};

export type HeatVulnerabilityResponse = {
  result: HeatVulnerabilityResult;
};

export type LandUseCompositionClass = {
  category: string;
  feature_count: number;
  area_m2: number;
  area_hectares: number;
  share_of_selected_pct: number;
  share_of_covered_pct: number;
};

export type LandUseCompositionSummary = {
  selected_area_m2: number;
  selected_area_hectares: number;
  covered_area_m2: number;
  covered_area_hectares: number;
  covered_share_pct: number;
  uncovered_area_m2: number;
  uncovered_area_hectares: number;
};

export type LandUseCompositionResult = {
  layer_id: string;
  title?: string;
  category_field: string;
  summary: LandUseCompositionSummary;
  classes: LandUseCompositionClass[];
};

export type LandUseCompositionRequest = {
  geometry: PolygonGeometry;
  layer_id?: string;
  category_field?: string;
};

export type LandUseCompositionResponse = {
  result: LandUseCompositionResult;
};

export type RelativeSummerLstPoint = {
  year: number;
  layer_id: string;
  title: string;
  units?: string | null;
  mean_anomaly_deg_c?: number | null;
  n_scenes?: number | null;
  mean_scene_lst_deg_c?: number | null;
  available: boolean;
};

export type RelativeSummerLstSeriesResponse = {
  metric: string;
  temporal_group: string;
  csv_relative_path?: string | null;
  points: RelativeSummerLstPoint[];
};

export type LulcChangePoint = {
  year: number;
  layer_id: string;
  title: string;
  built_area_hectares?: number | null;
  total_area_hectares?: number | null;
  class_areas_hectares?: Record<string, number> | null;
  available: boolean;
};

export type LulcChangeSeriesResponse = {
  metric: string;
  temporal_group: string;
  csv_relative_path?: string | null;
  points: LulcChangePoint[];
};

export type ChangeDetectionTransition = {
  from_class_index: number;
  from_class_label: string;
  from_class_color: string;
  to_class_index: number;
  to_class_label: string;
  to_class_color: string;
  pixel_count: number;
  area_hectares: number;
  share_pct: number;
  confidence_level: "low" | "medium" | "high";
  confidence_color: string;
};

export type ChangeDetectionResult = {
  from_layer_id: string;
  to_layer_id: string;
  from_year: number;
  to_year: number;
  title?: string;
  total_area_hectares: number;
  changed_area_hectares: number;
  changed_share_pct: number;
  uncertainty_share_pct: number;
  certainty_by_level_pct: Record<"low" | "medium" | "high", number>;
  changed_areas_geojson?: Record<string, unknown> | null;
  transitions: ChangeDetectionTransition[];
};

export type ChangeDetectionRequest = {
  from_layer_id: string;
  to_layer_id: string;
};

export type ChangeDetectionResponse = {
  result: ChangeDetectionResult;
};
