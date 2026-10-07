"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { MapCanvas, type BasemapId, type TerrainSourceId } from "@/components/map/MapCanvas";
import { MapLegend } from "@/components/map/MapLegend";
import { BasemapSwitcher } from "@/components/map/BasemapSwitcher";
import { LayerPanel } from "@/components/layers/LayerPanel";
import { DrawToolbar } from "@/components/analysis/DrawToolbar";
import { AnalysisPanel } from "@/components/analysis/AnalysisPanel";
import { CollapsiblePanel } from "@/components/layout/CollapsiblePanel";
import { useLayerCatalog } from "@/hooks/useLayerCatalog";
import { useAreaStatistics } from "@/hooks/useAreaStatistics";
import { fetchAreaStatistics, fetchBuildingContext, fetchBuildingsOverview, fetchHeatVulnerability, fetchTreeStatistics } from "@/lib/api/analysis";
import { API_BASE_URL, fetchJson } from "@/lib/api/client";
import type {
  BuildingContextResponse,
  BuildingOverviewLayerStatistics,
  HeatVulnerabilityResult,
  LayerAreaStatistics,
  TreeStatisticsResult,
} from "@/types/analysis";
import type { CatalogLayer } from "@/types/layers";

type SelectedBuilding = {
  id: string;
  properties: Record<string, unknown>;
  geometry: Record<string, unknown>;
  lngLat: [number, number];
};

