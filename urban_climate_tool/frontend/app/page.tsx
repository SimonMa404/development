"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { MapCanvas, type BasemapId, type TerrainSourceId } from "@/components/map/MapCanvas";
import { MapLegend } from "@/components/map/MapLegend";
import { BasemapSwitcher } from "@/components/map/BasemapSwitcher";
import { LayerPanel } from "@/components/layers/LayerPanel";
import { DrawToolbar } from "@/components/analysis/DrawToolbar";
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel";
import { RelativeSummerLstPanel } from "@/components/analysis/RelativeSummerLstPanel";
import { LulcChangePanel, type LulcClassSeries, type LulcYearPoint, type LulcYearRange } from "@/components/analysis/LulcChangePanel";
import { CollapsiblePanel } from "@/components/layout/CollapsiblePanel";
import { useLayerCatalog } from "@/hooks/useLayerCatalog";
import { useLulcChangeSeries } from "@/hooks/useLulcChangeSeries";
import { useRelativeSummerLstSeries } from "@/hooks/useRelativeSummerLstSeries";
import { useAreaStatistics } from "@/hooks/useAreaStatistics";
import {
  fetchAreaStatistics,
  fetchBuildingContext,
  fetchBuildingsOverview,
  fetchChangeDetection,
  fetchHeatVulnerability,
  fetchLandUseComposition,
  fetchTreeStatistics,
} from "@/lib/api/analysis";
import { API_BASE_URL, fetchJson } from "@/lib/api/client";
import type {
  AreaStatisticsResponse,
  BuildingContextResponse,
  ChangeDetectionResult,
  BuildingOverviewLayerStatistics,
  ChangeDetectionResponse,
  HeatVulnerabilityResult,
  LandUseCompositionResult,
  LayerAreaStatistics,
  RelativeSummerLstPoint,
  TreeStatisticsResult,
} from "@/types/analysis";
import type { CatalogLayer } from "@/types/layers";

type SelectedBuilding = {
  id: string;
  properties: Record<string, unknown>;
  geometry: Record<string, unknown>;
  lngLat: [number, number];
};

