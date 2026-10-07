import { postJson } from "@/lib/api/client";
import type {
  AreaStatisticsRequest,
  AreaStatisticsResponse,
  BuildingContextRequest,
  BuildingContextResponse,
  HeatVulnerabilityRequest,
  HeatVulnerabilityResponse,
  BuildingOverviewRequest,
  BuildingOverviewResponse,
  TreeStatisticsRequest,
  TreeStatisticsResponse,
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
