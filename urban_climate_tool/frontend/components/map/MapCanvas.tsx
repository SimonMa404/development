"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map, Source, Layer, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import type { CatalogLayer } from "@/types/layers";
import type { Feature, Polygon } from "geojson";

export const PLANEGG_CENTER = {
  longitude: 11.4245,
  latitude: 48.0995,
  zoom: 13.5,
  pitch: 0,
  bearing: 0,
};

const VECTOR_COLORS: Record<string, string> = {
  boundary: "#22d3ee",
  context: "#94a3b8",
  buildings3d: "#6b7280",
  trees3d: "#166534",
  population: "#3b82f6",
  nutzung: "#7c3aed",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const NUTZUNG_COLOR_MATCH_EXPRESSION: any = [
  "match",
  ["coalesce", ["get", "nutzart"], ""],
  "Wohnbaufläche",
  "#f59e0b",
  "Industrie- und Gewerbefläche",
  "#6b7280",
  "Fläche gemischter Nutzung",
  "#a855f7",
  "Sport-, Freizeit- und Erholungsfläche",
  "#84cc16",
  "Landwirtschaft",
  "#eab308",
  "Wald",
  "#15803d",
  "Gehölz",
  "#22c55e",
  "Stehendes Gewässer",
  "#3b82f6",
  "Fließgewässer",
  "#06b6d4",
  "Straßenverkehr",
  "#475569",
  "Bahnverkehr",
  "#334155",
  "Weg",
  "#94a3b8",
  "Platz",
  "#cbd5e1",
  "Friedhof",
  "#65a30d",
  "Fläche besonderer funktionaler Prägung",
  "#f97316",
  "Tagebau, Grube, Steinbruch",
  "#92400e",
  "Unland/Vegetationslose Fläche",
  "#78716c",
  "#64748b",
];

export type BasemapId = "satellite" | "hybrid" | "dark";
export type SatelliteBasemapSource = "bayern-20cm" | "global";
export type TerrainSourceId = "dem" | "dom" | "dsm";

type ClickedVectorFeature = {
  id: string;
  properties: Record<string, unknown>;
  geometry: Record<string, unknown>;
  lngLat: [number, number];
};

const ESRI_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics, and the GIS User Community";

function rasterStyle(
  tiles: string[],
  attribution: string,
  layerMaxzoom = 24,
  sourceMaxzoom = 20,
): {
  version: 8;
  sources: Record<string, unknown>;
  layers: Array<Record<string, unknown>>;
} {
  return {
    version: 8 as const,
    sources: {
      base: {
        type: "raster" as const,
        tiles,
        tileSize: 256,
        attribution,
        maxzoom: sourceMaxzoom,
      },
    },
    layers: [
      {
        id: "base-layer",
        type: "raster" as const,
        source: "base",
        minzoom: 0,
        maxzoom: layerMaxzoom,
      },
    ],
  };
}

const BASEMAP_STYLES: Record<Exclude<BasemapId, "satellite">, { version: 8; sources: Record<string, unknown>; layers: Array<Record<string, unknown>> }> = {
  hybrid: rasterStyle(["https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"], "Imagery © Google", 20),
  dark: rasterStyle(
    ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
    "Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community",
    16,
    16,
  ),
};

function satelliteStyle(
  apiBaseUrl: string,
  source: SatelliteBasemapSource,
): { version: 8; sources: Record<string, unknown>; layers: Array<Record<string, unknown>> } {
  return {
    version: 8 as const,
    sources: {
      global: {
        type: "raster" as const,
        tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        tileSize: 256,
        attribution: ESRI_ATTRIBUTION,
        maxzoom: 19,
      },
      bayern20cm: {
        type: "raster" as const,
        tiles: [`${apiBaseUrl}/api/tiles/rgb20cm-planegg/{z}/{x}/{y}.png`],
        tileSize: 256,
        attribution: "© Bayerische Vermessungsverwaltung",
        maxzoom: 20,
      },
    },
    layers: [
      {
        id: "base-global",
        type: "raster" as const,
        source: "global",
        minzoom: 0,
        maxzoom: 24,
      },
      {
        id: "overlay-bayern-20cm",
        type: "raster" as const,
        source: "bayern20cm",
        minzoom: 0,
        maxzoom: 24,
        paint: {
          "raster-opacity": source === "bayern-20cm" ? 1 : 0,
          "raster-fade-duration": 0,
          "raster-resampling": "nearest",
        },
      },
    ],
  };
}

const TRANSPARENT_STYLE = {
  version: 8 as const,
  sources: {},
  layers: [],
};

export const BASEMAP_OPTIONS: { id: BasemapId; label: string }[] = [
  { id: "satellite", label: "Satellite" },
  { id: "hybrid", label: "Hybrid" },
  { id: "dark", label: "Dark" },
];

function drawnPolygonFeature(points: [number, number][]): Feature<Polygon> | null {
  if (points.length < 3) return null;
  const ring = [...points, points[0]];
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [ring] },
  };
}

function CompassControl({ onReset, bearing }: { onReset: () => void; bearing: number }) {
  return (
    <button
      type="button"
      onClick={onReset}
      title="Reset to north"
      aria-label="Reset to north"
      className="glass-panel flex h-14 w-14 items-center justify-center rounded-full text-cyan-300 transition hover:text-cyan-100"
    >
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ transform: `rotate(${-bearing}deg)`, transition: "transform 150ms linear" }}
      >
        <path d="M12 2L15.5 12L12 10L8.5 12L12 2Z" fill="#f87171" />
        <path d="M12 22L8.5 12L12 14L15.5 12L12 22Z" fill="#cbd5e1" />
      </svg>
    </button>
  );
}