type SelectedNutzung = {
  id: string;
  properties: Record<string, unknown>;
  geometry: Record<string, unknown>;
  lngLat: [number, number];
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

function nutzungCategoryColor(category: unknown): string {
  const key = String(category ?? "").trim();
  const palette: Record<string, string> = {
    "Wohnbaufläche": "#f59e0b",
    "Industrie- und Gewerbefläche": "#6b7280",
    "Fläche gemischter Nutzung": "#a855f7",
    "Sport-, Freizeit- und Erholungsfläche": "#84cc16",
    Landwirtschaft: "#eab308",
    Wald: "#15803d",
    Gehölz: "#22c55e",
    "Stehendes Gewässer": "#3b82f6",
    "Fließgewässer": "#06b6d4",
    Straßenverkehr: "#475569",
    Bahnverkehr: "#334155",
    Weg: "#94a3b8",
    Platz: "#cbd5e1",
    Friedhof: "#65a30d",
    "Fläche besonderer funktionaler Prägung": "#f97316",
    "Tagebau, Grube, Steinbruch": "#92400e",
    "Unland/Vegetationslose Fläche": "#78716c",
  };
  return palette[key] ?? "#64748b";
}

function extractBuildingHeight(properties?: Record<string, unknown> | null): number {
  if (!properties) return 0;

  const direct = Number(properties.height);
  if (Number.isFinite(direct) && direct > 0) return direct;

  const roof = Number(properties.roof_height);
  const ground = Number(properties.ground_height);
  if (Number.isFinite(roof) && Number.isFinite(ground) && roof > ground) {
    return roof - ground;
  }

  const zMax = Number(properties.z_max);
  const zMin = Number(properties.z_min);
  if (Number.isFinite(zMax) && Number.isFinite(zMin) && zMax > zMin) {
    return zMax - zMin;
  }

  return 0;
}

type DrawnPolygonGeometry = {
  type: "Polygon";
  coordinates: number[][][];
};
type SwipeLayerSelection = "from-rgb" | "to-rgb" | "from-lulc" | "to-lulc";
type EffectiveTerrainMode = "off" | "dem" | "dom" | "dsm";
const LEGACY_LULC_LAYER_ID = "lulc-planegg";

export default function HomePage() {
  const { data: catalogLayers, isLoading, error } = useLayerCatalog();
  const relativeSummerLstSeries = useRelativeSummerLstSeries();
  const lulcChangeSeries = useLulcChangeSeries();
  const [overrides, setOverrides] = useState<Record<string, Partial<CatalogLayer>>>({});
  const [drawMode, setDrawMode] = useState(false);
  const [drawnPoints, setDrawnPoints] = useState<[number, number][]>([]);
  const [drawnGeometry, setDrawnGeometry] = useState<DrawnPolygonGeometry | null>(null);
  const [basemap, setBasemap] = useState<BasemapId>("satellite");
  const [terrain3dEnabled, setTerrain3dEnabled] = useState(false);
  const [terrainSource, setTerrainSource] = useState<TerrainSourceId>("dem");
  const [effectiveTerrainMode, setEffectiveTerrainMode] = useState<EffectiveTerrainMode>("off");
  const [terrainOffIntentVersion, setTerrainOffIntentVersion] = useState(0);
  const [terrainAvailable, setTerrainAvailable] = useState(true);
  const [terrainSourcesAvailable, setTerrainSourcesAvailable] = useState<Record<TerrainSourceId, boolean>>({ dem: true, dom: true, dsm: true });
  const [terrainExaggeration, setTerrainExaggeration] = useState(1.8);
  const [hillshadeStrength, setHillshadeStrength] = useState(0.7);
  const [layersPanelOpen, setLayersPanelOpen] = useState(true);
  const [comparisonPanelOpen, setComparisonPanelOpen] = useState(true);
  const [analysisPanelOpen, setAnalysisPanelOpen] = useState(true);
  const [analysisView, setAnalysisView] = useState<"planegg" | "drawn">("planegg");
  const [dashboardMode, setDashboardMode] = useState<"analysis" | "heat-development" | "land-cover-change">("analysis");
  const [timeSeriesScope, setTimeSeriesScope] = useState<"planegg" | "drawn">("planegg");
  const [selectedSeriesLayerId, setSelectedSeriesLayerId] = useState<string | null>(null);
  const [selectedLulcLayerId, setSelectedLulcLayerId] = useState<string | null>(null);
  const [selectedRgbLayerId, setSelectedRgbLayerId] = useState<string | null>(null);
  const [lulcYearRange, setLulcYearRange] = useState<LulcYearRange>({ fromYear: null, toYear: null });
  const [changeDetectionVisible, setChangeDetectionVisible] = useState(true);
  const [changeDetectionOpacity, setChangeDetectionOpacity] = useState(0.7);
  const [fromLulcVisible, setFromLulcVisible] = useState(false);
  const [toLulcVisible, setToLulcVisible] = useState(true);
  const [fromRgbVisible, setFromRgbVisible] = useState(false);
  const [toRgbVisible, setToRgbVisible] = useState(false);
  const [fromLulcOpacity, setFromLulcOpacity] = useState(0.85);
  const [toLulcOpacity, setToLulcOpacity] = useState(0.9);
  const [fromRgbOpacity, setFromRgbOpacity] = useState(0.8);
  const [toRgbOpacity, setToRgbOpacity] = useState(0.8);
  const [swipeEnabled, setSwipeEnabled] = useState(false);
  const [swipePosition, setSwipePosition] = useState(0.5);
  const [swipeLeftSelection, setSwipeLeftSelection] = useState<SwipeLayerSelection>("from-rgb");
  const [swipeRightSelection, setSwipeRightSelection] = useState<SwipeLayerSelection>("to-rgb");
  const [layerCompareEnabled, setLayerCompareEnabled] = useState(false);
  const [layerComparePosition, setLayerComparePosition] = useState(0.5);
  const [layerCompareLeftId, setLayerCompareLeftId] = useState<string | null>(null);
  const [layerCompareRightId, setLayerCompareRightId] = useState<string | null>(null);
  const [changeDetectionResult, setChangeDetectionResult] = useState<ChangeDetectionResult | null>(null);
  const changeDetectionCacheRef = useRef<Record<string, ChangeDetectionResult>>({});
  const hasAutoSelectedSeriesRef = useRef(false);
  const [hasDrawnSelection, setHasDrawnSelection] = useState(false);
  const [selectedBuilding, setSelectedBuilding] = useState<SelectedBuilding | null>(null);
  const [selectedNutzung, setSelectedNutzung] = useState<SelectedNutzung | null>(null);
  const [allBuildingHeights, setAllBuildingHeights] = useState<number[]>([]);
  const [overviewResults, setOverviewResults] = useState<LayerAreaStatistics[] | undefined>(undefined);
  const [overviewPending, setOverviewPending] = useState(false);
  const [overviewError, setOverviewError] = useState<Error | null>(null);
  const [overviewBuildingStats, setOverviewBuildingStats] = useState<{ count: number; averageHeight: number } | null>(null);
  const [overviewBuildingClimate, setOverviewBuildingClimate] = useState<BuildingOverviewLayerStatistics[]>([]);
  const [overviewVulnerability, setOverviewVulnerability] = useState<HeatVulnerabilityResult | null>(null);
  const [overviewTreeStats, setOverviewTreeStats] = useState<TreeStatisticsResult | null>(null);
  const [overviewLandUse, setOverviewLandUse] = useState<LandUseCompositionResult | null>(null);
  const [activeLayerOrder, setActiveLayerOrder] = useState<string[]>([]);
  const [draggingActiveLayerId, setDraggingActiveLayerId] = useState<string | null>(null);
  const [activeDropTargetId, setActiveDropTargetId] = useState<string | null>(null);
  const domTerrainMode = effectiveTerrainMode === "dom" || effectiveTerrainMode === "dsm";
  const hasAnyTerrainSource = terrainSourcesAvailable.dem || terrainSourcesAvailable.dom || terrainSourcesAvailable.dsm;

  const areaStatistics = useAreaStatistics();
  const buildingContext = useMutation<BuildingContextResponse, Error, { geometry: Record<string, unknown>; layer_ids: string[] }>({
    mutationFn: (payload) =>
      fetchBuildingContext({
        ...payload,
        buildings_layer_id: "buildings-3d-planegg",
        buffer_meters: 15,
      }),
  });
  const heatVulnerability = useMutation<
    HeatVulnerabilityResult,
    Error,
    { geometry: { type: "Polygon"; coordinates: number[][][] }; lstLayerId?: string | null; ndviLayerId?: string | null }
  >({
    mutationFn: async (payload) => {
      const response = await fetchHeatVulnerability({
        geometry: payload.geometry,
        census_layer_id: "census-2022-100m-planegg",
        lst_layer_id: payload.lstLayerId ?? null,
        ndvi_layer_id: payload.ndviLayerId ?? null,
      });
      return response.result;
    },
  });
  const treeStatistics = useMutation<TreeStatisticsResult, Error, { geometry: { type: "Polygon"; coordinates: number[][][] } }>({
    mutationFn: async (payload) => {
      const response = await fetchTreeStatistics({
        geometry: payload.geometry,
        layer_id: "trees-3d-planegg",
      });
      return response.result;
    },
  });
  const landUseComposition = useMutation<LandUseCompositionResult, Error, { geometry: { type: "Polygon"; coordinates: number[][][] } }>({
    mutationFn: async (payload) => {
      const response = await fetchLandUseComposition({
        geometry: payload.geometry,
        layer_id: "nutzung-planegg",
        category_field: "nutzart",
      });
      return response.result;
    },
  });
  const drawnHeatSeriesStatistics = useMutation<AreaStatisticsResponse, Error, { geometry: DrawnPolygonGeometry; layer_ids: string[] }>({
    mutationFn: fetchAreaStatistics,
  });
  const drawnLulcSeriesStatistics = useMutation<AreaStatisticsResponse, Error, { geometry: DrawnPolygonGeometry; layer_ids: string[] }>({
    mutationFn: fetchAreaStatistics,
  });
  const changeDetection = useMutation<ChangeDetectionResponse, Error, { from_layer_id: string; to_layer_id: string }>({
    mutationFn: (payload) => fetchChangeDetection({ from_layer_id: payload.from_layer_id, to_layer_id: payload.to_layer_id }),
    onSuccess: (response, variables) => {
      const key = `${variables.from_layer_id}__${variables.to_layer_id}`;
      changeDetectionCacheRef.current[key] = response.result;
      setChangeDetectionResult(response.result);
    },
  });

  function applyComparisonLayer(layerId: string, visible: boolean, opacity: number) {
    setOverrides((prev) => ({
      ...prev,
      [layerId]: {
        ...prev[layerId],
        default_visible: visible,
        default_opacity: opacity,
      },
    }));
  }

  function handleToggleFromLulc(visible: boolean) {
    setFromLulcVisible(visible);
    if (!fromYearPoint?.layerId) return;
    applyComparisonLayer(fromYearPoint.layerId, visible, fromLulcOpacity);
  }

  function handleToggleToLulc(visible: boolean) {
    setToLulcVisible(visible);
    if (!toYearPoint?.layerId) return;
    applyComparisonLayer(toYearPoint.layerId, visible, toLulcOpacity);
  }

  function handleFromLulcOpacity(opacity: number) {
    setFromLulcOpacity(opacity);
    if (!fromLulcVisible || !fromYearPoint?.layerId) return;
    applyComparisonLayer(fromYearPoint.layerId, true, opacity);
  }

  function handleToLulcOpacity(opacity: number) {
    setToLulcOpacity(opacity);
    if (!toLulcVisible || !toYearPoint?.layerId) return;
    applyComparisonLayer(toYearPoint.layerId, true, opacity);
  }

  function handleToggleFromRgb(visible: boolean) {
    setFromRgbVisible(visible);
    if (!fromYearRgbOption?.layerId) return;
    setOverrides((prev) => {
      const next = { ...prev };
      if (visible) {
        for (const layerId of rgbLayerIds) {
          next[layerId] = { ...next[layerId], default_visible: false };
        }
      }
      next[fromYearRgbOption.layerId] = {
        ...next[fromYearRgbOption.layerId],
        default_visible: visible,
        default_opacity: fromRgbOpacity,
      };
      if (visible && toRgbVisible && toYearRgbOption?.layerId) {
        next[toYearRgbOption.layerId] = {
          ...next[toYearRgbOption.layerId],
          default_visible: true,
          default_opacity: toRgbOpacity,
        };
      }
      return next;
    });
  }

  function handleToggleToRgb(visible: boolean) {
    setToRgbVisible(visible);
    if (!toYearRgbOption?.layerId) return;
    setOverrides((prev) => {
      const next = { ...prev };
      if (visible) {
        for (const layerId of rgbLayerIds) {
          next[layerId] = { ...next[layerId], default_visible: false };
        }
      }
      next[toYearRgbOption.layerId] = {
        ...next[toYearRgbOption.layerId],
        default_visible: visible,
        default_opacity: toRgbOpacity,
      };
      if (visible && fromRgbVisible && fromYearRgbOption?.layerId) {
        next[fromYearRgbOption.layerId] = {
          ...next[fromYearRgbOption.layerId],
          default_visible: true,
          default_opacity: fromRgbOpacity,
        };
      }
      return next;
    });
  }

  function handleFromRgbOpacity(opacity: number) {
    setFromRgbOpacity(opacity);
    if (!fromRgbVisible || !fromYearRgbOption?.layerId) return;
    applyComparisonLayer(fromYearRgbOption.layerId, true, opacity);
  }

  function handleToRgbOpacity(opacity: number) {
    setToRgbOpacity(opacity);
    if (!toRgbVisible || !toYearRgbOption?.layerId) return;
    applyComparisonLayer(toYearRgbOption.layerId, true, opacity);
  }

  function resetComparisonYearLayers() {
    setFromLulcVisible(false);
    setToLulcVisible(false);
    setFromRgbVisible(false);
    setToRgbVisible(false);
    setOverrides((prev) => {
      const next = { ...prev };
      next[LEGACY_LULC_LAYER_ID] = { ...next[LEGACY_LULC_LAYER_ID], default_visible: false };
      for (const layerId of lulcLayerIds) {
        next[layerId] = { ...next[layerId], default_visible: false };
      }
      for (const layerId of rgbLayerIds) {
        next[layerId] = { ...next[layerId], default_visible: false };
      }
      return next;
    });
  }

  const layers = useMemo(() => {
    if (!catalogLayers) return [];
    return catalogLayers.map((layer) => ({ ...layer, ...overrides[layer.id] }));
  }, [catalogLayers, overrides]);

  const availableCatalogLayers = useMemo(() => (catalogLayers ?? []).filter((layer) => layer.available), [catalogLayers]);

  const inspectableRasterLayers = useMemo(
    () => layers.filter((layer) => layer.layer_type === "raster" && layer.default_visible && layer.available),
    [layers],
  );

  const overviewLayerIds = useMemo(
    () =>
      availableCatalogLayers
        .filter((layer) => layer.layer_type === "raster" && layer.inspectable)
        .map((layer) => layer.id),
    [availableCatalogLayers],
  );

  const legendLayers = useMemo(
    () =>
      layers
        .filter((layer) => layer.default_visible && layer.available)
        .filter((layer) => !(layer.value_type === "rgb" || layer.style?.color_scale === "rgb"))
        .filter(
          (layer) =>
            layer.layer_type === "raster" ||
            (layer.layer_type === "vector" && (layer.style?.color_scale === "population" || layer.style?.color_scale === "nutzung")),
        ),
    [layers],
  );

  useEffect(() => {
    const visible = layers
      .filter((layer) => layer.default_visible && layer.available)
      .sort((a, b) => b.default_order - a.default_order)
      .map((layer) => layer.id);

    setActiveLayerOrder((prev) => {
      const kept = prev.filter((id) => visible.includes(id));
      const added = visible.filter((id) => !kept.includes(id));
      // Newly visible layers should always appear on top.
      const next = [...added, ...kept];
      if (next.length === prev.length && next.every((id, i) => id === prev[i])) return prev;
      return next;
    });
  }, [layers]);

  const activeLayers = useMemo(() => {
    const visibleMap = new Map(
      layers
        .filter((layer) => layer.default_visible && layer.available)
        .map((layer) => [layer.id, layer] as const),
    );
    const ordered = activeLayerOrder
      .map((id) => visibleMap.get(id))
      .filter((layer): layer is CatalogLayer => Boolean(layer));
    const remaining = [...visibleMap.values()].filter((layer) => !activeLayerOrder.includes(layer.id));
    remaining.sort((a, b) => b.default_order - a.default_order);
    return [...ordered, ...remaining];
  }, [layers, activeLayerOrder]);

  const censusVisible = useMemo(
    () => layers.some((layer) => layer.id === "census-2022-100m-planegg" && layer.default_visible && layer.available),
    [layers],
  );
  const censusAvailable = useMemo(
    () => availableCatalogLayers.some((layer) => layer.id === "census-2022-100m-planegg"),
    [availableCatalogLayers],
  );
  const lstVisible = useMemo(
    () => layers.some((layer) => layer.id === "lst-planegg" && layer.default_visible && layer.available),
    [layers],
  );
  const lstAvailable = useMemo(
    () => availableCatalogLayers.some((layer) => layer.id === "lst-planegg"),
    [availableCatalogLayers],
  );
  const ndviVisible = useMemo(
    () => layers.some((layer) => layer.id === "ndvi-planegg" && layer.default_visible && layer.available),
    [layers],
  );
  const ndviAvailable = useMemo(
    () => availableCatalogLayers.some((layer) => layer.id === "ndvi-planegg"),
    [availableCatalogLayers],
  );
  const buildingsVisible = useMemo(
    () => layers.some((layer) => layer.id === "buildings-3d-planegg" && layer.default_visible && layer.available),
    [layers],
  );
  const buildingsAvailable = useMemo(
    () => availableCatalogLayers.some((layer) => layer.id === "buildings-3d-planegg"),
    [availableCatalogLayers],
  );
  const treesAvailable = useMemo(
    () => availableCatalogLayers.some((layer) => layer.id === "trees-3d-planegg"),
    [availableCatalogLayers],
  );
  const nutzungVisible = useMemo(
    () => layers.some((layer) => layer.id === "nutzung-planegg" && layer.default_visible && layer.available),
    [layers],
  );
  const nutzungAvailable = useMemo(
    () => availableCatalogLayers.some((layer) => layer.id === "nutzung-planegg"),
    [availableCatalogLayers],
  );

  const visibleRasterLayerIds = useMemo(
    () =>
      layers
        .filter((layer) => layer.layer_type === "raster" && layer.default_visible && layer.available)
        .map((layer) => layer.id),
    [layers],
  );

  const layerComparisonCandidates = useMemo(
    () => layers.filter((layer) => layer.layer_type === "raster" && layer.available),
    [layers],
  );

  useEffect(() => {
    if (layerComparisonCandidates.length === 0) return;
    if (!layerCompareLeftId || !layerComparisonCandidates.some((layer) => layer.id === layerCompareLeftId)) {
      setLayerCompareLeftId(layerComparisonCandidates[0].id);
    }
    if (!layerCompareRightId || !layerComparisonCandidates.some((layer) => layer.id === layerCompareRightId)) {
      setLayerCompareRightId(layerComparisonCandidates[Math.min(1, layerComparisonCandidates.length - 1)]?.id ?? layerComparisonCandidates[0].id);
    }
  }, [layerComparisonCandidates, layerCompareLeftId, layerCompareRightId]);

  const layerCompareLeftLabel = useMemo(
    () => layerComparisonCandidates.find((layer) => layer.id === layerCompareLeftId)?.short_title
      ?? layerComparisonCandidates.find((layer) => layer.id === layerCompareLeftId)?.title
      ?? "Left",
    [layerComparisonCandidates, layerCompareLeftId],
  );

  const layerCompareRightLabel = useMemo(
    () => layerComparisonCandidates.find((layer) => layer.id === layerCompareRightId)?.short_title
      ?? layerComparisonCandidates.find((layer) => layer.id === layerCompareRightId)?.title
      ?? "Right",
    [layerComparisonCandidates, layerCompareRightId],
  );

  const layerCompareAvailable = useMemo(
    () => Boolean(layerCompareLeftId && layerCompareRightId && layerCompareLeftId !== layerCompareRightId),
    [layerCompareLeftId, layerCompareRightId],
  );

  const layerCompareLeftOpacity = useMemo(
    () => (layerCompareLeftId ? (layers.find((layer) => layer.id === layerCompareLeftId)?.default_opacity ?? 1) : 1),
    [layers, layerCompareLeftId],
  );

  const layerCompareRightOpacity = useMemo(
    () => (layerCompareRightId ? (layers.find((layer) => layer.id === layerCompareRightId)?.default_opacity ?? 1) : 1),
    [layers, layerCompareRightId],
  );

  function activateLayerOnTop(layerId: string, opacity?: number) {
    setActiveLayerOrder((prev) => [layerId, ...prev.filter((id) => id !== layerId)]);
    setOverrides((prev) => ({
      ...prev,
      [layerId]: {
        ...prev[layerId],
        default_visible: true,
        ...(opacity !== undefined ? { default_opacity: opacity } : {}),
      },
    }));
  }

  function handleEnableLayerComparison(enabled: boolean) {
    if (enabled && layerCompareLeftId && layerCompareRightId) {
      activateLayerOnTop(layerCompareRightId, 1);
      activateLayerOnTop(layerCompareLeftId, 1);
    }
    setLayerCompareEnabled(enabled);
  }

  const lstPalette = useMemo(
    () => layers.find((layer) => layer.id === "lst-planegg")?.legend?.palette ?? ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#fee090", "#fdae61", "#f46d43", "#d73027"],
    [layers],
  );
  const ndviPalette = useMemo(
    () => layers.find((layer) => layer.id === "ndvi-planegg")?.legend?.palette ?? ["#8B4513", "#d73027", "#fee08b", "#ffffbf", "#a6d96a", "#1a9850", "#00441b"],
    [layers],
  );

  const relativeSummerLayerIds = useMemo(
    () =>
      new Set(
        (relativeSummerLstSeries.data?.points ?? [])
          .filter((point) => point.available)
          .map((point) => point.layer_id),
      ),
    [relativeSummerLstSeries.data?.points],
  );
  const relativeSummerLayerIdsList = useMemo(() => [...relativeSummerLayerIds].sort(), [relativeSummerLayerIds]);

  const lulcAreaByLayerId = useMemo(() => {
    const byLayer = new Map<string, { builtAreaHectares?: number | null; totalAreaHectares?: number | null; classAreas?: Record<string, number> | null }>();
    for (const point of lulcChangeSeries.data?.points ?? []) {
      byLayer.set(point.layer_id, {
        builtAreaHectares: point.built_area_hectares,
        totalAreaHectares: point.total_area_hectares,
        classAreas: point.class_areas_hectares,
      });
    }
    return byLayer;
  }, [lulcChangeSeries.data?.points]);

  const lulcYearPoints = useMemo<LulcYearPoint[]>(() => {
    const candidates = availableCatalogLayers.filter((layer) =>
      layer.layer_type === "raster" &&
      (
        layer.temporal_group === "lulc_yearly" ||
        /^lulc-planegg-\d{4}$/.test(layer.id)
      ) &&
      layer.id !== LEGACY_LULC_LAYER_ID,
    );

    const withYear = candidates.flatMap((layer) => {
        const byTemporalYear = layer.temporal_year;
        const byAcquisition = layer.acquisition_date && layer.acquisition_date.length >= 4
          ? Number(layer.acquisition_date.slice(0, 4))
          : NaN;
        const year = typeof byTemporalYear === "number" ? byTemporalYear : (Number.isFinite(byAcquisition) ? byAcquisition : null);
        if (year === null) return [];
        return [{
          year,
          layerId: layer.id,
          title: layer.short_title ?? layer.title,
          available: layer.available,
          builtAreaHectares: lulcAreaByLayerId.get(layer.id)?.builtAreaHectares ?? null,
          totalAreaHectares: lulcAreaByLayerId.get(layer.id)?.totalAreaHectares ?? null,
          classValues: lulcAreaByLayerId.get(layer.id)?.classAreas ?? null,
        } satisfies LulcYearPoint];
      });

    return withYear.sort((a, b) => a.year - b.year);
  }, [availableCatalogLayers, lulcAreaByLayerId]);

  const lulcLayerIds = useMemo(() => new Set(lulcYearPoints.map((point) => point.layerId)), [lulcYearPoints]);
  const lulcLayerIdsList = useMemo(() => [...lulcLayerIds].sort(), [lulcLayerIds]);

  const lulcClassSeries = useMemo<LulcClassSeries[]>(() => {
    const referenceLayerId = selectedLulcLayerId ?? lulcYearPoints.find((point) => point.available)?.layerId ?? lulcYearPoints[0]?.layerId;
    if (!referenceLayerId) return [];
    const referenceLayer = availableCatalogLayers.find((layer) => layer.id === referenceLayerId);
    const labels = referenceLayer?.legend?.labels ?? [];
    const palette = referenceLayer?.legend?.palette ?? [];
    return labels.map((label, index) => ({ classKey: String(index), label, color: palette[index] ?? "#94a3b8" }));
  }, [availableCatalogLayers, lulcYearPoints, selectedLulcLayerId]);

  const rgbYearOptions = useMemo(() => {
    const optionsByYear = new Map<number, { layerId: string; title: string; available: boolean }>();
    const rgbCandidates = availableCatalogLayers.filter((layer) =>
      layer.layer_type === "raster" &&
      layer.value_type === "rgb" &&
      (
        layer.temporal_group === "rgb_yearly" ||
        layer.tags?.includes("sentinel-2") ||
        layer.tags?.includes("sentinel-rgb") ||
        layer.source?.toLowerCase().includes("sentinel-2")
      ) &&
      (layer.temporal_year !== undefined || (layer.acquisition_date && layer.acquisition_date.length >= 4)),
    );
    for (const layer of rgbCandidates) {
      const temporalYear = typeof layer.temporal_year === "number"
        ? layer.temporal_year
        : Number(layer.acquisition_date?.slice(0, 4));
      if (!Number.isFinite(temporalYear)) continue;
      optionsByYear.set(Number(temporalYear), {
        layerId: layer.id,
        title: layer.short_title ?? layer.title,
        available: layer.available,
      });
    }
    return optionsByYear;
  }, [availableCatalogLayers]);

  const rgbLayerIds = useMemo(() => new Set([...rgbYearOptions.values()].map((item) => item.layerId)), [rgbYearOptions]);
  const fromYearPoint = useMemo(
    () => (lulcYearRange.fromYear ? lulcYearPoints.find((point) => point.year === lulcYearRange.fromYear) ?? null : null),
    [lulcYearPoints, lulcYearRange.fromYear],
  );
  const toYearPoint = useMemo(
    () => (lulcYearRange.toYear ? lulcYearPoints.find((point) => point.year === lulcYearRange.toYear) ?? null : null),
    [lulcYearPoints, lulcYearRange.toYear],
  );
  const fromYearRgbOption = useMemo(
    () => (lulcYearRange.fromYear ? rgbYearOptions.get(lulcYearRange.fromYear) ?? null : null),
    [lulcYearRange.fromYear, rgbYearOptions],
  );
  const toYearRgbOption = useMemo(
    () => (lulcYearRange.toYear ? rgbYearOptions.get(lulcYearRange.toYear) ?? null : null),
    [lulcYearRange.toYear, rgbYearOptions],
  );
  const hasSelectedChangePair = useMemo(
    () => Boolean(fromYearPoint?.available && toYearPoint?.available && fromYearPoint.year !== toYearPoint.year),
    [fromYearPoint, toYearPoint],
  );
  const activeChangeResult = changeDetectionResult;

  const swipeLayerChoiceEntries = useMemo(
    () => [
      { key: "from-rgb" as const, label: `From RGB (${fromYearRgbOption?.title ?? "not available"})`, layerId: fromYearRgbOption?.layerId ?? null },
      { key: "to-rgb" as const, label: `To RGB (${toYearRgbOption?.title ?? "not available"})`, layerId: toYearRgbOption?.layerId ?? null },
      { key: "from-lulc" as const, label: `From LULC (${fromYearPoint?.title ?? "not available"})`, layerId: fromYearPoint?.layerId ?? null },
      { key: "to-lulc" as const, label: `To LULC (${toYearPoint?.title ?? "not available"})`, layerId: toYearPoint?.layerId ?? null },
    ],
    [fromYearRgbOption?.title, fromYearRgbOption?.layerId, toYearRgbOption?.title, toYearRgbOption?.layerId, fromYearPoint?.title, fromYearPoint?.layerId, toYearPoint?.title, toYearPoint?.layerId],
  );

  function resolveSwipeLayerId(selection: SwipeLayerSelection): string | null {
    if (selection === "from-rgb") return fromYearRgbOption?.layerId ?? null;
    if (selection === "to-rgb") return toYearRgbOption?.layerId ?? null;
    if (selection === "from-lulc") return fromYearPoint?.layerId ?? null;
    return toYearPoint?.layerId ?? null;
  }

  const swipeLeftLayerId = useMemo(() => resolveSwipeLayerId(swipeLeftSelection), [swipeLeftSelection, fromYearRgbOption?.layerId, toYearRgbOption?.layerId, fromYearPoint?.layerId, toYearPoint?.layerId]);
  const swipeRightLayerId = useMemo(() => resolveSwipeLayerId(swipeRightSelection), [swipeRightSelection, fromYearRgbOption?.layerId, toYearRgbOption?.layerId, fromYearPoint?.layerId, toYearPoint?.layerId]);

  function ensureSwipeSelectionVisible(selection: SwipeLayerSelection) {
    if (selection === "from-rgb") {
      handleToggleFromRgb(true);
      return;
    }
    if (selection === "to-rgb") {
      handleToggleToRgb(true);
      return;
    }
    if (selection === "from-lulc") {
      handleToggleFromLulc(true);
      return;
    }
    handleToggleToLulc(true);
  }

  const swipeAvailable = useMemo(
    () => Boolean(swipeLeftLayerId && swipeRightLayerId && swipeLeftLayerId !== swipeRightLayerId),
    [swipeLeftLayerId, swipeRightLayerId],
  );

  const swipeLeftLabel = useMemo(
    () => swipeLayerChoiceEntries.find((entry) => entry.key === swipeLeftSelection)?.label ?? "none",
    [swipeLayerChoiceEntries, swipeLeftSelection],
  );
  const swipeRightLabel = useMemo(
    () => swipeLayerChoiceEntries.find((entry) => entry.key === swipeRightSelection)?.label ?? "none",
    [swipeLayerChoiceEntries, swipeRightSelection],
  );

  const layerTitleById = useMemo(() => {
    const map = new Map<string, string>();
    for (const layer of availableCatalogLayers) {
      map.set(layer.id, layer.short_title ?? layer.title);
    }
    return map;
  }, [availableCatalogLayers]);

  const swipeLeftDividerLabel = useMemo(
    () => (swipeLeftLayerId ? layerTitleById.get(swipeLeftLayerId) ?? swipeLeftLayerId : "Left"),
    [swipeLeftLayerId, layerTitleById],
  );

  const swipeRightDividerLabel = useMemo(
    () => (swipeRightLayerId ? layerTitleById.get(swipeRightLayerId) ?? swipeRightLayerId : "Right"),
    [swipeRightLayerId, layerTitleById],
  );

  const effectiveSwipeEnabled = dashboardMode === "land-cover-change"
    ? (swipeEnabled && swipeAvailable)
    : (layerCompareEnabled && layerCompareAvailable);
  const effectiveSwipePosition = dashboardMode === "land-cover-change" ? swipePosition : layerComparePosition;
  const effectiveSwipeLeftLayerId = dashboardMode === "land-cover-change" ? swipeLeftLayerId : layerCompareLeftId;
  const effectiveSwipeRightLayerId = dashboardMode === "land-cover-change" ? swipeRightLayerId : layerCompareRightId;
  const effectiveSwipeLeftLabel = dashboardMode === "land-cover-change" ? swipeLeftDividerLabel : layerCompareLeftLabel;
  const effectiveSwipeRightLabel = dashboardMode === "land-cover-change" ? swipeRightDividerLabel : layerCompareRightLabel;

  const heatStatsByLayerId = useMemo(() => {
    const byLayer = new Map<string, LayerAreaStatistics>();
    for (const result of drawnHeatSeriesStatistics.data?.results ?? []) {
      byLayer.set(result.layer_id, result);
    }
    return byLayer;
  }, [drawnHeatSeriesStatistics.data?.results]);

  const relativeSummerPointsForScope = useMemo<RelativeSummerLstPoint[]>(() => {
    const points = relativeSummerLstSeries.data?.points ?? [];
    if (timeSeriesScope !== "drawn" || !hasDrawnSelection) return points;
    return points.map((point) => {
      const stats = heatStatsByLayerId.get(point.layer_id);
      if (!stats) return point;
      const drawnAnomaly = stats.selected.mean;
      const absolute = point.mean_scene_lst_deg_c !== null && point.mean_scene_lst_deg_c !== undefined
        ? point.mean_scene_lst_deg_c + drawnAnomaly
        : null;
      return {
        ...point,
        mean_anomaly_deg_c: drawnAnomaly,
        mean_scene_lst_deg_c: absolute,
      };
    });
  }, [relativeSummerLstSeries.data?.points, timeSeriesScope, hasDrawnSelection, heatStatsByLayerId]);

  const lulcStatsByLayerId = useMemo(() => {
    const byLayer = new Map<string, LayerAreaStatistics>();
    for (const result of drawnLulcSeriesStatistics.data?.results ?? []) {
      byLayer.set(result.layer_id, result);
    }
    return byLayer;
  }, [drawnLulcSeriesStatistics.data?.results]);

  const lulcPointsForScope = useMemo<LulcYearPoint[]>(() => {
    if (timeSeriesScope !== "drawn" || !hasDrawnSelection) return lulcYearPoints;
    return lulcYearPoints.map((point) => {
      const stats = lulcStatsByLayerId.get(point.layerId);
      if (!stats?.selected.class_breakdown?.length) return point;
      const classValues = Object.fromEntries(
        stats.selected.class_breakdown.map((entry) => [String(entry.class_index), entry.percentage]),
      );
      return {
        ...point,
        classValues,
        builtAreaHectares: classValues["6"] ?? null,
        totalAreaHectares: 100,
      };
    });
  }, [lulcYearPoints, timeSeriesScope, hasDrawnSelection, lulcStatsByLayerId]);

  useEffect(() => {
    if (hasAutoSelectedSeriesRef.current || selectedSeriesLayerId) return;
    const points = relativeSummerLstSeries.data?.points ?? [];
    const latestAvailable = points.filter((point) => point.available).sort((a, b) => b.year - a.year)[0];
    if (!latestAvailable) return;
    setSelectedSeriesLayerId(latestAvailable.layer_id);
    hasAutoSelectedSeriesRef.current = true;
  }, [relativeSummerLstSeries.data?.points, selectedSeriesLayerId]);

  useEffect(() => {
    if (selectedLulcLayerId) return;
    const latest = [...lulcYearPoints].reverse().find((point) => point.available);
    if (!latest) return;
    setSelectedLulcLayerId(latest.layerId);
  }, [lulcYearPoints, selectedLulcLayerId]);

  function handleSelectRelativeSummerPoint(point: RelativeSummerLstPoint) {
    if (!point.available) return;

    if (selectedSeriesLayerId === point.layer_id) {
      setSelectedSeriesLayerId(null);
      setOverrides((prev) => {
        const next = { ...prev };
        for (const layerId of relativeSummerLayerIds) {
          next[layerId] = {
            ...next[layerId],
            default_visible: false,
          };
        }
        return next;
      });
      return;
    }

    setSelectedSeriesLayerId(point.layer_id);
    setOverrides((prev) => {
      const next = { ...prev };
      next["lst-planegg"] = { ...next["lst-planegg"], default_visible: false };
      for (const layerId of relativeSummerLayerIds) {
        next[layerId] = {
          ...next[layerId],
          default_visible: layerId === point.layer_id,
          default_opacity: layerId === point.layer_id ? 0.85 : (next[layerId]?.default_opacity ?? 0.75),
        };
      }
      return next;
    });
  }

  function handleSelectLulcPoint(point: LulcYearPoint) {
    if (!point.available) return;
    setSelectedLulcLayerId(point.layerId);
    setChangeDetectionVisible(false);
    const rgbForYear = rgbYearOptions.get(point.year) ?? null;
    if (!rgbForYear || rgbForYear.layerId !== selectedRgbLayerId) {
      setSelectedRgbLayerId(null);
    }
    setOverrides((prev) => {
      const next = { ...prev };
      next[LEGACY_LULC_LAYER_ID] = { ...next[LEGACY_LULC_LAYER_ID], default_visible: false };
      for (const layerId of lulcLayerIds) {
        next[layerId] = {
          ...next[layerId],
          default_visible: layerId === point.layerId,
          default_opacity: layerId === point.layerId ? toLulcOpacity : (next[layerId]?.default_opacity ?? 0.8),
        };
      }
      if (!rgbForYear || rgbForYear.layerId !== selectedRgbLayerId) {
        for (const rgbLayerId of rgbLayerIds) {
          next[rgbLayerId] = {
            ...next[rgbLayerId],
            default_visible: false,
          };
        }
      }
      return next;
    });
  }

  useEffect(() => {
    if (dashboardMode !== "heat-development") return;
    if (!selectedSeriesLayerId) return;
    const selectedPoint = (relativeSummerLstSeries.data?.points ?? []).find((point) => point.layer_id === selectedSeriesLayerId && point.available);
    if (!selectedPoint) return;
    const layer = layers.find((item) => item.id === selectedSeriesLayerId);
    if (layer?.default_visible) return;
    handleSelectRelativeSummerPoint(selectedPoint);
  }, [dashboardMode, selectedSeriesLayerId, relativeSummerLstSeries.data?.points, layers]);

  useEffect(() => {
    let active = true;
    fetchJson<{ features: Array<{ properties?: Record<string, unknown> }> }>("/api/vectors/buildings-3d-planegg")
      .then((fc) => {
        if (!active) return;
        const heights = fc.features
          .map((f) => extractBuildingHeight((f.properties ?? {}) as Record<string, unknown>))
          .filter((v) => Number.isFinite(v) && v > 0)
          .sort((a, b) => a - b);
        setAllBuildingHeights(heights);
      })
      .catch(() => {
        if (active) setAllBuildingHeights([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function loadOverview() {
      if (overviewLayerIds.length === 0 && !censusAvailable && !treesAvailable && !buildingsAvailable && !nutzungAvailable) {
        if (!active) return;
        setOverviewResults([]);
        setOverviewBuildingStats(null);
        setOverviewVulnerability(null);
        setOverviewTreeStats(null);
        setOverviewLandUse(null);
        setOverviewPending(false);
        return;
      }

      setOverviewPending(true);
      setOverviewError(null);
      try {
        const [boundaryFc, buildingsFc] = await Promise.all([
          fetchJson<{ features: Array<{ geometry: { type: "Polygon"; coordinates: number[][][] } }> }>("/api/vectors/planegg-boundary"),
          fetchJson<{ features: Array<{ properties?: Record<string, unknown> }> }>("/api/vectors/buildings-3d-planegg"),
        ]);

        const boundary = boundaryFc.features[0]?.geometry;
        if (!boundary) throw new Error("Boundary geometry unavailable.");

        const stats = overviewLayerIds.length > 0
          ? await fetchAreaStatistics({
              geometry: boundary,
              layer_ids: overviewLayerIds,
            })
          : { results: [] };

        const vulnerability = censusAvailable
          ? await fetchHeatVulnerability({
              geometry: boundary,
              census_layer_id: "census-2022-100m-planegg",
              lst_layer_id: lstAvailable ? "lst-planegg" : null,
              ndvi_layer_id: ndviAvailable ? "ndvi-planegg" : null,
            })
          : null;

        const treeStats = treesAvailable
          ? await fetchTreeStatistics({
              geometry: boundary,
              layer_id: "trees-3d-planegg",
            })
          : null;

        const landUse = nutzungAvailable
          ? await fetchLandUseComposition({
              geometry: boundary,
              layer_id: "nutzung-planegg",
              category_field: "nutzart",
            })
          : null;

        const buildingsOverviewIds = overviewLayerIds.filter((id) => id === "ndvi-planegg" || id === "lst-planegg");
        const buildingsOverview = buildingsAvailable
          ? await fetchBuildingsOverview({
              layer_ids: buildingsOverviewIds,
              buildings_layer_id: "buildings-3d-planegg",
            })
          : { results: [] };

        const heights = buildingsFc.features
          .map((feature) => extractBuildingHeight((feature.properties ?? {}) as Record<string, unknown>))
          .filter((value) => Number.isFinite(value) && value > 0);

        if (!active) return;
        setOverviewResults(stats.results);
        setOverviewVulnerability(vulnerability?.result ?? null);
        setOverviewTreeStats(treeStats?.result ?? null);
        setOverviewLandUse(landUse?.result ?? null);
        setOverviewBuildingClimate(buildingsOverview.results);
        setOverviewBuildingStats(
          buildingsAvailable
            ? {
                count: buildingsFc.features.length,
                averageHeight: heights.length > 0 ? heights.reduce((sum, h) => sum + h, 0) / heights.length : 0,
              }
            : null,
        );
      } catch (err) {
        if (!active) return;
        setOverviewError(err instanceof Error ? err : new Error("Failed to load area overview"));
      } finally {
        if (active) setOverviewPending(false);
      }
    }

    void loadOverview();
    return () => {
      active = false;
    };
  }, [overviewLayerIds, censusAvailable, lstAvailable, ndviAvailable, treesAvailable, buildingsAvailable, nutzungAvailable]);

  useEffect(() => {
    let active = true;
    let retryTimer: number | null = null;

    const scheduleRetry = (delayMs: number, attempt: number) => {
      retryTimer = window.setTimeout(() => {
        loadStatus(attempt + 1);
      }, delayMs);
    };

    const loadStatus = (attempt: number) => {
      fetchJson<{ available: boolean; sources?: Partial<Record<TerrainSourceId, boolean>> }>(`/api/terrain/status?source=${terrainSource}`)
        .then((payload) => {
          if (!active) return;
          setTerrainAvailable(Boolean(payload.available));
          setTerrainSourcesAvailable({
            dem: Boolean(payload.sources?.dem),
            dom: Boolean(payload.sources?.dom),
            dsm: Boolean(payload.sources?.dsm),
          });
        })
        .catch(() => {
          if (!active) return;
          // Keep last known values to avoid disabling the toggle because of transient
          // startup/network issues. Retry with a capped backoff.
          if (attempt < 6) {
            const delayMs = Math.min(5000, 850 * (attempt + 1));
            scheduleRetry(delayMs, attempt);
          }
        });
    };

    loadStatus(0);

    return () => {
      active = false;
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [terrainSource]);

  useEffect(() => {
    if (terrainSource === "dem" && !terrainSourcesAvailable.dem) {
      if (terrainSourcesAvailable.dom) setTerrainSource("dom");
      else if (terrainSourcesAvailable.dsm) setTerrainSource("dsm");
    }
    if (terrainSource === "dom" && !terrainSourcesAvailable.dom) {
      if (terrainSourcesAvailable.dem) setTerrainSource("dem");
      else if (terrainSourcesAvailable.dsm) setTerrainSource("dsm");
    }
    if (terrainSource === "dsm" && !terrainSourcesAvailable.dsm) {
      if (terrainSourcesAvailable.dem) setTerrainSource("dem");
      else if (terrainSourcesAvailable.dom) setTerrainSource("dom");
    }
  }, [terrainSource, terrainSourcesAvailable]);

  function handleToggleVisibility(id: string) {
    const current = layers.find((layer) => layer.id === id);
    const currentVisible = current?.default_visible ?? false;
    const nextVisible = !currentVisible;

    if (nextVisible) {
      activateLayerOnTop(id);
    } else {
      setOverrides((prev) => ({
        ...prev,
        [id]: { ...prev[id], default_visible: false },
      }));
      setActiveLayerOrder((prev) => prev.filter((layerId) => layerId !== id));
    }

    const toggledLayer = layers.find((layer) => layer.id === id);
    const isSwipeComparisonLayer = id === swipeLeftLayerId || id === swipeRightLayerId;
    if (swipeEnabled && toggledLayer?.layer_type === "raster" && !isSwipeComparisonLayer) {
      setSwipeEnabled(false);
    }
  }

  function handleOpacityChange(id: string, opacity: number) {
    setOverrides((prev) => ({ ...prev, [id]: { ...prev[id], default_opacity: opacity } }));
  }

  function handleToggleTerrain3d() {
    setTerrain3dEnabled((enabled) => {
      if (enabled) {
        setTerrainOffIntentVersion((version) => version + 1);
      }
      return !enabled;
    });
  }

  function handleResetVisibleLayers() {
    setOverrides((prev) => {
      const next = { ...prev };
      for (const layer of layers) {
        if (!layer.available || !layer.default_visible) continue;
        next[layer.id] = {
          ...next[layer.id],
          default_visible: false,
        };
      }
      return next;
    });
    setSwipeEnabled(false);
    setChangeDetectionVisible(false);
  }

  function handleMoveActiveLayer(layerId: string, direction: "up" | "down" | "top" | "bottom") {
    const ids = activeLayers.map((layer) => layer.id);
    const currentIndex = ids.indexOf(layerId);
    if (currentIndex < 0) return;

    const targetIndex =
      direction === "top"
        ? 0
        : direction === "bottom"
          ? ids.length - 1
          : direction === "up"
            ? currentIndex - 1
            : currentIndex + 1;
    if (targetIndex < 0 || targetIndex >= ids.length) return;

    const nextIds = [...ids];
    const [moved] = nextIds.splice(currentIndex, 1);
    nextIds.splice(targetIndex, 0, moved);

    setActiveLayerOrder(nextIds);
  }

  function handleReorderActiveLayersByDrop(draggedId: string, targetId: string) {
    if (!draggedId || !targetId || draggedId === targetId) return;
    const ids = activeLayers.map((layer) => layer.id);
    const fromIndex = ids.indexOf(draggedId);
    const toIndex = ids.indexOf(targetId);
    if (fromIndex < 0 || toIndex < 0) return;

    const nextIds = [...ids];
    const [moved] = nextIds.splice(fromIndex, 1);
    nextIds.splice(toIndex, 0, moved);

    setActiveLayerOrder(nextIds);
    setDraggingActiveLayerId(null);
    setActiveDropTargetId(null);
  }

  function handleMapClick(lngLat: [number, number]) {
    setSelectedNutzung(null);
    if (!drawMode) return;
    setDrawnPoints((prev) => [...prev, lngLat]);
  }

  function handleFinishDraw() {
    if (drawnPoints.length < 3) return;
    const ring = [...drawnPoints, drawnPoints[0]];
    const polygon: DrawnPolygonGeometry = { type: "Polygon", coordinates: [ring] };
    setDrawnGeometry(polygon);
    setHasDrawnSelection(true);
    setAnalysisView("drawn");
    setTimeSeriesScope("drawn");
    setDrawMode(false);
  }

  function handleClearDraw() {
    setDrawMode(false);
    setDrawnPoints([]);
    setDrawnGeometry(null);
    areaStatistics.reset();
    heatVulnerability.reset();
    treeStatistics.reset();
    drawnHeatSeriesStatistics.reset();
    drawnLulcSeriesStatistics.reset();
    setHasDrawnSelection(false);
    setAnalysisView("planegg");
    setTimeSeriesScope("planegg");
  }

  useEffect(() => {
    if (!hasDrawnSelection || !drawnGeometry) return;
    if (relativeSummerLayerIdsList.length > 0) {
      drawnHeatSeriesStatistics.mutate({ geometry: drawnGeometry, layer_ids: relativeSummerLayerIdsList });
    } else {
      drawnHeatSeriesStatistics.reset();
    }

    if (lulcLayerIdsList.length > 0) {
      drawnLulcSeriesStatistics.mutate({ geometry: drawnGeometry, layer_ids: lulcLayerIdsList });
    } else {
      drawnLulcSeriesStatistics.reset();
    }
  }, [hasDrawnSelection, drawnGeometry, relativeSummerLayerIdsList, lulcLayerIdsList]);

  useEffect(() => {
    if (!lulcYearRange.fromYear || !lulcYearRange.toYear || lulcYearRange.fromYear === lulcYearRange.toYear) {
      changeDetection.reset();
      setChangeDetectionResult(null);
      setSwipeEnabled(false);
      resetComparisonYearLayers();
      return;
    }
    const fromPoint = lulcYearPoints.find((p) => p.year === lulcYearRange.fromYear);
    const toPoint = lulcYearPoints.find((p) => p.year === lulcYearRange.toYear);
    if (!fromPoint?.available || !toPoint?.available) {
      changeDetection.reset();
      setChangeDetectionResult(null);
      setSwipeEnabled(false);
      resetComparisonYearLayers();
      return;
    }
    setChangeDetectionVisible(true);
    setSwipeLeftSelection("from-rgb");
    setSwipeRightSelection("to-rgb");
    setFromLulcVisible(false);
    setToLulcVisible(false);
    const hasFromRgb = Boolean(fromYearRgbOption?.layerId);
    const hasToRgb = Boolean(toYearRgbOption?.layerId);
    const useRgbPair = hasFromRgb && hasToRgb;
    setFromRgbVisible(hasFromRgb);
    setToRgbVisible(hasToRgb);
    setToLulcVisible(!useRgbPair);
    setSwipeEnabled(useRgbPair);
    setOverrides((prev) => {
      const next = { ...prev };
      next[LEGACY_LULC_LAYER_ID] = { ...next[LEGACY_LULC_LAYER_ID], default_visible: false };
      for (const layerId of lulcLayerIds) {
        next[layerId] = { ...next[layerId], default_visible: false };
      }
      for (const layerId of rgbLayerIds) {
        next[layerId] = { ...next[layerId], default_visible: false };
      }
      if (hasFromRgb && fromYearRgbOption?.layerId) {
        next[fromYearRgbOption.layerId] = {
          ...next[fromYearRgbOption.layerId],
          default_visible: true,
          default_opacity: fromRgbOpacity,
        };
      }
      if (hasToRgb && toYearRgbOption?.layerId) {
        next[toYearRgbOption.layerId] = {
          ...next[toYearRgbOption.layerId],
          default_visible: true,
          default_opacity: toRgbOpacity,
        };
      }
      if (!useRgbPair) {
        next[toPoint.layerId] = {
          ...next[toPoint.layerId],
          default_visible: true,
          default_opacity: toLulcOpacity,
        };
      }
      return next;
    });
    const key = `${fromPoint.layerId}__${toPoint.layerId}`;
    const cached = changeDetectionCacheRef.current[key];
    if (cached) {
      setChangeDetectionResult(cached);
      return;
    }
    setChangeDetectionResult(null);
    changeDetection.mutate({ from_layer_id: fromPoint.layerId, to_layer_id: toPoint.layerId });
  }, [lulcYearRange, lulcYearPoints, fromYearRgbOption?.layerId, toYearRgbOption?.layerId, fromRgbOpacity, toRgbOpacity]);

  useEffect(() => {
    if (swipeEnabled && !swipeAvailable) {
      setSwipeEnabled(false);
    }
  }, [swipeEnabled, swipeAvailable]);

  useEffect(() => {
    if (dashboardMode !== "land-cover-change" && swipeEnabled) {
      setSwipeEnabled(false);
    }
  }, [dashboardMode, swipeEnabled]);

  useEffect(() => {
    if (!terrain3dEnabled || effectiveTerrainMode !== "off") return;
    if (swipeEnabled) {
      setSwipeEnabled(false);
    }
  }, [terrain3dEnabled, swipeEnabled, effectiveTerrainMode]);

  useEffect(() => {
    if (!hasDrawnSelection || !drawnGeometry) return;

    areaStatistics.mutate({
      geometry: drawnGeometry,
      layer_ids: inspectableRasterLayers.map((layer) => layer.id),
    });

    if (censusVisible) {
      heatVulnerability.mutate({
        geometry: drawnGeometry,
        lstLayerId: lstVisible ? "lst-planegg" : null,
        ndviLayerId: ndviVisible ? "ndvi-planegg" : null,
      });
    } else {
      heatVulnerability.reset();
    }

    if (treesAvailable) {
      treeStatistics.mutate({ geometry: drawnGeometry });
    } else {
      treeStatistics.reset();
    }

    if (nutzungAvailable) {
      landUseComposition.mutate({ geometry: drawnGeometry });
    } else {
      landUseComposition.reset();
    }
  }, [
    hasDrawnSelection,
    drawnGeometry,
    inspectableRasterLayers,
    censusVisible,
    lstVisible,
    ndviVisible,
    treesAvailable,
    nutzungAvailable,
  ]);

  function handleBuildingClick(building: SelectedBuilding) {
    setSelectedNutzung(null);
    setSelectedBuilding(building);
    buildingContext.mutate({
      geometry: building.geometry,
      layer_ids: ["lst-planegg", "ndvi-planegg"],
    });
  }

  function handleNutzungClick(feature: SelectedNutzung) {
    setSelectedBuilding(null);
    buildingContext.reset();
    setSelectedNutzung(feature);
  }

  const selectedBuildingHeight = extractBuildingHeight(selectedBuilding?.properties as Record<string, unknown> | undefined);
  const heightPercentile = useMemo(() => {
    if (!selectedBuilding || allBuildingHeights.length === 0 || !Number.isFinite(selectedBuildingHeight)) return null;
    const belowOrEqual = allBuildingHeights.filter((h) => h <= selectedBuildingHeight).length;
    return (belowOrEqual / allBuildingHeights.length) * 100;
  }, [allBuildingHeights, selectedBuilding, selectedBuildingHeight]);

  const useDrawnView = analysisView === "drawn" && hasDrawnSelection;
  const analysisResults = useDrawnView ? areaStatistics.data?.results : overviewResults;
  const analysisPending = useDrawnView ? areaStatistics.isPending : overviewPending;
  const analysisError = useDrawnView ? areaStatistics.error : overviewError;
  const vulnerabilityResult = useDrawnView ? (heatVulnerability.data ?? null) : overviewVulnerability;
  const vulnerabilityPending = useDrawnView ? heatVulnerability.isPending : overviewPending;
  const vulnerabilityError = useDrawnView ? heatVulnerability.error : null;
  const treeStatsResult = useDrawnView ? (treeStatistics.data ?? null) : overviewTreeStats;
  const treeStatsPending = useDrawnView ? treeStatistics.isPending : overviewPending;
  const treeStatsError = useDrawnView ? treeStatistics.error : null;
  const landUseResult = useDrawnView ? (landUseComposition.data ?? null) : overviewLandUse;
  const landUsePending = useDrawnView ? landUseComposition.isPending : overviewPending;
  const landUseError = useDrawnView ? landUseComposition.error : null;
  const totalAreaHectares = landUseResult?.summary.selected_area_hectares ?? treeStatsResult?.area_hectares ?? null;

  if (isLoading) {
    return (
      <main className="flex h-screen w-screen items-center justify-center bg-[#05070d] text-slate-400">
        Loading layer catalog…
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex h-screen w-screen items-center justify-center bg-[#05070d] text-red-400">
        Failed to load layer catalog: {error.message}
      </main>
    );
  }

  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-[#05070d] text-slate-100">
      <header className="z-20 flex h-14 shrink-0 items-center justify-between border-b border-white/5 bg-[#05070d]/90 px-4 backdrop-blur-md">
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-cyan-300">Urban Climate Tool</h1>
          <p className="text-[11px] text-slate-500">Planegg · satellite-derived climate indicators</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-1 rounded-md border border-white/10 bg-white/5 p-1 sm:flex">
            <button
              type="button"
              onClick={() => setDashboardMode("analysis")}
              className={`rounded px-2 py-1 text-[11px] transition ${
                dashboardMode === "analysis" ? "bg-cyan-400/15 text-cyan-200" : "text-slate-300 hover:bg-white/10"
              }`}
            >
              Analysis
            </button>
            <button
              type="button"
              onClick={() => setDashboardMode("heat-development")}
              className={`rounded px-2 py-1 text-[11px] transition ${
                dashboardMode === "heat-development" ? "bg-cyan-400/15 text-cyan-200" : "text-slate-300 hover:bg-white/10"
              }`}
            >
              Heat Development
            </button>
            <button
              type="button"
              onClick={() => setDashboardMode("land-cover-change")}
              className={`rounded px-2 py-1 text-[11px] transition ${
                dashboardMode === "land-cover-change" ? "bg-cyan-400/15 text-cyan-200" : "text-slate-300 hover:bg-white/10"
              }`}
            >
              Land Cover Change
            </button>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={terrain3dEnabled}
            disabled={!hasAnyTerrainSource}
            onClick={handleToggleTerrain3d}
            className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[11px] font-medium transition ${
              hasAnyTerrainSource
                ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-200 hover:bg-cyan-400/15"
                : "cursor-not-allowed border-white/10 bg-white/5 text-slate-500"
            }`}
            title={hasAnyTerrainSource ? "Toggle 3D terrain mode" : "No terrain source available. Import DEM, DOM, or DSM first."}
          >
            <span
              className={`relative h-4 w-8 shrink-0 rounded-full transition ${
                terrain3dEnabled && hasAnyTerrainSource ? "bg-cyan-400" : "bg-slate-700"
              }`}
            >
              <span
                className={`absolute top-0.5 h-3 w-3 rounded-full bg-slate-950 transition ${
                  terrain3dEnabled && hasAnyTerrainSource ? "left-4" : "left-0.5"
                }`}
              />
            </span>
            3D Terrain
          </button>
          {terrain3dEnabled && hasAnyTerrainSource ? (
            <div className="hidden items-center gap-3 rounded-md border border-white/10 bg-white/5 px-2.5 py-1 sm:flex">
              <label className="flex items-center gap-2 text-[11px] text-slate-300">
                Model
                <select
                  value={terrainSource}
                  onChange={(event) => setTerrainSource(event.target.value as TerrainSourceId)}
                  className="rounded border border-white/10 bg-slate-900 px-1.5 py-0.5 text-[11px] text-slate-200"
                >
                  <option value="dem" disabled={!terrainSourcesAvailable.dem}>DEM</option>
                  <option value="dom" disabled={!terrainSourcesAvailable.dom}>DOM</option>
                  <option value="dsm" disabled={!terrainSourcesAvailable.dsm}>DSM</option>
                </select>
              </label>
              <label className="flex items-center gap-2 text-[11px] text-slate-300">
                Z-factor
                <input
                  type="range"
                  min={1}
                  max={3}
                  step={0.1}
                  value={domTerrainMode ? 1 : terrainExaggeration}
                  onChange={(event) => setTerrainExaggeration(Number(event.target.value))}
                  disabled={domTerrainMode}
                  className="w-20 accent-cyan-400"
                />
                <span className="w-8 text-right text-cyan-300">{(domTerrainMode ? 1 : terrainExaggeration).toFixed(1)}x</span>
              </label>
              <label className="flex items-center gap-2 text-[11px] text-slate-300">
                Hillshade
                <input
                  type="range"
                  min={0.2}
                  max={1.4}
                  step={0.1}
                  value={domTerrainMode ? 0 : hillshadeStrength}
                  onChange={(event) => setHillshadeStrength(Number(event.target.value))}
                  disabled={domTerrainMode}
                  className="w-20 accent-cyan-400"
                />
              </label>
            </div>
          ) : null}
          <BasemapSwitcher value={basemap} onChange={setBasemap} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <MapCanvas
            layers={layers}
            activeLayerOrder={activeLayers.map((layer) => layer.id)}
            apiBaseUrl={API_BASE_URL}
            drawMode={drawMode}
            drawnPoints={drawnPoints}
            onMapClick={handleMapClick}
            onBuildingClick={handleBuildingClick}
            onNutzungClick={handleNutzungClick}
            basemap={basemap}
            terrain3dEnabled={terrain3dEnabled}
            terrainSource={terrainSource}
            terrainAvailable={terrainAvailable}
            terrainSourcesAvailable={terrainSourcesAvailable}
            terrainExaggeration={domTerrainMode ? 1 : terrainExaggeration}
            terrainOffIntentVersion={terrainOffIntentVersion}
            onEffectiveTerrainModeChange={setEffectiveTerrainMode}
            hillshadeStrength={domTerrainMode ? 0 : hillshadeStrength}
            selectedBuildingId={selectedBuilding?.id ?? null}
            selectedNutzungId={selectedNutzung?.id ?? null}
            changeDetectionGeojson={activeChangeResult?.changed_areas_geojson ?? null}
            changeDetectionVisible={changeDetectionVisible}
            changeDetectionOpacity={changeDetectionOpacity}
            swipeEnabled={effectiveSwipeEnabled}
            swipePosition={effectiveSwipePosition}
            onSwipePositionChange={dashboardMode === "land-cover-change" ? setSwipePosition : setLayerComparePosition}
            swipeLeftLayerId={effectiveSwipeLeftLayerId}
            swipeRightLayerId={effectiveSwipeRightLayerId}
            swipeLeftLabel={effectiveSwipeLeftLabel}
            swipeRightLabel={effectiveSwipeRightLabel}
          />

          <div className="pointer-events-none absolute left-4 top-4 z-10">
            <div className="pointer-events-auto flex flex-col gap-2">
              <CollapsiblePanel
                title="Layers"
                isOpen={layersPanelOpen}
                onToggle={() => setLayersPanelOpen((v) => !v)}
                widthClass="w-80"
                badge={
                  <span className="rounded-full bg-cyan-400/10 px-1.5 py-0.5 text-[9px] text-cyan-300">
                    {layers.filter((l) => l.default_visible && l.available).length}
                  </span>
                }
              >
                <LayerPanel
                  layers={layers}
                  onToggleVisibility={handleToggleVisibility}
                  onOpacityChange={handleOpacityChange}
                  onResetVisible={handleResetVisibleLayers}
                />
              </CollapsiblePanel>

              <CollapsiblePanel
                title="Comparison"
                isOpen={comparisonPanelOpen}
                onToggle={() => setComparisonPanelOpen((v) => !v)}
                widthClass="w-80"
              >
                <div className="space-y-2 text-[11px] text-slate-300">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={layerCompareEnabled && layerCompareAvailable}
                      onChange={(event) => handleEnableLayerComparison(event.target.checked)}
                      disabled={!layerCompareAvailable}
                      className="accent-cyan-400"
                    />
                    Enable swipe comparison
                  </label>
                  <p className="text-[10px] text-slate-400">Only selected left/right layers change with swipe. Other active layers remain visible on both sides.</p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <label className="flex flex-col gap-1 text-[10px]">
                      <span>Left layer</span>
                      <select
                        value={layerCompareLeftId ?? ""}
                        onChange={(event) => {
                          const id = event.target.value || null;
                          setLayerCompareLeftId(id);
                          if (id) {
                            activateLayerOnTop(id, 1);
                          }
                        }}
                        className="rounded border border-white/10 bg-slate-900 px-2 py-1 text-[10px] text-slate-200"
                      >
                        {layerComparisonCandidates.map((layer) => (
                          <option key={`cmp-left-${layer.id}`} value={layer.id}>
                            {layer.short_title ?? layer.title}
                          </option>
                        ))}
                      </select>
                      <label className="mt-1 flex items-center gap-2 text-[10px] text-slate-400">
                        Opacity
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={layerCompareLeftOpacity}
                          onChange={(event) => {
                            if (!layerCompareLeftId) return;
                            handleOpacityChange(layerCompareLeftId, Number(event.target.value));
                          }}
                          className="w-full accent-cyan-400"
                        />
                        <span className="w-8 text-right text-slate-300">{Math.round(layerCompareLeftOpacity * 100)}%</span>
                      </label>
                    </label>
                    <label className="flex flex-col gap-1 text-[10px]">
                      <span>Right layer</span>
                      <select
                        value={layerCompareRightId ?? ""}
                        onChange={(event) => {
                          const id = event.target.value || null;
                          setLayerCompareRightId(id);
                          if (id) {
                            activateLayerOnTop(id, 1);
                          }
                        }}
                        className="rounded border border-white/10 bg-slate-900 px-2 py-1 text-[10px] text-slate-200"
                      >
                        {layerComparisonCandidates.map((layer) => (
                          <option key={`cmp-right-${layer.id}`} value={layer.id}>
                            {layer.short_title ?? layer.title}
                          </option>
                        ))}
                      </select>
                      <label className="mt-1 flex items-center gap-2 text-[10px] text-slate-400">
                        Opacity
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={layerCompareRightOpacity}
                          onChange={(event) => {
                            if (!layerCompareRightId) return;
                            handleOpacityChange(layerCompareRightId, Number(event.target.value));
                          }}
                          className="w-full accent-cyan-400"
                        />
                        <span className="w-8 text-right text-slate-300">{Math.round(layerCompareRightOpacity * 100)}%</span>
                      </label>
                    </label>
                  </div>
                </div>
              </CollapsiblePanel>
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-4 left-1/2 z-10 -translate-x-1/2">
            <div className="pointer-events-auto">
              <DrawToolbar
                drawMode={drawMode}
                pointCount={drawnPoints.length}
                onStart={() => {
                  setDrawnPoints([]);
                  setSelectedBuilding(null);
                  buildingContext.reset();
                  setSelectedNutzung(null);
                  setDrawMode(true);
                }}
                onFinish={handleFinishDraw}
                onClear={handleClearDraw}
              />
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-4 right-4 z-10">
            <div className="pointer-events-auto flex max-w-[320px] flex-col gap-2">
              {legendLayers.map((layer) => (
                <MapLegend key={layer.id} layer={layer} />
              ))}
              {activeLayers.length > 0 ? (
                <div className="glass-panel rounded-xl p-2">
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-cyan-300">Active layers (top → bottom)</div>
                  <div className="max-h-64 space-y-1 overflow-y-auto">
                    {activeLayers.map((layer, index) => (
                      <div
                        key={`active-${layer.id}`}
                        onDragEnter={(event) => {
                          event.preventDefault();
                          if (draggingActiveLayerId && draggingActiveLayerId !== layer.id) {
                            setActiveDropTargetId(layer.id);
                          }
                        }}
                        onDragOver={(event) => {
                          event.preventDefault();
                          if (draggingActiveLayerId && draggingActiveLayerId !== layer.id) {
                            setActiveDropTargetId(layer.id);
                          }
                        }}
                        onDrop={(event) => {
                          event.preventDefault();
                          const draggedId = draggingActiveLayerId ?? event.dataTransfer.getData("text/plain");
                          handleReorderActiveLayersByDrop(draggedId, layer.id);
                        }}
                        className={`rounded bg-white/[0.04] px-2 py-1 text-[10px] text-slate-200 ${
                          draggingActiveLayerId === layer.id
                            ? "opacity-70"
                            : activeDropTargetId === layer.id
                              ? "ring-1 ring-cyan-300/70"
                              : ""
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate pr-2">
                            <button
                              type="button"
                              data-no-drag="true"
                              draggable
                              onDragStart={(event) => {
                                setDraggingActiveLayerId(layer.id);
                                event.dataTransfer.effectAllowed = "move";
                                event.dataTransfer.setData("text/plain", layer.id);
                              }}
                              onDragEnd={() => {
                                setDraggingActiveLayerId(null);
                                setActiveDropTargetId(null);
                              }}
                              className="mr-1 cursor-grab text-slate-400 active:cursor-grabbing"
                              aria-label={`Drag ${layer.short_title ?? layer.title}`}
                              title="Drag to reorder"
                            >
                              ↕
                            </button>
                            {layer.short_title ?? layer.title}
                          </span>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              data-no-drag="true"
                              onClick={() => handleMoveActiveLayer(layer.id, "top")}
                              disabled={index === 0}
                              className="rounded px-1 text-slate-300 hover:bg-white/10 disabled:opacity-30"
                              aria-label={`Move ${layer.short_title ?? layer.title} to top`}
                              title="Move to top"
                            >
                              ⤒
                            </button>
                            <button
                              type="button"
                              data-no-drag="true"
                              onClick={() => handleMoveActiveLayer(layer.id, "bottom")}
                              disabled={index === activeLayers.length - 1}
                              className="rounded px-1 text-slate-300 hover:bg-white/10 disabled:opacity-30"
                              aria-label={`Move ${layer.short_title ?? layer.title} to bottom`}
                              title="Move to bottom"
                            >
                              ⤓
                            </button>
                            <button
                              type="button"
                              data-no-drag="true"
                              onClick={() => handleToggleVisibility(layer.id)}
                              className="text-red-300 hover:text-red-200"
                              aria-label={`Deactivate ${layer.short_title ?? layer.title}`}
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-[9px] uppercase tracking-wide text-slate-400">Opacity</span>
                          <input
                            type="range"
                            data-no-drag="true"
                            min={0}
                            max={1}
                            step={0.05}
                            value={layer.default_opacity}
                            draggable={false}
                            onMouseDown={(event) => event.stopPropagation()}
                            onPointerDown={(event) => event.stopPropagation()}
                            onDragStart={(event) => event.preventDefault()}
                            onChange={(event) => handleOpacityChange(layer.id, Number(event.target.value))}
                            className="w-full accent-cyan-400"
                            aria-label={`Opacity for ${layer.short_title ?? layer.title}`}
                          />
                          <span className="w-8 text-right text-[9px] text-slate-400">{Math.round(layer.default_opacity * 100)}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          {selectedBuilding ? (
            <div className="pointer-events-none absolute bottom-4 right-4 z-10 w-[360px]">
              <div className="glass-panel pointer-events-auto rounded-xl p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Building info</h3>
                    <p className="text-[11px] text-slate-300">ID: {selectedBuilding.id}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedBuilding(null);
                      buildingContext.reset();
                    }}
                    className="rounded bg-white/10 px-2 py-1 text-[10px] text-slate-200 hover:bg-white/20"
                  >
                    Close
                  </button>
                </div>

                <div className="mb-2 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                  <span>Height: {selectedBuildingHeight.toFixed(1)} m</span>
                  <span>Method: {String(selectedBuilding.properties.method ?? "n/a")}</span>
                  <span>Created: {String(selectedBuilding.properties.creation_date ?? "n/a")}</span>
                  <span>Ground z: {selectedBuilding.properties.ground_height ? String(selectedBuilding.properties.ground_height) : "n/a"}</span>
                </div>

                <div className="mb-2">
                  <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">Building height vs area buildings</div>
                  <div className="relative h-4 rounded bg-slate-700/60">
                    <div className="absolute inset-y-0 left-1/2 w-[1px] bg-slate-400/70" />
                    {heightPercentile !== null ? (
                      <div
                        className="absolute inset-y-0 w-[4px] rounded bg-cyan-300 shadow-[0_0_8px_rgba(34,211,238,0.9)]"
                        style={{ left: `${heightPercentile}%` }}
                        title={`Height percentile: ${heightPercentile.toFixed(1)}%`}
                      />
                    ) : null}
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-slate-400">
                    <span>Shorter</span>
                    <span>{heightPercentile !== null ? `${heightPercentile.toFixed(1)}th percentile` : "n/a"}</span>
                    <span>Taller</span>
                  </div>
                </div>

                {buildingContext.isPending ? <p className="text-[11px] text-slate-400">Calculating 15m context stats…</p> : null}
                {buildingContext.error ? (
                  <p className="text-[11px] text-red-300">{buildingContext.error.message}</p>
                ) : null}

                {buildingContext.data?.results ? (
                  <div className="space-y-2">
                    {buildingContext.data.results.map((result) => (
                      <div key={result.layer_id} className="rounded border border-white/10 bg-white/[0.02] p-2">
                        <div className="mb-1 text-[11px] font-semibold text-slate-200">{(result.title ?? result.layer_id).replace(/^Planegg\s+/i, "")}</div>
                        <div className="mb-2">
                          <div
                            className="relative h-4 rounded"
                            style={{
                              background: `linear-gradient(90deg, ${(result.legend?.palette ?? ["#334155", "#22d3ee"]).join(", ")})`,
                            }}
                          >
                            {(() => {
                              const min = result.value_range?.minimum ?? result.average_building.minimum;
                              const max = result.value_range?.maximum ?? result.average_building.maximum;
                              const range = max - min || 1;
                              const selectedPct = Math.max(0, Math.min(100, ((result.selected.mean - min) / range) * 100));
                              const avgPct = Math.max(0, Math.min(100, ((result.average_building.mean - min) / range) * 100));
                              return (
                                <>
                                  <div
                                    className="absolute inset-y-0 w-[4px] rounded border border-white/70 bg-black"
                                    style={{ left: `${selectedPct}%` }}
                                    title={`Selected: ${result.selected.mean.toFixed(2)} ${result.units ?? ""}`}
                                  />
                                  <div
                                    className="absolute inset-y-0 w-[5px] rounded border border-white/70"
                                    style={{
                                      left: `${avgPct}%`,
                                      backgroundImage: "repeating-linear-gradient(to bottom, #000000 0 2px, transparent 2px 4px)",
                                      backgroundColor: "rgba(255,255,255,0.65)",
                                    }}
                                    title={`Average building: ${result.average_building.mean.toFixed(2)} ${result.units ?? ""}`}
                                  />
                                </>
                              );
                            })()}
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400">
                          <span>15m mean: {result.selected.mean.toFixed(2)} {result.units ?? ""}</span>
                          <span>Area avg bldg: {result.average_building.mean.toFixed(2)} {result.units ?? ""}</span>
                          <span>15m min/max: {result.selected.minimum.toFixed(2)} / {result.selected.maximum.toFixed(2)}</span>
                          <span>Avg min/max: {result.average_building.minimum.toFixed(2)} / {result.average_building.maximum.toFixed(2)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}

          {selectedNutzung ? (
            <div className="pointer-events-none absolute bottom-4 right-4 z-10 w-[360px]">
              <div className="glass-panel pointer-events-auto rounded-xl p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-cyan-300">ALKIS Nutzung</h3>
                    <div
                      className="mt-1 inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-base font-semibold"
                      style={{
                        backgroundColor: `${nutzungCategoryColor(selectedNutzung.properties.nutzart)}33`,
                        color: nutzungCategoryColor(selectedNutzung.properties.nutzart),
                        border: `1px solid ${nutzungCategoryColor(selectedNutzung.properties.nutzart)}66`,
                      }}
                    >
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: nutzungCategoryColor(selectedNutzung.properties.nutzart) }}
                      />
                      {displayValue(selectedNutzung.properties.nutzart)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedNutzung(null)}
                    className="rounded bg-white/10 px-2 py-1 text-[10px] text-slate-200 hover:bg-white/20"
                  >
                    Close
                  </button>
                </div>

                <div className="space-y-1 rounded border border-white/10 bg-white/[0.02] p-2 text-[11px] text-slate-300">
                  <div><span className="font-medium text-slate-400">OID:</span> {displayValue(selectedNutzung.properties.oid ?? selectedNutzung.id)}</div>
                  <div><span className="font-medium text-slate-400">Aktualität:</span> {displayValue(selectedNutzung.properties.aktualit)}</div>
                  <div><span className="font-medium text-slate-400">Bezeichnung:</span> {displayValue(selectedNutzung.properties.bez)}</div>
                  <div><span className="font-medium text-slate-400">Name:</span> {displayValue(selectedNutzung.properties.name)}</div>
                </div>

                <details className="mt-2 rounded border border-white/10 bg-white/[0.02] p-2">
                  <summary className="cursor-pointer text-[10px] font-medium uppercase tracking-wide text-slate-500">
                    Weitere Attribute
                  </summary>
                  <div className="mt-2 space-y-1">
                    {Object.entries(selectedNutzung.properties)
                      .filter(([key]) => !["oid", "aktualit", "nutzart", "bez", "name"].includes(key))
                      .map(([key, value]) => (
                        <div key={key} className="flex items-start justify-between gap-2 text-[10px]">
                          <span className="text-slate-500">{key}</span>
                          <span className="text-right text-slate-300">{displayValue(value)}</span>
                        </div>
                      ))}
                  </div>
                </details>
              </div>
            </div>
          ) : null}
        </div>

        <div
          className={`glass-panel z-20 flex min-h-0 shrink-0 flex-col rounded-none border-y-0 border-r-0 transition-all ${
            analysisPanelOpen ? "w-96" : "w-12"
          }`}
        >
          <button
            type="button"
            onClick={() => setAnalysisPanelOpen((v) => !v)}
            className="flex shrink-0 items-center justify-between gap-2 px-3 py-3 text-left"
          >
            {analysisPanelOpen ? (
              <span className="text-xs font-semibold uppercase tracking-wide text-cyan-300">
                {dashboardMode === "analysis" ? "Area analysis" : dashboardMode === "heat-development" ? "Heat development" : "Land cover change"}
              </span>
            ) : null}
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              className={`shrink-0 text-slate-400 transition-transform ${analysisPanelOpen ? "" : "rotate-180"}`}
            >
              <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          {analysisPanelOpen ? (
            <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
              {dashboardMode === "analysis" ? (
                <>
                  <div className="mb-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setAnalysisView("planegg")}
                      className={`rounded-md border px-2 py-1.5 text-xs transition ${
                        analysisView === "planegg"
                          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      }`}
                    >
                      Planegg Overview
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (hasDrawnSelection) setAnalysisView("drawn");
                      }}
                      disabled={!hasDrawnSelection}
                      className={`rounded-md border px-2 py-1.5 text-xs transition ${
                        analysisView === "drawn"
                          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      } ${!hasDrawnSelection ? "cursor-not-allowed opacity-50" : ""}`}
                    >
                      Drawn Area
                    </button>
                  </div>
                  <AnalysisPanel
                    results={analysisResults}
                    isPending={analysisPending}
                    error={analysisError}
                    treeStats={treeStatsResult}
                    treeStatsPending={treeStatsPending}
                    treeStatsError={treeStatsError}
                    overviewMode={!useDrawnView}
                    overviewBuildingStats={overviewBuildingStats}
                    overviewBuildingClimate={overviewBuildingClimate}
                    vulnerability={vulnerabilityResult}
                    vulnerabilityPending={vulnerabilityPending}
                    vulnerabilityError={vulnerabilityError}
                    lstPalette={lstPalette}
                    ndviPalette={ndviPalette}
                    showBuildings={useDrawnView ? buildingsVisible : buildingsAvailable}
                    showVulnerability={useDrawnView ? censusVisible : censusAvailable}
                    showTrees={useDrawnView ? treesAvailable : treesAvailable}
                    showLandUse={useDrawnView ? nutzungVisible : nutzungAvailable}
                    landUse={landUseResult}
                    landUsePending={landUsePending}
                    landUseError={landUseError}
                    totalAreaHectares={totalAreaHectares}
                    visibleLayerIds={visibleRasterLayerIds}
                  />
                </>
              ) : dashboardMode === "heat-development" ? (
                <>
                  <div className="mb-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setTimeSeriesScope("planegg")}
                      className={`rounded-md border px-2 py-1.5 text-xs transition ${
                        timeSeriesScope === "planegg"
                          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      }`}
                    >
                      Planegg
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (hasDrawnSelection) setTimeSeriesScope("drawn");
                      }}
                      disabled={!hasDrawnSelection}
                      className={`rounded-md border px-2 py-1.5 text-xs transition ${
                        timeSeriesScope === "drawn"
                          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      } ${!hasDrawnSelection ? "cursor-not-allowed opacity-50" : ""}`}
                    >
                      Drawn Area
                    </button>
                  </div>
                  <RelativeSummerLstPanel
                    points={relativeSummerPointsForScope}
                    isPending={relativeSummerLstSeries.isPending || (timeSeriesScope === "drawn" && drawnHeatSeriesStatistics.isPending)}
                    error={relativeSummerLstSeries.error ?? (timeSeriesScope === "drawn" ? drawnHeatSeriesStatistics.error : null)}
                    selectedLayerId={selectedSeriesLayerId}
                    onSelectYear={handleSelectRelativeSummerPoint}
                  />
                </>
              ) : (
                <>
                  <div className="mb-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setTimeSeriesScope("planegg")}
                      className={`rounded-md border px-2 py-1.5 text-xs transition ${
                        timeSeriesScope === "planegg"
                          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      }`}
                    >
                      Planegg
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (hasDrawnSelection) setTimeSeriesScope("drawn");
                      }}
                      disabled={!hasDrawnSelection}
                      className={`rounded-md border px-2 py-1.5 text-xs transition ${
                        timeSeriesScope === "drawn"
                          ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                      } ${!hasDrawnSelection ? "cursor-not-allowed opacity-50" : ""}`}
                    >
                      Drawn Area
                    </button>
                  </div>
                  <LulcChangePanel
                    points={lulcPointsForScope}
                    classSeries={lulcClassSeries}
                    scope={timeSeriesScope}
                    selectedLayerId={selectedLulcLayerId}
                    onSelectYear={handleSelectLulcPoint}
                    yearRange={lulcYearRange}
                    onYearRangeChange={setLulcYearRange}
                    showYearList={false}
                  />
                  {timeSeriesScope === "drawn" && drawnLulcSeriesStatistics.isPending ? (
                    <p className="mt-2 text-[11px] text-slate-500">Updating drawn-area LULC series…</p>
                  ) : null}
                  {timeSeriesScope === "drawn" && drawnLulcSeriesStatistics.error ? (
                    <p className="mt-2 text-[11px] text-red-300">{drawnLulcSeriesStatistics.error.message}</p>
                  ) : null}
                  {changeDetection.isPending ? (
                    <p className="mt-2 text-[11px] text-slate-500">Computing change detection…</p>
                  ) : null}
                  {changeDetection.error ? (
                    <p className="mt-2 text-[11px] text-red-300">{changeDetection.error.message}</p>
                  ) : null}
                  {hasSelectedChangePair ? (
                    <div className="mt-3 space-y-2 rounded border border-cyan-400/30 bg-cyan-400/5 p-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-cyan-300">
                          {fromYearPoint?.year ?? activeChangeResult?.from_year ?? "—"} → {toYearPoint?.year ?? activeChangeResult?.to_year ?? "—"}
                        </h4>
                        <button
                          type="button"
                          onClick={() => setLulcYearRange({ fromYear: null, toYear: null })}
                          className="text-[10px] text-slate-400 hover:text-slate-200"
                        >
                          Clear
                        </button>
                      </div>
                      <div className="rounded border border-white/10 bg-white/[0.03] p-2 text-[10px] text-slate-300">
                        <div className="mb-1 font-medium text-slate-200">Change layer controls</div>
                        <div className="mb-1 flex items-center justify-between">
                          <label className="inline-flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={changeDetectionVisible}
                              onChange={(event) => setChangeDetectionVisible(event.target.checked)}
                              className="accent-cyan-400"
                            />
                            Show on map
                          </label>
                          <button
                            type="button"
                            onClick={() => {
                              setChangeDetectionVisible(false);
                              setLulcYearRange({ fromYear: null, toYear: null });
                              resetComparisonYearLayers();
                            }}
                            className="rounded border border-white/15 px-1.5 py-0.5 text-[10px] text-slate-300 hover:bg-white/10"
                          >
                            Deselect
                          </button>
                        </div>
                        <label className="flex items-center gap-2 text-[10px] text-slate-400">
                          Opacity
                          <input
                            type="range"
                            min={0.1}
                            max={1}
                            step={0.05}
                            value={changeDetectionOpacity}
                            onChange={(event) => setChangeDetectionOpacity(Number(event.target.value))}
                            className="w-full accent-cyan-400"
                          />
                          <span className="w-10 text-right text-slate-300">{Math.round(changeDetectionOpacity * 100)}%</span>
                        </label>

                        <div className="mt-2 rounded border border-white/10 bg-white/[0.02] p-2">
                          <div className="mb-1 font-medium text-slate-200">Selected year layers</div>

                          <div className="space-y-2">
                            <div className="rounded border border-white/10 bg-white/[0.03] p-2">
                              <div className="mb-1 text-[10px] text-slate-300">From year: {fromYearPoint?.year ?? "—"}</div>
                              <label className="mb-1 inline-flex items-center gap-2 text-[10px] text-slate-400">
                                <input
                                  type="checkbox"
                                  checked={fromLulcVisible}
                                  onChange={(event) => handleToggleFromLulc(event.target.checked)}
                                  className="accent-cyan-400"
                                />
                                Show LULC ({fromYearPoint?.title ?? "n/a"})
                              </label>
                              <label className="mb-1 flex items-center gap-2 text-[10px] text-slate-400">
                                LULC opacity
                                <input
                                  type="range"
                                  min={0.1}
                                  max={1}
                                  step={0.05}
                                  value={fromLulcOpacity}
                                  onChange={(event) => handleFromLulcOpacity(Number(event.target.value))}
                                  className="w-full accent-cyan-400"
                                />
                                <span className="w-10 text-right text-slate-300">{Math.round(fromLulcOpacity * 100)}%</span>
                              </label>
                              <label className="mb-1 inline-flex items-center gap-2 text-[10px] text-slate-400">
                                <input
                                  type="checkbox"
                                  checked={fromRgbVisible}
                                  onChange={(event) => handleToggleFromRgb(event.target.checked)}
                                  disabled={!fromYearRgbOption?.available}
                                  className="accent-cyan-400"
                                />
                                Show RGB ({fromYearRgbOption?.title ?? "not available"})
                              </label>
                              <label className="flex items-center gap-2 text-[10px] text-slate-400">
                                RGB opacity
                                <input
                                  type="range"
                                  min={0.1}
                                  max={1}
                                  step={0.05}
                                  value={fromRgbOpacity}
                                  onChange={(event) => handleFromRgbOpacity(Number(event.target.value))}
                                  disabled={!fromYearRgbOption?.available}
                                  className="w-full accent-cyan-400"
                                />
                                <span className="w-10 text-right text-slate-300">{Math.round(fromRgbOpacity * 100)}%</span>
                              </label>
                            </div>

                            <div className="rounded border border-white/10 bg-white/[0.03] p-2">
                              <div className="mb-1 text-[10px] text-slate-300">To year: {toYearPoint?.year ?? "—"}</div>
                              <label className="mb-1 inline-flex items-center gap-2 text-[10px] text-slate-400">
                                <input
                                  type="checkbox"
                                  checked={toLulcVisible}
                                  onChange={(event) => handleToggleToLulc(event.target.checked)}
                                  className="accent-cyan-400"
                                />
                                Show LULC ({toYearPoint?.title ?? "n/a"})
                              </label>
                              <label className="mb-1 flex items-center gap-2 text-[10px] text-slate-400">
                                LULC opacity
                                <input
                                  type="range"
                                  min={0.1}
                                  max={1}
                                  step={0.05}
                                  value={toLulcOpacity}
                                  onChange={(event) => handleToLulcOpacity(Number(event.target.value))}
                                  className="w-full accent-cyan-400"
                                />
                                <span className="w-10 text-right text-slate-300">{Math.round(toLulcOpacity * 100)}%</span>
                              </label>
                              <label className="mb-1 inline-flex items-center gap-2 text-[10px] text-slate-400">
                                <input
                                  type="checkbox"
                                  checked={toRgbVisible}
                                  onChange={(event) => handleToggleToRgb(event.target.checked)}
                                  disabled={!toYearRgbOption?.available}
                                  className="accent-cyan-400"
                                />
                                Show RGB ({toYearRgbOption?.title ?? "not available"})
                              </label>
                              <label className="flex items-center gap-2 text-[10px] text-slate-400">
                                RGB opacity
                                <input
                                  type="range"
                                  min={0.1}
                                  max={1}
                                  step={0.05}
                                  value={toRgbOpacity}
                                  onChange={(event) => handleToRgbOpacity(Number(event.target.value))}
                                  disabled={!toYearRgbOption?.available}
                                  className="w-full accent-cyan-400"
                                />
                                <span className="w-10 text-right text-slate-300">{Math.round(toRgbOpacity * 100)}%</span>
                              </label>
                            </div>
                          </div>

                          <div className="mt-2 rounded border border-white/10 bg-white/[0.03] p-2">
                            <div className="mb-1 flex items-center justify-between text-[10px]">
                              <span className="font-medium text-slate-200">Swipe compare</span>
                              <label className="inline-flex items-center gap-2 text-slate-300">
                                <input
                                  type="checkbox"
                                  checked={swipeEnabled && swipeAvailable}
                                  onChange={(event) => {
                                    const next = event.target.checked;
                                    if (next) {
                                      ensureSwipeSelectionVisible(swipeLeftSelection);
                                      ensureSwipeSelectionVisible(swipeRightSelection);
                                    }
                                    setSwipeEnabled(next);
                                  }}
                                  disabled={!hasSelectedChangePair}
                                  className="accent-cyan-400"
                                />
                                Enable
                              </label>
                            </div>
                            <p className="mb-1 text-[10px] text-slate-400">
                              Left side shows: {swipeLeftLabel} · Right side shows: {swipeRightLabel}
                            </p>
                            <label className="flex items-center gap-2 text-[10px] text-slate-400">
                              Divider
                              <input
                                type="range"
                                min={0.05}
                                max={0.95}
                                step={0.01}
                                value={swipePosition}
                                onChange={(event) => setSwipePosition(Number(event.target.value))}
                                disabled={!swipeEnabled || !swipeAvailable}
                                className="w-full accent-cyan-400"
                              />
                              <span className="w-10 text-right text-slate-300">{Math.round(swipePosition * 100)}%</span>
                            </label>
                            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                              <label className="flex flex-col gap-1 text-[10px] text-slate-300">
                                Left layer
                                <select
                                  value={swipeLeftSelection}
                                  onChange={(event) => {
                                    const value = event.target.value as SwipeLayerSelection;
                                    setSwipeLeftSelection(value);
                                    if (swipeEnabled) ensureSwipeSelectionVisible(value);
                                  }}
                                  className="rounded border border-white/10 bg-slate-900 px-2 py-1 text-[10px] text-slate-200"
                                >
                                  {swipeLayerChoiceEntries.map((entry) => (
                                    <option key={`left-${entry.key}`} value={entry.key} disabled={!entry.layerId}>
                                      {entry.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="flex flex-col gap-1 text-[10px] text-slate-300">
                                Right layer
                                <select
                                  value={swipeRightSelection}
                                  onChange={(event) => {
                                    const value = event.target.value as SwipeLayerSelection;
                                    setSwipeRightSelection(value);
                                    if (swipeEnabled) ensureSwipeSelectionVisible(value);
                                  }}
                                  className="rounded border border-white/10 bg-slate-900 px-2 py-1 text-[10px] text-slate-200"
                                >
                                  {swipeLayerChoiceEntries.map((entry) => (
                                    <option key={`right-${entry.key}`} value={entry.key} disabled={!entry.layerId}>
                                      {entry.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                            </div>
                          </div>
                        </div>
                      </div>
                      {activeChangeResult ? (
                        <>
                          <div className="grid grid-cols-2 gap-1 text-[10px] text-slate-400">
                            <div>
                              <span className="text-slate-500">Total area:</span>
                              <span className="ml-1 text-slate-300">{activeChangeResult.total_area_hectares.toFixed(1)} ha</span>
                            </div>
                            <div>
                              <span className="text-slate-500">Changed:</span>
                              <span className="ml-1 text-slate-300">{activeChangeResult.changed_share_pct.toFixed(1)}%</span>
                            </div>
                            <div>
                              <span className="text-slate-500">Low-certainty share:</span>
                              <span className="ml-1 text-amber-200">{activeChangeResult.uncertainty_share_pct.toFixed(2)}%</span>
                            </div>
                            <div>
                              <span className="text-slate-500">High-certainty share:</span>
                              <span className="ml-1 text-rose-200">{(activeChangeResult.certainty_by_level_pct.high ?? 0).toFixed(2)}%</span>
                            </div>
                          </div>
                          <div className="rounded border border-white/10 bg-white/[0.03] p-1.5 text-[10px] text-slate-400">
                            <div className="mb-1 font-medium text-slate-300">Certainty grading from transition percentages</div>
                            <div className="space-y-1">
                              <div className="flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" /> High (≥1.00%)</span>
                                <span>{(activeChangeResult.certainty_by_level_pct.high ?? 0).toFixed(2)}%</span>
                              </div>
                              <div className="flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-orange-500" /> Medium (0.25–0.99%)</span>
                                <span>{(activeChangeResult.certainty_by_level_pct.medium ?? 0).toFixed(2)}%</span>
                              </div>
                              <div className="flex items-center justify-between gap-2">
                                <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-yellow-400" /> Low (&lt;0.25%)</span>
                                <span>{(activeChangeResult.certainty_by_level_pct.low ?? 0).toFixed(2)}%</span>
                              </div>
                            </div>
                          </div>
                          <div className="max-h-48 space-y-1 overflow-y-auto">
                            {activeChangeResult.transitions.map((transition, idx) => (
                          <div key={idx} className="flex items-start gap-1.5 rounded bg-white/[0.02] p-1 text-[10px]">
                            <div className="flex items-center gap-1">
                              <span
                                className="h-2.5 w-2.5 rounded-full"
                                style={{ backgroundColor: transition.from_class_color }}
                              />
                              <span className="text-slate-400">{transition.from_class_label}</span>
                            </div>
                            <svg className="h-3 w-3 text-slate-600" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" fill="none" />
                            </svg>
                            <div className="flex items-center gap-1">
                              <span
                                className="h-2.5 w-2.5 rounded-full"
                                style={{ backgroundColor: transition.to_class_color }}
                              />
                              <span className="text-slate-300">{transition.to_class_label}</span>
                            </div>
                            <span
                              className="rounded px-1 py-0.5 text-[9px] font-medium"
                              style={{ backgroundColor: `${transition.confidence_color}33`, color: transition.confidence_color }}
                            >
                              {transition.confidence_level}
                            </span>
                            <span className="ml-auto text-right text-slate-500">
                              {transition.area_hectares.toFixed(2)} ha
                              <span className="ml-1">({transition.share_pct.toFixed(2)}%)</span>
                            </span>
                          </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        <p className="text-[11px] text-slate-400">Computing transition matrix…</p>
                      )}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}

