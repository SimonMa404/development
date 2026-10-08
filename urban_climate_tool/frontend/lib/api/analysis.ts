import { fetchJson, postJson } from "@/lib/api/client";
import type {
  AreaStatisticsRequest,
  AreaStatisticsResponse,
  BuildingContextRequest,
  BuildingContextResponse,
  ChangeDetectionRequest,
  ChangeDetectionResponse,
  HeatVulnerabilityRequest,
  HeatVulnerabilityResponse,
  BuildingOverviewRequest,
  BuildingOverviewResponse,
  TreeStatisticsRequest,
  TreeStatisticsResponse,
  LandUseCompositionRequest,
  LandUseCompositionResponse,
  LulcChangeSeriesResponse,
  RelativeSummerLstSeriesResponse,
} from "@/types/analysis";

export async function fetchAreaStatistics(request: AreaStatisticsRequest): Promise<AreaStatisticsResponse> {
  return postJson<AreaStatisticsResponse, AreaStatisticsRequest>("/api/analysis/area-statistics", request);
}

export async function fetchTreeStatistics(request: TreeStatisticsRequest): Promise<TreeStatisticsResponse> {
  return postJson<TreeStatisticsResponse, TreeStatisticsRequest>("/api/analysis/tree-statistics", request);
}

export async function fetchBuildingContext(request: BuildingContextRequest): Promise<BuildingContextResponse> {
  return postJson<BuildingContextResponse, BuildingContextRequest>("/api/analysis/building-context", request);
}

export async function fetchBuildingsOverview(request: BuildingOverviewRequest): Promise<BuildingOverviewResponse> {
  return postJson<BuildingOverviewResponse, BuildingOverviewRequest>("/api/analysis/buildings-overview", request);
}

export async function fetchHeatVulnerability(request: HeatVulnerabilityRequest): Promise<HeatVulnerabilityResponse> {
  return postJson<HeatVulnerabilityResponse, HeatVulnerabilityRequest>("/api/analysis/heat-vulnerability", request);
}

export async function fetchLandUseComposition(request: LandUseCompositionRequest): Promise<LandUseCompositionResponse> {
  return postJson<LandUseCompositionResponse, LandUseCompositionRequest>("/api/analysis/land-use-composition", request);
}

export async function fetchRelativeSummerLstSeries(): Promise<RelativeSummerLstSeriesResponse> {
  return fetchJson<RelativeSummerLstSeriesResponse>("/api/layers/time-series/lst-relative-summer?include_unavailable=true");
}

export async function fetchLulcChangeSeries(): Promise<LulcChangeSeriesResponse> {
  return fetchJson<LulcChangeSeriesResponse>("/api/layers/time-series/lulc-change?include_unavailable=true");
}

export async function fetchChangeDetection(request: ChangeDetectionRequest): Promise<ChangeDetectionResponse> {
  return postJson<ChangeDetectionResponse, ChangeDetectionRequest>("/api/analysis/change-detection", request);
}