export function MapCanvas({
  layers,
  activeLayerOrder = [],
  apiBaseUrl,
  drawMode = false,
  drawnPoints = [],
  onMapClick,
  onBuildingClick,
  onNutzungClick,
  basemap = "satellite",
  satelliteBasemapSource = "bayern-20cm",
  terrain3dEnabled = false,
  terrainSource = "dem",
  terrainAvailable = false,
  terrainSourcesAvailable = { dem: true, dom: true, dsm: true },
  terrainExaggeration = 1.8,
  hillshadeStrength = 0.7,
  selectedBuildingId = null,
  selectedNutzungId = null,
  changeDetectionGeojson = null,
  changeDetectionVisible = true,
  changeDetectionOpacity = 0.7,
  swipeEnabled = false,
  swipePosition = 0.5,
  onSwipePositionChange,
  swipeLeftLayerId = null,
  swipeRightLayerId = null,
  swipeLeftLabel = "Left",
  swipeRightLabel = "Right",
  terrainOffIntentVersion = 0,
  onEffectiveTerrainModeChange,
}: {
  layers: CatalogLayer[];
  activeLayerOrder?: string[];
  apiBaseUrl: string;
  drawMode?: boolean;
  drawnPoints?: [number, number][];
  onMapClick?: (lngLat: [number, number]) => void;
  onBuildingClick?: (payload: ClickedVectorFeature) => void;
  onNutzungClick?: (payload: ClickedVectorFeature) => void;
  basemap?: BasemapId;
  satelliteBasemapSource?: SatelliteBasemapSource;
  terrain3dEnabled?: boolean;
  terrainSource?: TerrainSourceId;
  terrainAvailable?: boolean;
  terrainSourcesAvailable?: Record<TerrainSourceId, boolean>;
  terrainExaggeration?: number;
  hillshadeStrength?: number;
  selectedBuildingId?: string | null;
  selectedNutzungId?: string | null;
  changeDetectionGeojson?: Record<string, unknown> | null;
  changeDetectionVisible?: boolean;
  changeDetectionOpacity?: number;
  swipeEnabled?: boolean;
  swipePosition?: number;
  onSwipePositionChange?: (position: number) => void;
  swipeLeftLayerId?: string | null;
  swipeRightLayerId?: string | null;
  swipeLeftLabel?: string;
  swipeRightLabel?: string;
  terrainOffIntentVersion?: number;
  onEffectiveTerrainModeChange?: (mode: "off" | "dem" | "dom" | "dsm") => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapRef>(null);
  const compareMapRef = useRef<MapRef>(null);
  const previousTerrainModeRef = useRef<"off" | "dem" | "dom" | "dsm">("off");
  const previousOffIntentVersionRef = useRef<number>(terrainOffIntentVersion);
  const preTerrainViewRef = useRef<{ longitude: number; latitude: number; zoom: number; bearing: number } | null>(null);
  const [viewState, setViewState] = useState(PLANEGG_CENTER);
  const [bearing, setBearing] = useState(0);
  const [terrainRevision, setTerrainRevision] = useState(0);
  const [tileVersion] = useState(() => Date.now());
  const [isDraggingSwipe, setIsDraggingSwipe] = useState(false);
  const [effectiveTerrainMode, setEffectiveTerrainMode] = useState<"off" | "dem" | "dom" | "dsm">("off");
  const domMode = effectiveTerrainMode === "dom" || effectiveTerrainMode === "dsm";
  const terrainSourceId = `terrain-${terrainSource}`;

  const swipeIsActive = Boolean(swipeEnabled && swipeLeftLayerId && swipeRightLayerId && swipeLeftLayerId !== swipeRightLayerId);
  const effectiveSwipeActive = swipeIsActive && effectiveTerrainMode === "off";

  useEffect(() => {
    onEffectiveTerrainModeChange?.(effectiveTerrainMode);
  }, [effectiveTerrainMode, onEffectiveTerrainModeChange]);

  useEffect(() => {
    if (terrainOffIntentVersion === previousOffIntentVersionRef.current) return;
    previousOffIntentVersionRef.current = terrainOffIntentVersion;

    const map = mapRef.current?.getMap();
    if (!map) return;

    try {
      map.setTerrain(null);
    } catch {
      // no-op
    }
    previousTerrainModeRef.current = "off";
    setEffectiveTerrainMode("off");

    const baseline = preTerrainViewRef.current;
    map.easeTo({
      center: baseline ? [baseline.longitude, baseline.latitude] : undefined,
      zoom: baseline ? baseline.zoom : Math.max(12.5, map.getZoom()),
      pitch: 0,
      bearing: baseline ? baseline.bearing : 0,
      offset: [0, 0],
      duration: 360,
    });
  }, [terrainOffIntentVersion]);

  useEffect(() => {
    if (!effectiveSwipeActive) return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    setViewState({
      longitude: map.getCenter().lng,
      latitude: map.getCenter().lat,
      zoom: map.getZoom(),
      pitch: map.getPitch(),
      bearing: map.getBearing(),
    });
  }, [effectiveSwipeActive]);

  const visibleLayers = useMemo(() => {
    const isPriority3dLayer = (layer: CatalogLayer) =>
      layer.layer_type === "vector" &&
      (layer.style?.color_scale === "buildings3d" || layer.style?.color_scale === "trees3d");

    const orderRank = new globalThis.Map<string, number>();
    activeLayerOrder.forEach((id, idx) => {
      orderRank.set(id, idx);
    });

    const sorted = [...layers]
      .filter((layer) => layer.default_visible && layer.available)
      .sort((a, b) => {
        const aRank = orderRank.get(a.id);
        const bRank = orderRank.get(b.id);
        if (aRank !== undefined && bRank !== undefined) {
          // activeLayerOrder is top->bottom; map rendering needs bottom->top
          return bRank - aRank;
        }
        if (aRank !== undefined) return 1;
        if (bRank !== undefined) return -1;
        return a.default_order - b.default_order;
      });

    if (drawMode) {
      return sorted.filter((layer) => !isPriority3dLayer(layer));
    }

    return sorted;
  }, [layers, drawMode, activeLayerOrder]);

  const baseVisibleLayers = useMemo(() => {
    if (!effectiveSwipeActive || !swipeLeftLayerId || !swipeRightLayerId) return visibleLayers;
    return visibleLayers.filter((layer) => layer.id !== swipeRightLayerId);
  }, [visibleLayers, effectiveSwipeActive, swipeLeftLayerId, swipeRightLayerId]);

  const swipeRightLayer = useMemo(() => {
    if (!effectiveSwipeActive || !swipeRightLayerId) return null;
    return layers.find((layer) => layer.id === swipeRightLayerId && layer.layer_type === "raster" && layer.available) ?? null;
  }, [layers, effectiveSwipeActive, swipeRightLayerId]);

  const buildingInteractiveLayerIds = useMemo(
    () =>
      visibleLayers
        .filter((layer) => layer.layer_type === "vector" && layer.style?.color_scale === "buildings3d")
        .flatMap((layer) =>
          domMode
            ? [`${layer.id}-fill-2d`, `${layer.id}-outline-2d`]
            : [`${layer.id}-extrusion-3d`, `${layer.id}-outline-3d`],
        ),
    [visibleLayers, domMode],
  );

  const nutzungInteractiveLayerIds = useMemo(
    () =>
      visibleLayers
        .filter((layer) => layer.layer_type === "vector" && layer.style?.color_scale === "nutzung")
        .flatMap((layer) => [`${layer.id}-hit`, `${layer.id}-fill`, `${layer.id}-line`]),
    [visibleLayers],
  );

  const interactiveLayerIds = useMemo(
    () => (drawMode ? [] : [...buildingInteractiveLayerIds, ...nutzungInteractiveLayerIds]),
    [buildingInteractiveLayerIds, nutzungInteractiveLayerIds, drawMode],
  );

  const updateSwipePosition = useCallback(
    (clientX: number) => {
      if (!onSwipePositionChange) return;
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect || rect.width <= 0) return;
      const ratio = Math.min(0.95, Math.max(0.05, (clientX - rect.left) / rect.width));
      onSwipePositionChange(ratio);
    },
    [onSwipePositionChange],
  );

  useEffect(() => {
    if (!isDraggingSwipe) return;
    const handleMove = (event: MouseEvent) => {
      updateSwipePosition(event.clientX);
    };
    const handleUp = () => {
      setIsDraggingSwipe(false);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [isDraggingSwipe, updateSwipePosition]);

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      if (drawMode) {
        onMapClick?.([event.lngLat.lng, event.lngLat.lat]);
        return;
      }

      const map = mapRef.current?.getMap();
      const nutzungLayerIds = new Set(nutzungInteractiveLayerIds);
      const buildingLayerIds = new Set(buildingInteractiveLayerIds);

      const desiredLayerIds = [...nutzungInteractiveLayerIds, ...buildingInteractiveLayerIds];
      const queryableLayerIds = map
        ? desiredLayerIds.filter((layerId) => Boolean(map.getLayer(layerId)))
        : [];

      let clickFeatures = event.features ?? [];
      if (map && queryableLayerIds.length > 0) {
        try {
          clickFeatures = map.queryRenderedFeatures(event.point, {
            layers: queryableLayerIds,
          });
        } catch {
          clickFeatures = event.features ?? [];
        }
      }

      const nutzungFeature = clickFeatures.find((feature) => nutzungLayerIds.has(String(feature.layer.id)));
      if (nutzungFeature && onNutzungClick) {
        const props = (nutzungFeature.properties ?? {}) as Record<string, unknown>;
        const id = String(props.oid ?? props.id ?? nutzungFeature.id ?? "unknown-nutzung");
        onNutzungClick({
          id,
          properties: props,
          geometry: nutzungFeature.geometry as unknown as Record<string, unknown>,
          lngLat: [event.lngLat.lng, event.lngLat.lat],
        });
        return;
      }

      const buildingFeature = clickFeatures.find((feature) => buildingLayerIds.has(String(feature.layer.id)));

      if (buildingFeature && onBuildingClick) {
        const props = (buildingFeature.properties ?? {}) as Record<string, unknown>;
        const id = String(props.id ?? buildingFeature.id ?? "unknown-building");
        onBuildingClick({
          id,
          properties: props,
          geometry: buildingFeature.geometry as unknown as Record<string, unknown>,
          lngLat: [event.lngLat.lng, event.lngLat.lat],
        });
        return;
      }

      onMapClick?.([event.lngLat.lng, event.lngLat.lat]);
    },
    [drawMode, onMapClick, onBuildingClick, onNutzungClick, buildingInteractiveLayerIds, nutzungInteractiveLayerIds],
  );

  const polygon = drawnPolygonFeature(drawnPoints);
  const hasDrawPolygon = Boolean(polygon);
  const mapStyle = useMemo(() => {
    if (basemap === "satellite") {
      return satelliteStyle(apiBaseUrl, satelliteBasemapSource);
    }
    return BASEMAP_STYLES[basemap];
  }, [basemap, apiBaseUrl, satelliteBasemapSource]);

  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;

      const sourceAvailable = Boolean(terrainSourcesAvailable[terrainSource]);
      const nextDomMode = terrainSource === "dom" || terrainSource === "dsm";
      const effectiveExaggeration = nextDomMode ? 1 : terrainExaggeration;
      const wantsTerrain = terrain3dEnabled && terrainAvailable && sourceAvailable;
      const nextTerrainMode: "off" | "dem" | "dom" | "dsm" = wantsTerrain ? terrainSource : "off";
      const previousTerrainMode = previousTerrainModeRef.current;
      const modeChanged = previousTerrainMode !== nextTerrainMode;

      const terrainShouldBeEnabled = nextTerrainMode !== "off";
      if (terrainShouldBeEnabled) {
        if (modeChanged && previousTerrainMode === "off") {
          preTerrainViewRef.current = {
            longitude: map.getCenter().lng,
            latitude: map.getCenter().lat,
            zoom: map.getZoom(),
            bearing: map.getBearing(),
          };
        }

        try {
          map.setTerrain({ source: terrainSourceId, exaggeration: effectiveExaggeration });
        } catch (error) {
          console.error("Failed to enable terrain mode", {
            requestedMode: nextTerrainMode,
            terrainSourceId,
            error,
          });
          setEffectiveTerrainMode("off");
          window.setTimeout(() => {
            setTerrainRevision((v) => v + 1);
          }, 180);
          return;
        }

        if (modeChanged && effectiveExaggeration > 0) {
          const currentZoom = map.getZoom();
          const zoomLiftFactor = Math.max(1, Math.min(4, Math.pow(1.28, Math.max(0, currentZoom - 13))));
          const pitchTarget = nextDomMode ? 50 : (currentZoom >= 16 ? 40 : 45);
          const baseZoomTarget = currentZoom >= 16 ? currentZoom - 0.45 : currentZoom >= 15 ? currentZoom - 0.25 : currentZoom;
          const heightDeltaCompensation = (previousTerrainMode === "dom" || previousTerrainMode === "dsm") && nextTerrainMode === "dem"
            ? -0.15
            : previousTerrainMode === "dem" && nextDomMode
              ? 0.1
              : 0;
          const zoomTarget = baseZoomTarget + heightDeltaCompensation;
          map.easeTo({
            pitch: pitchTarget,
            zoom: zoomTarget,
            offset: [0, -Math.round(22 * effectiveExaggeration * zoomLiftFactor)],
            duration: 320,
          });
        }
        previousTerrainModeRef.current = nextTerrainMode;
        setEffectiveTerrainMode(nextTerrainMode);
        return;
      }

      try {
        map.setTerrain(null);
      } catch (error) {
        console.error("Failed to disable terrain mode", { error });
      }

      if (modeChanged && !terrain3dEnabled) {
        const baseline = preTerrainViewRef.current;
        const offZoom = baseline
          ? baseline.zoom
          : previousTerrainMode === "dem"
            ? map.getZoom() + 0.2
            : Math.max(12.5, map.getZoom());
        map.easeTo({
          center: baseline ? [baseline.longitude, baseline.latitude] : undefined,
          pitch: 0,
          bearing: baseline ? baseline.bearing : 0,
          zoom: offZoom,
          offset: [0, 0],
          duration: 280,
        });
      }
      previousTerrainModeRef.current = "off";
      setEffectiveTerrainMode("off");
    return;
  }, [terrain3dEnabled, terrainAvailable, terrainExaggeration, terrainRevision, mapStyle, terrainSourceId, terrainSource, terrainSourcesAvailable]);

  useEffect(() => {
    const applyLayerOrder = () => {
      const map = mapRef.current?.getMap();
      if (!map) return;

      const styleLayers = map.getStyle()?.layers ?? [];

      // Enforce requested active-layer z-order (top -> bottom in UI).
      // moveLayer() places a layer on top, so apply bottom -> top.
      for (const sourceId of [...activeLayerOrder].reverse()) {
        const sourceLayerIds = styleLayers
          .filter((entry) => String((entry as { source?: string }).source ?? "") === sourceId)
          .map((entry) => entry.id);

        for (const styleLayerId of sourceLayerIds) {
          if (map.getLayer(styleLayerId)) {
            map.moveLayer(styleLayerId);
          }
        }
      }

      // Keep drawn selection overlays above all other layers.
      const drawLayerOrder = ["draw-polygon-fill", "draw-polygon-line", "draw-points-layer"];
      for (const layerId of drawLayerOrder) {
        if (map.getLayer(layerId)) {
          map.moveLayer(layerId);
        }
      }
    };

    const frame = window.requestAnimationFrame(applyLayerOrder);
    const timer = window.setTimeout(applyLayerOrder, 60);

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [terrainRevision, drawnPoints.length, hasDrawPolygon, activeLayerOrder, domMode, visibleLayers.length]);

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <Map
        ref={mapRef}
        initialViewState={PLANEGG_CENTER}
        {...(effectiveSwipeActive
          ? {
              longitude: viewState.longitude,
              latitude: viewState.latitude,
              zoom: viewState.zoom,
              pitch: viewState.pitch,
              bearing: viewState.bearing,
            }
          : {})}
        mapStyle={mapStyle as unknown as StyleSpecification}
        style={{ width: "100%", height: "100%" }}
        cursor={drawMode ? "crosshair" : "grab"}
        onClick={handleClick}
        interactiveLayerIds={interactiveLayerIds}
        onMove={(event) => {
          if (effectiveSwipeActive) {
            setViewState(event.viewState);
          }
          setBearing(event.viewState.bearing ?? 0);
        }}
        onLoad={() => {
          setTerrainRevision((v) => v + 1);
        }}
        onStyleData={() => setTerrainRevision((v) => v + 1)}
      >
        <Source
          id="terrain-dem"
          type="raster-dem"
          tiles={[`${apiBaseUrl}/api/terrain/{z}/{x}/{y}.png?source=dem&v=${tileVersion}`]}
          tileSize={256}
          encoding="terrarium"
          maxzoom={14}
        />

        <Source
          id="terrain-dom"
          type="raster-dem"
          tiles={[`${apiBaseUrl}/api/terrain/{z}/{x}/{y}.png?source=dom&v=${tileVersion}`]}
          tileSize={256}
          encoding="terrarium"
          maxzoom={13}
        />

        <Source
          id="terrain-dsm"
          type="raster-dem"
          tiles={[`${apiBaseUrl}/api/terrain/{z}/{x}/{y}.png?source=dsm&v=${tileVersion}`]}
          tileSize={256}
          encoding="terrarium"
          maxzoom={14}
        />

        {effectiveTerrainMode === "dem" ? (
          <Layer
            id="terrain-hillshade"
            type="hillshade"
            source={terrainSourceId}
            paint={{
              "hillshade-exaggeration": hillshadeStrength,
              "hillshade-shadow-color": "#0f172a",
              "hillshade-highlight-color": "#e2e8f0",
            }}
          />
        ) : null}

        {baseVisibleLayers.map((layer) => {
          if (layer.layer_type === "raster") {
            const isRgb = layer.value_type === "rgb" || layer.style?.color_scale === "rgb";
            const interpolation = (layer.style?.interpolation ?? "").toLowerCase();
            const useNearest = layer.value_type === "categorical" || isRgb || interpolation === "nearest";
            return (
              <Source
                key={layer.id}
                id={layer.id}
                type="raster"
                tiles={[`${apiBaseUrl}/api/tiles/${layer.id}/{z}/{x}/{y}.png?v=${tileVersion}`]}
                tileSize={256}
              >
                <Layer
                  id={`${layer.id}-layer`}
                  type="raster"
                  paint={{
                    "raster-opacity": layer.default_opacity,
                    "raster-resampling": useNearest ? "nearest" : "linear",
                    ...(useNearest ? { "raster-fade-duration": 0 } : {}),
                    ...(isRgb
                      ? {
                          "raster-brightness-min": 0.0,
                          "raster-brightness-max": 1,
                        }
                      : {}),
                  }}
                />
              </Source>
            );
          }

          if (layer.layer_type === "vector") {
            const color = VECTOR_COLORS[layer.style?.color_scale ?? ""] ?? "#22d3ee";
            const dashed = layer.style?.color_scale === "context";

            if (layer.style?.color_scale === "buildings3d") {
              const buildingsUrl = `${apiBaseUrl}/api/vectors/${layer.id}`;
              const modeSuffix = "3d";
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const extrusionHeightExpr: any = [
                "coalesce",
                [
                  "max",
                  1,
                  [
                    "-",
                    ["coalesce", ["to-number", ["get", "roof_height"]], 0],
                    ["coalesce", ["to-number", ["get", "ground_height"]], 0],
                  ],
                ],
                ["max", 1, ["coalesce", ["to-number", ["get", "height"]], 6]],
                6,
              ];

              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const selectedExtrusionHeightExpr: any = ["+", extrusionHeightExpr, 0.5];

              return (
                <Source key={`${layer.id}-${modeSuffix}`} id={layer.id} type="geojson" data={buildingsUrl}>
                  <Layer
                    id={`${layer.id}-extrusion-3d`}
                    type="fill-extrusion"
                    paint={{
                      "fill-extrusion-color": color,
                      "fill-extrusion-height": extrusionHeightExpr,
                      "fill-extrusion-base": 0,
                      "fill-extrusion-opacity": layer.default_opacity,
                      "fill-extrusion-vertical-gradient": true,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-outline-3d`}
                    type="line"
                    paint={{
                      "line-color": "#d1d5db",
                      "line-width": 0.6,
                      "line-opacity": 0.6,
                    }}
                  />
                  {selectedBuildingId ? (
                    <Layer
                      id={`${layer.id}-selected-extrusion`}
                      type="fill-extrusion"
                      filter={["==", ["to-string", ["get", "id"]], selectedBuildingId]}
                      paint={{
                        "fill-extrusion-color": "#fde047",
                        "fill-extrusion-height": selectedExtrusionHeightExpr,
                        "fill-extrusion-base": 0,
                        "fill-extrusion-opacity": 1,
                        "fill-extrusion-vertical-gradient": true,
                      }}
                    />
                  ) : null}
                  {selectedBuildingId ? (
                    <Layer
                      id={`${layer.id}-selected-outline`}
                      type="line"
                      filter={["==", ["to-string", ["get", "id"]], selectedBuildingId]}
                      paint={{
                        "line-color": "#fde047",
                        "line-width": 4,
                        "line-opacity": 1,
                        "line-blur": 0.8,
                      }}
                    />
                  ) : null}
                </Source>
              );
            }

            if (layer.style?.color_scale === "trees3d") {
              const treeGreen = "#16a34a";
              const treeGreenDark = "#15803d";
              const treeGreenLight = "#22c55e";
              const trunkBrown = "#6b4f2a";
              const modeSuffix = "3d";
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const canopyBaseExpr: any = ["coalesce", ["to-number", ["get", "canopy_base"]], 1.5];
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const canopyTopExpr: any = ["coalesce", ["to-number", ["get", "height"]], 12];
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const canopyShellBaseExpr: any = ["coalesce", ["to-number", ["get", "canopy_shell_base"]], canopyBaseExpr];
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const canopyShellTopExpr: any = ["coalesce", ["to-number", ["get", "canopy_shell_top"]], canopyTopExpr];

              return (
                <Source
                  key={`${layer.id}-${modeSuffix}`}
                  id={layer.id}
                  type="geojson"
                  data={`${apiBaseUrl}/api/vectors/${layer.id}`}
                >
                  <Layer
                    id={`${layer.id}-point-halo`}
                    type="circle"
                    maxzoom={13}
                    filter={["==", ["get", "tree_part"], "point"]}
                    paint={{
                      "circle-color": treeGreen,
                      "circle-opacity": 0.12,
                      "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 3, 11, 5, 13, 7],
                    }}
                  />
                  <Layer
                    id={`${layer.id}-trunk`}
                    type="fill-extrusion"
                    minzoom={12}
                    filter={["==", ["get", "tree_part"], "trunk"]}
                    paint={{
                      "fill-extrusion-color": trunkBrown,
                      "fill-extrusion-height": ["coalesce", ["to-number", ["get", "trunk_height"]], 2.4],
                      "fill-extrusion-base": 0,
                      "fill-extrusion-opacity": Math.min(1, layer.default_opacity + 0.08),
                      "fill-extrusion-vertical-gradient": true,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-canopy-lower`}
                    type="fill-extrusion"
                    minzoom={12}
                    filter={[
                      "any",
                      ["==", ["get", "tree_part"], "canopy"],
                      ["==", ["get", "tree_part"], "canopy_lower"],
                    ]}
                    paint={{
                      "fill-extrusion-color": treeGreen,
                      "fill-extrusion-height": canopyShellTopExpr,
                      "fill-extrusion-base": canopyShellBaseExpr,
                      "fill-extrusion-opacity": Math.max(0.68, layer.default_opacity * 0.82),
                      "fill-extrusion-vertical-gradient": true,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-canopy-mid`}
                    type="fill-extrusion"
                    minzoom={12}
                    filter={["==", ["get", "tree_part"], "canopy_mid"]}
                    paint={{
                      "fill-extrusion-color": "#1fb857",
                      "fill-extrusion-height": canopyShellTopExpr,
                      "fill-extrusion-base": canopyShellBaseExpr,
                      "fill-extrusion-opacity": Math.max(0.58, layer.default_opacity * 0.74),
                      "fill-extrusion-vertical-gradient": true,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-canopy-top`}
                    type="fill-extrusion"
                    minzoom={12}
                    filter={["==", ["get", "tree_part"], "canopy_upper"]}
                    paint={{
                      "fill-extrusion-color": treeGreenLight,
                      "fill-extrusion-height": canopyShellTopExpr,
                      "fill-extrusion-base": canopyShellBaseExpr,
                      "fill-extrusion-opacity": Math.max(0.5, layer.default_opacity * 0.66),
                      "fill-extrusion-vertical-gradient": true,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-canopy-outline`}
                    type="line"
                    minzoom={12}
                    filter={[
                      "any",
                      ["==", ["get", "tree_part"], "canopy"],
                      ["==", ["get", "tree_part"], "canopy_lower"],
                      ["==", ["get", "tree_part"], "canopy_mid"],
                      ["==", ["get", "tree_part"], "canopy_upper"],
                    ]}
                    paint={{
                      "line-color": treeGreenDark,
                      "line-width": 0.45,
                      "line-opacity": 0.45,
                    }}
                  />
                </Source>
              );
            }

            if (layer.style?.color_scale === "population") {
              return (
                <Source key={layer.id} id={layer.id} type="geojson" data={`${apiBaseUrl}/api/vectors/${layer.id}`}>
                  <Layer
                    id={`${layer.id}-fill`}
                    type="fill"
                    paint={{
                      "fill-color": [
                        "interpolate",
                        ["linear"],
                        ["coalesce", ["to-number", ["get", "population"]], 0],
                        0,
                        "#e2e8f0",
                        25,
                        "#93c5fd",
                        100,
                        "#3b82f6",
                        250,
                        "#f59e0b",
                        500,
                        "#ef4444",
                      ],
                      "fill-opacity": layer.default_opacity,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-line`}
                    type="line"
                    paint={{
                      "line-color": "#0f172a",
                      "line-width": 0.2,
                      "line-opacity": 0.25,
                    }}
                  />
                </Source>
              );
            }

            if (layer.style?.color_scale === "nutzung") {
              return (
                <Source key={layer.id} id={layer.id} type="geojson" data={`${apiBaseUrl}/api/vectors/${layer.id}`}>
                  <Layer
                    id={`${layer.id}-hit`}
                    type="fill"
                    paint={{
                      "fill-color": "#000000",
                      "fill-opacity": 0.01,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-fill`}
                    type="fill"
                    paint={{
                      "fill-color": NUTZUNG_COLOR_MATCH_EXPRESSION,
                      "fill-opacity": Math.max(0.2, layer.default_opacity * 0.62),
                    }}
                  />
                  <Layer
                    id={`${layer.id}-line`}
                    type="line"
                    paint={{
                      "line-color": "#0f172a",
                      "line-width": 0.45,
                      "line-opacity": Math.max(0.35, layer.default_opacity * 0.7),
                    }}
                  />
                  {selectedNutzungId ? (
                    <Layer
                      id={`${layer.id}-selected-fill`}
                      type="fill"
                      filter={["==", ["to-string", ["get", "oid"]], selectedNutzungId]}
                      paint={{
                        "fill-color": "#fde047",
                        "fill-opacity": 0.3,
                      }}
                    />
                  ) : null}
                  {selectedNutzungId ? (
                    <Layer
                      id={`${layer.id}-selected-line`}
                      type="line"
                      filter={["==", ["to-string", ["get", "oid"]], selectedNutzungId]}
                      paint={{
                        "line-color": "#fde047",
                        "line-width": 2.2,
                        "line-opacity": 1,
                      }}
                    />
                  ) : null}
                </Source>
              );
            }

            return (
              <Source key={layer.id} id={layer.id} type="geojson" data={`${apiBaseUrl}/api/vectors/${layer.id}`}>
                <Layer
                  id={`${layer.id}-fill`}
                  type="fill"
                  paint={{
                    "fill-color": color,
                    "fill-opacity": layer.default_opacity * 0.12,
                  }}
                />
                <Layer
                  id={`${layer.id}-line`}
                  type="line"
                  paint={{
                    "line-color": color,
                    "line-width": dashed ? 2 : 3,
                    "line-opacity": layer.default_opacity,
                    ...(dashed ? { "line-dasharray": [2, 2] } : {}),
                  }}
                />
              </Source>
            );
          }

          return null;
        })}

        {changeDetectionGeojson && changeDetectionVisible ? (
          <Source id="change-detection" type="geojson" data={changeDetectionGeojson as never}>
            <Layer
              id="change-detection-fill"
              type="fill"
              paint={{
                "fill-color": [
                  "match",
                  ["coalesce", ["get", "confidence_level"], "low"],
                  "high",
                  "#ef4444",
                  "medium",
                  "#f97316",
                  "#facc15",
                ],
                "fill-opacity": [
                  "*",
                  changeDetectionOpacity,
                  [
                    "match",
                    ["coalesce", ["get", "confidence_level"], "low"],
                    "high",
                    0.45,
                    "medium",
                    0.34,
                    0.24,
                  ],
                ],
              }}
            />
            <Layer
              id="change-detection-line"
              type="line"
              paint={{
                "line-color": [
                  "match",
                  ["coalesce", ["get", "confidence_level"], "low"],
                  "high",
                  "#fca5a5",
                  "medium",
                  "#fdba74",
                  "#fde68a",
                ],
                "line-width": 1.1,
                "line-opacity": Math.min(1, changeDetectionOpacity + 0.15),
              }}
            />
          </Source>
        ) : null}

        {drawnPoints.length > 0 ? (
          <Source
            id="draw-points"
            type="geojson"
            data={{
              type: "FeatureCollection",
              features: drawnPoints.map((p) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: p } })),
            }}
          >
            <Layer id="draw-points-layer" type="circle" paint={{ "circle-radius": 5, "circle-color": "#f97316" }} />
          </Source>
        ) : null}

        {polygon ? (
          <Source id="draw-polygon" type="geojson" data={polygon}>
            <Layer
              id="draw-polygon-fill"
              type="fill"
              paint={{ "fill-color": "#f97316", "fill-opacity": 0.2 }}
            />
            <Layer
              id="draw-polygon-line"
              type="line"
              paint={{ "line-color": "#f97316", "line-width": 2 }}
            />
          </Source>
        ) : null}

      </Map>

      {effectiveSwipeActive && swipeRightLayer ? (
        <div
          key={`swipe-overlay-${swipeRightLayer.id}`}
          className="pointer-events-none absolute inset-0 z-[8] overflow-hidden"
          style={{ clipPath: `inset(0 0 0 ${Math.max(0, Math.min(1, swipePosition)) * 100}%)` }}
        >
          <Map
            key={`swipe-map-${swipeRightLayer.id}`}
            ref={compareMapRef}
            longitude={viewState.longitude}
            latitude={viewState.latitude}
            zoom={viewState.zoom}
            pitch={viewState.pitch}
            bearing={viewState.bearing}
            mapStyle={TRANSPARENT_STYLE}
            style={{ width: "100%", height: "100%" }}
            interactive={false}
          >
            <Source
              key={`swipe-source-${swipeRightLayer.id}`}
              id="swipe-compare-raster"
              type="raster"
              tiles={[`${apiBaseUrl}/api/tiles/${swipeRightLayer.id}/{z}/{x}/{y}.png?v=${tileVersion}`]}
              tileSize={256}
            >
              <Layer
                id="swipe-compare-raster-layer"
                type="raster"
                paint={{
                  "raster-opacity": swipeRightLayer.default_opacity,
                  "raster-resampling":
                    swipeRightLayer.value_type === "categorical" ||
                    (swipeRightLayer.style?.interpolation ?? "").toLowerCase() === "nearest"
                      ? "nearest"
                      : "linear",
                  "raster-fade-duration": 0,
                }}
              />
            </Source>
            {visibleLayers
              .filter((layer) => layer.layer_type === "vector" && layer.style?.color_scale === "trees3d")
              .map((layer) => {
                const treeGreen = "#16a34a";
                const treeGreenDark = "#15803d";
                const treeGreenLight = "#22c55e";
                const trunkBrown = "#6b4f2a";
                const modeSuffix = "3d";
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const canopyBaseExpr: any = ["coalesce", ["to-number", ["get", "canopy_base"]], 1.5];
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const canopyTopExpr: any = ["coalesce", ["to-number", ["get", "height"]], 12];
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const canopyShellBaseExpr: any = ["coalesce", ["to-number", ["get", "canopy_shell_base"]], canopyBaseExpr];
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const canopyShellTopExpr: any = ["coalesce", ["to-number", ["get", "canopy_shell_top"]], canopyTopExpr];

                return (
                  <Source
                    key={`swipe-${layer.id}-${modeSuffix}`}
                    id={`swipe-${layer.id}`}
                    type="geojson"
                    data={`${apiBaseUrl}/api/vectors/${layer.id}`}
                  >
                    <Layer
                      id={`swipe-${layer.id}-point-halo`}
                      type="circle"
                      maxzoom={13}
                      filter={["==", ["get", "tree_part"], "point"]}
                      paint={{
                        "circle-color": treeGreen,
                        "circle-opacity": 0.12,
                        "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 3, 11, 5, 13, 7],
                      }}
                    />
                    <Layer
                      id={`swipe-${layer.id}-trunk`}
                      type="fill-extrusion"
                      minzoom={12}
                      filter={["==", ["get", "tree_part"], "trunk"]}
                      paint={{
                        "fill-extrusion-color": trunkBrown,
                        "fill-extrusion-height": ["coalesce", ["to-number", ["get", "trunk_height"]], 2.4],
                        "fill-extrusion-base": 0,
                        "fill-extrusion-opacity": Math.min(1, layer.default_opacity + 0.08),
                        "fill-extrusion-vertical-gradient": true,
                      }}
                    />
                    <Layer
                      id={`swipe-${layer.id}-canopy-lower`}
                      type="fill-extrusion"
                      minzoom={12}
                      filter={[
                        "any",
                        ["==", ["get", "tree_part"], "canopy"],
                        ["==", ["get", "tree_part"], "canopy_lower"],
                      ]}
                      paint={{
                        "fill-extrusion-color": treeGreen,
                        "fill-extrusion-height": canopyShellTopExpr,
                        "fill-extrusion-base": canopyShellBaseExpr,
                        "fill-extrusion-opacity": Math.max(0.7, layer.default_opacity * 0.88),
                        "fill-extrusion-vertical-gradient": true,
                      }}
                    />
                    <Layer
                      id={`swipe-${layer.id}-canopy-mid`}
                      type="fill-extrusion"
                      minzoom={12}
                      filter={["==", ["get", "tree_part"], "canopy_mid"]}
                      paint={{
                        "fill-extrusion-color": "#1fb857",
                        "fill-extrusion-height": canopyShellTopExpr,
                        "fill-extrusion-base": canopyShellBaseExpr,
                        "fill-extrusion-opacity": Math.max(0.58, layer.default_opacity * 0.74),
                        "fill-extrusion-vertical-gradient": true,
                      }}
                    />
                    <Layer
                      id={`swipe-${layer.id}-canopy-top`}
                      type="fill-extrusion"
                      minzoom={12}
                      filter={["==", ["get", "tree_part"], "canopy_upper"]}
                      paint={{
                        "fill-extrusion-color": treeGreenLight,
                        "fill-extrusion-height": canopyShellTopExpr,
                        "fill-extrusion-base": canopyShellBaseExpr,
                        "fill-extrusion-opacity": Math.max(0.5, layer.default_opacity * 0.66),
                        "fill-extrusion-vertical-gradient": true,
                      }}
                    />
                    <Layer
                      id={`swipe-${layer.id}-canopy-outline`}
                      type="line"
                      minzoom={12}
                      filter={[
                        "any",
                        ["==", ["get", "tree_part"], "canopy"],
                        ["==", ["get", "tree_part"], "canopy_lower"],
                        ["==", ["get", "tree_part"], "canopy_mid"],
                        ["==", ["get", "tree_part"], "canopy_upper"],
                      ]}
                      paint={{
                        "line-color": treeGreenDark,
                        "line-width": 0.45,
                        "line-opacity": 0.45,
                      }}
                    />
                  </Source>
                );
              })}
            {changeDetectionGeojson && changeDetectionVisible ? (
              <Source id="change-detection-swipe" type="geojson" data={changeDetectionGeojson as never}>
                <Layer
                  id="change-detection-fill-swipe"
                  type="fill"
                  paint={{
                    "fill-color": [
                      "match",
                      ["coalesce", ["get", "confidence_level"], "low"],
                      "high",
                      "#ef4444",
                      "medium",
                      "#f97316",
                      "#facc15",
                    ],
                    "fill-opacity": [
                      "*",
                      changeDetectionOpacity,
                      [
                        "match",
                        ["coalesce", ["get", "confidence_level"], "low"],
                        "high",
                        0.45,
                        "medium",
                        0.34,
                        0.24,
                      ],
                    ],
                  }}
                />
                <Layer
                  id="change-detection-line-swipe"
                  type="line"
                  paint={{
                    "line-color": [
                      "match",
                      ["coalesce", ["get", "confidence_level"], "low"],
                      "high",
                      "#fca5a5",
                      "medium",
                      "#fdba74",
                      "#fde68a",
                    ],
                    "line-width": 1.1,
                    "line-opacity": Math.min(1, changeDetectionOpacity + 0.15),
                  }}
                />
              </Source>
            ) : null}
          </Map>
        </div>
      ) : null}

      {effectiveSwipeActive ? (
        <div
          className="pointer-events-auto absolute bottom-0 top-0 z-[9] w-0.5 bg-cyan-300/85 shadow-[0_0_0_1px_rgba(8,145,178,0.6)]"
          style={{ left: `calc(${Math.max(0, Math.min(1, swipePosition)) * 100}% - 1px)` }}
          onMouseDown={(event) => {
            setIsDraggingSwipe(true);
            updateSwipePosition(event.clientX);
          }}
        >
          <button
            type="button"
            className="absolute left-1/2 top-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/70 bg-slate-900/80 text-cyan-200 shadow"
            aria-label="Move swipe divider"
            onMouseDown={(event) => {
              event.preventDefault();
              setIsDraggingSwipe(true);
              updateSwipePosition(event.clientX);
            }}
          >
            ↔
          </button>
          <div
            className="pointer-events-none absolute top-3 rounded bg-slate-900/70 px-2 py-0.5 text-[10px] text-cyan-100"
            style={{ right: "10px", transform: "translateX(-100%)" }}
          >
            {swipeLeftLabel}
          </div>
          <div
            className="pointer-events-none absolute top-3 rounded bg-slate-900/70 px-2 py-0.5 text-[10px] text-cyan-100"
            style={{ left: "10px" }}
          >
            {swipeRightLabel}
          </div>
        </div>
      ) : null}

      <div className="pointer-events-auto absolute right-4 top-4 z-10">
        <CompassControl
          bearing={bearing}
          onReset={() => {
            mapRef.current?.getMap().easeTo({
              bearing: 0,
              duration: 350,
            });
          }}
        />
      </div>
    </div>
  );
}