export default function HomePage() {
  const { data: catalogLayers, isLoading, error } = useLayerCatalog();
  const [overrides, setOverrides] = useState<Record<string, Partial<CatalogLayer>>>({});
  const [drawMode, setDrawMode] = useState(false);
  const [drawnPoints, setDrawnPoints] = useState<[number, number][]>([]);
  const [basemap, setBasemap] = useState<BasemapId>("satellite");
  const [terrain3dEnabled, setTerrain3dEnabled] = useState(false);
  const [terrainSource, setTerrainSource] = useState<TerrainSourceId>("dem");
  const [terrainAvailable, setTerrainAvailable] = useState(false);
  const [terrainSourcesAvailable, setTerrainSourcesAvailable] = useState<Record<TerrainSourceId, boolean>>({ dem: false, dom: false });
  const [terrainExaggeration, setTerrainExaggeration] = useState(1.8);
  const [hillshadeStrength, setHillshadeStrength] = useState(0.7);
  const [layersPanelOpen, setLayersPanelOpen] = useState(true);
  const [analysisPanelOpen, setAnalysisPanelOpen] = useState(true);
  const [analysisView, setAnalysisView] = useState<"planegg" | "drawn">("planegg");
  const [hasDrawnSelection, setHasDrawnSelection] = useState(false);
  const [selectedBuilding, setSelectedBuilding] = useState<SelectedBuilding | null>(null);
  const [allBuildingHeights, setAllBuildingHeights] = useState<number[]>([]);
  const [overviewResults, setOverviewResults] = useState<LayerAreaStatistics[] | undefined>(undefined);
  const [overviewPending, setOverviewPending] = useState(false);
  const [overviewError, setOverviewError] = useState<Error | null>(null);
  const [overviewBuildingStats, setOverviewBuildingStats] = useState<{ count: number; averageHeight: number } | null>(null);
  const [overviewBuildingClimate, setOverviewBuildingClimate] = useState<BuildingOverviewLayerStatistics[]>([]);
  const [overviewVulnerability, setOverviewVulnerability] = useState<HeatVulnerabilityResult | null>(null);
  const [overviewTreeStats, setOverviewTreeStats] = useState<TreeStatisticsResult | null>(null);
  const domTerrainMode = terrain3dEnabled && terrainSource === "dom";

  const areaStatistics = useAreaStatistics();
  const buildingContext = useMutation<BuildingContextResponse, Error, { geometry: Record<string, unknown>; layer_ids: string[] }>(
    {
      mutationFn: (payload) =>
        fetchBuildingContext({
          ...payload,
          buildings_layer_id: "buildings-3d-planegg",
          buffer_meters: 15,
        }),
    },
  );

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
        .filter((layer) => layer.layer_type === "raster" || (layer.layer_type === "vector" && layer.style?.color_scale === "population")),
    [layers],
  );

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

  const visibleRasterLayerIds = useMemo(
    () =>
      layers
        .filter((layer) => layer.layer_type === "raster" && layer.default_visible && layer.available)
        .map((layer) => layer.id),
    [layers],
  );

  const lstPalette = useMemo(
    () => layers.find((layer) => layer.id === "lst-planegg")?.legend?.palette ?? ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#fee090", "#fdae61", "#f46d43", "#d73027"],
    [layers],
  );
  const ndviPalette = useMemo(
    () => layers.find((layer) => layer.id === "ndvi-planegg")?.legend?.palette ?? ["#8B4513", "#d73027", "#fee08b", "#ffffbf", "#a6d96a", "#1a9850", "#00441b"],
    [layers],
  );

  useEffect(() => {
    let active = true;
    fetchJson<{ features: Array<{ properties?: { height?: number | string } }> }>("/api/vectors/buildings-3d-planegg")
      .then((fc) => {
        if (!active) return;
        const heights = fc.features
          .map((f) => Number(f.properties?.height))
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
      if (overviewLayerIds.length === 0 && !censusAvailable && !treesAvailable && !buildingsAvailable) {
        if (!active) return;
        setOverviewResults([]);
        setOverviewBuildingStats(null);
        setOverviewVulnerability(null);
        setOverviewTreeStats(null);
        setOverviewPending(false);
        return;
      }

      setOverviewPending(true);
      setOverviewError(null);
      try {
        const [boundaryFc, buildingsFc] = await Promise.all([
          fetchJson<{ features: Array<{ geometry: { type: "Polygon"; coordinates: number[][][] } }> }>("/api/vectors/planegg-boundary-buffered"),
          fetchJson<{ features: Array<{ properties?: { height?: number | string } }> }>("/api/vectors/buildings-3d-planegg"),
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

        const buildingsOverviewIds = overviewLayerIds.filter((id) => id === "ndvi-planegg" || id === "lst-planegg");
        const buildingsOverview = buildingsAvailable
          ? await fetchBuildingsOverview({
              layer_ids: buildingsOverviewIds,
              buildings_layer_id: "buildings-3d-planegg",
            })
          : { results: [] };

        const heights = buildingsFc.features
          .map((feature) => Number(feature.properties?.height))
          .filter((value) => Number.isFinite(value) && value > 0);

        if (!active) return;
        setOverviewResults(stats.results);
        setOverviewVulnerability(vulnerability?.result ?? null);
        setOverviewTreeStats(treeStats?.result ?? null);
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
  }, [overviewLayerIds, censusAvailable, lstAvailable, ndviAvailable, treesAvailable, buildingsAvailable]);

  useEffect(() => {
    let active = true;
    fetchJson<{ available: boolean; sources?: Partial<Record<TerrainSourceId, boolean>> }>(`/api/terrain/status?source=${terrainSource}`)
      .then((payload) => {
        if (!active) return;
        setTerrainAvailable(Boolean(payload.available));
        setTerrainSourcesAvailable({
          dem: Boolean(payload.sources?.dem),
          dom: Boolean(payload.sources?.dom),
        });
      })
      .catch(() => {
        if (!active) return;
        setTerrainAvailable(false);
        setTerrainSourcesAvailable({ dem: false, dom: false });
      });
    return () => {
      active = false;
    };
  }, [terrainSource]);

  useEffect(() => {
    if (terrainSource === "dem" && !terrainSourcesAvailable.dem && terrainSourcesAvailable.dom) {
      setTerrainSource("dom");
    }
    if (terrainSource === "dom" && !terrainSourcesAvailable.dom && terrainSourcesAvailable.dem) {
      setTerrainSource("dem");
    }
  }, [terrainSource, terrainSourcesAvailable]);

  function handleToggleVisibility(id: string) {
    setOverrides((prev) => {
      const current = layers.find((layer) => layer.id === id);
      const nextVisible = !(prev[id]?.default_visible ?? current?.default_visible ?? false);
      return { ...prev, [id]: { ...prev[id], default_visible: nextVisible } };
    });
  }

  function handleOpacityChange(id: string, opacity: number) {
    setOverrides((prev) => ({ ...prev, [id]: { ...prev[id], default_opacity: opacity } }));
  }

  function handleMapClick(lngLat: [number, number]) {
    if (!drawMode) return;
    setDrawnPoints((prev) => [...prev, lngLat]);
  }

  function handleFinishDraw() {
    if (drawnPoints.length < 3) return;
    const ring = [...drawnPoints, drawnPoints[0]];
    const polygon = { type: "Polygon" as const, coordinates: [ring] };
    areaStatistics.mutate({
      geometry: polygon,
      layer_ids: inspectableRasterLayers.map((layer) => layer.id),
    });
    if (censusVisible) {
      heatVulnerability.mutate({
        geometry: polygon,
        lstLayerId: lstVisible ? "lst-planegg" : null,
        ndviLayerId: ndviVisible ? "ndvi-planegg" : null,
      });
    } else {
      heatVulnerability.reset();
    }
    if (treesAvailable) {
      treeStatistics.mutate({ geometry: polygon });
    } else {
      treeStatistics.reset();
    }
    setHasDrawnSelection(true);
    setAnalysisView("drawn");
    setDrawMode(false);
  }

  function handleClearDraw() {
    setDrawMode(false);
    setDrawnPoints([]);
    areaStatistics.reset();
    heatVulnerability.reset();
    treeStatistics.reset();
    setHasDrawnSelection(false);
    setAnalysisView("planegg");
  }

  function handleBuildingClick(building: SelectedBuilding) {
    setSelectedBuilding(building);
    buildingContext.mutate({
      geometry: building.geometry,
      layer_ids: ["lst-planegg", "ndvi-planegg"],
    });
  }

  const selectedBuildingHeight = Number(selectedBuilding?.properties.height ?? 0);
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
          <button
            type="button"
            role="switch"
            aria-checked={terrain3dEnabled}
            disabled={!terrainSourcesAvailable.dem && !terrainSourcesAvailable.dom}
            onClick={() => setTerrain3dEnabled((v) => !v)}
            className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[11px] font-medium transition ${
              terrainSourcesAvailable.dem || terrainSourcesAvailable.dom
                ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-200 hover:bg-cyan-400/15"
                : "cursor-not-allowed border-white/10 bg-white/5 text-slate-500"
            }`}
            title={(terrainSourcesAvailable.dem || terrainSourcesAvailable.dom) ? "Toggle 3D terrain mode" : "No terrain source available. Import DEM/DOM first."}
          >
            <span
              className={`relative h-4 w-8 shrink-0 rounded-full transition ${
                terrain3dEnabled && (terrainSourcesAvailable.dem || terrainSourcesAvailable.dom) ? "bg-cyan-400" : "bg-slate-700"
              }`}
            >
              <span
                className={`absolute top-0.5 h-3 w-3 rounded-full bg-slate-950 transition ${
                  terrain3dEnabled && (terrainSourcesAvailable.dem || terrainSourcesAvailable.dom) ? "left-4" : "left-0.5"
                }`}
              />
            </span>
            3D Terrain
          </button>
          {terrain3dEnabled && (terrainSourcesAvailable.dem || terrainSourcesAvailable.dom) ? (
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
            apiBaseUrl={API_BASE_URL}
            drawMode={drawMode}
            drawnPoints={drawnPoints}
            onMapClick={handleMapClick}
            onBuildingClick={handleBuildingClick}
            basemap={basemap}
            terrain3dEnabled={terrain3dEnabled}
            terrainSource={terrainSource}
            terrainAvailable={terrainAvailable}
            terrainExaggeration={domTerrainMode ? 1 : terrainExaggeration}
            hillshadeStrength={domTerrainMode ? 0 : hillshadeStrength}
            selectedBuildingId={selectedBuilding?.id ?? null}
          />

          <div className={`pointer-events-none absolute left-4 top-4 z-10 ${layersPanelOpen ? "h-[calc(100%-2rem)]" : ""}`}>
            <div className={`pointer-events-auto ${layersPanelOpen ? "h-full" : ""}`}>
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
                <LayerPanel layers={layers} onToggleVisibility={handleToggleVisibility} onOpacityChange={handleOpacityChange} />
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
                  <span>Height: {Number(selectedBuilding.properties.height ?? 0).toFixed(1)} m</span>
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
              <span className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Area analysis</span>
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
                visibleLayerIds={visibleRasterLayerIds}
              />
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}

