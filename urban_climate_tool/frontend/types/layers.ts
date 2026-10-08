export type LayerType = "raster" | "vector" | "point";

export type LayerLegend = {
  type: string;
  palette: string[];
  labels?: string[];
};

export type LayerStyle = {
  color_scale?: string;
  interpolation?: string;
  opacity?: number;
};

export type LayerValueRange = {
  minimum: number;
  maximum: number;
};

export type CatalogLayer = {
  id: string;
  title: string;
  short_title?: string;
  description?: string;
  layer_type: LayerType;
  thematic_group?: string;
  area?: string;
  storage_backend: string;
  relative_path: string;
  data_format: string;
  source?: string;
  attribution?: string;
  units?: string;
  value_type?: string;
  native_crs?: string;
  bounds?: Record<string, number>;
  acquisition_date?: string;
  temporal_start?: string;
  temporal_end?: string;
  temporal_group?: string;
  temporal_metric?: string;
  temporal_year?: number;
  spatial_resolution?: number;
  nodata?: number;
  value_range?: LayerValueRange;
  default_visible: boolean;
  default_opacity: number;
  default_order: number;
  min_zoom: number;
  max_zoom: number;
  inspectable: boolean;
  selectable: boolean;
  style?: LayerStyle;
  legend?: LayerLegend;
  analysis_capabilities: string[];
  tags: string[];
  is_demo: boolean;
  available: boolean;
};

export type LayerFilter = {
  layerType?: string;
  thematicGroup?: string;
  availability?: "available" | "unavailable";
  tag?: string;
};
