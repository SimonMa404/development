"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Map, Source, Layer, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
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
export type TerrainSourceId = "dem" | "dom";

type ClickedVectorFeature = {
  id: string;
  properties: Record<string, unknown>;
  geometry: Record<string, unknown>;
  lngLat: [number, number];
};

const ESRI_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics, and the GIS User Community";

function rasterStyle(tiles: string[], attribution: string, maxzoom = 20) {
  return {
    version: 8 as const,
    sources: {
      base: {
        type: "raster" as const,
        tiles,
        tileSize: 256,
        attribution,
      },
    },
    layers: [
      {
        id: "base-layer",
        type: "raster" as const,
        source: "base",
        minzoom: 0,
        maxzoom,
      },
    ],
  };
}

const BASEMAP_STYLES: Record<BasemapId, ReturnType<typeof rasterStyle>> = {
  satellite: rasterStyle(
    ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    ESRI_ATTRIBUTION,
  ),
  hybrid: rasterStyle(["https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"], "Imagery © Google", 20),
  dark: rasterStyle(
    ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
    "Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community",
    16,
  ),
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
  apiBaseUrl,
  drawMode = false,
  drawnPoints = [],
  onMapClick,
  onBuildingClick,
  onNutzungClick,
  basemap = "satellite",
  terrain3dEnabled = false,
  terrainSource = "dem",
  terrainAvailable = false,
  terrainExaggeration = 1.8,
  hillshadeStrength = 0.7,
  selectedBuildingId = null,
  selectedNutzungId = null,
}: {
  layers: CatalogLayer[];
  apiBaseUrl: string;
  drawMode?: boolean;
  drawnPoints?: [number, number][];
  onMapClick?: (lngLat: [number, number]) => void;
  onBuildingClick?: (payload: ClickedVectorFeature) => void;
  onNutzungClick?: (payload: ClickedVectorFeature) => void;
  basemap?: BasemapId;
  terrain3dEnabled?: boolean;
  terrainSource?: TerrainSourceId;
  terrainAvailable?: boolean;
  terrainExaggeration?: number;
  hillshadeStrength?: number;
  selectedBuildingId?: string | null;
  selectedNutzungId?: string | null;
}) {
  const mapRef = useRef<MapRef>(null);
  const previousTerrainEnabledRef = useRef(false);
  const [bearing, setBearing] = useState(0);
  const [terrainRevision, setTerrainRevision] = useState(0);
  const domMode = terrainSource === "dom";

  const visibleLayers = useMemo(() => {
    const isPriority3dLayer = (layer: CatalogLayer) =>
      layer.layer_type === "vector" &&
      (layer.style?.color_scale === "buildings3d" || layer.style?.color_scale === "trees3d");

    const sorted = layers
      .filter((layer) => layer.default_visible && layer.available)
      .sort((a, b) => a.default_order - b.default_order);

    const normalLayers = sorted.filter((layer) => !isPriority3dLayer(layer));
    const priority3dLayers = sorted.filter(isPriority3dLayer);

    if (drawMode) {
      return normalLayers;
    }

    return [...normalLayers, ...priority3dLayers];
  }, [layers, drawMode]);

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
  const mapStyle = useMemo(() => BASEMAP_STYLES[basemap], [basemap]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const map = mapRef.current?.getMap();
      if (!map) return;

      const hasTerrainSource = Boolean(map.getSource("terrain-dem"));
      const effectiveExaggeration = domMode ? 1 : terrainExaggeration;

      const terrainShouldBeEnabled = terrain3dEnabled && terrainAvailable && hasTerrainSource;
      if (terrainShouldBeEnabled) {
        map.setTerrain({ source: "terrain-dem", exaggeration: effectiveExaggeration });
        if (!previousTerrainEnabledRef.current && effectiveExaggeration > 0) {
          map.easeTo({ pitch: 55, duration: 350 });
        }
        previousTerrainEnabledRef.current = true;
        return;
      }

      map.setTerrain(null);
      if (previousTerrainEnabledRef.current) {
        map.easeTo({ pitch: 0, duration: 300 });
      }
      previousTerrainEnabledRef.current = false;
    }, 50);

    return () => window.clearTimeout(timer);
  }, [terrain3dEnabled, terrainAvailable, terrainExaggeration, domMode, terrainRevision, mapStyle]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const map = mapRef.current?.getMap();
      if (!map) return;

      // Keep drawn selection overlays above all other layers.
      const drawLayerOrder = ["draw-polygon-fill", "draw-polygon-line", "draw-points-layer"];
      for (const layerId of drawLayerOrder) {
        if (map.getLayer(layerId)) {
          map.moveLayer(layerId);
        }
      }
    }, 0);

    return () => window.clearTimeout(timer);
  }, [terrainRevision, drawnPoints.length, Boolean(polygon)]);

  return (
    <div className="relative h-full w-full">
      <Map
        ref={mapRef}
        initialViewState={PLANEGG_CENTER}
        mapStyle={mapStyle}
        style={{ width: "100%", height: "100%" }}
        cursor={drawMode ? "crosshair" : "grab"}
        onClick={handleClick}
        interactiveLayerIds={interactiveLayerIds}
        onRotate={(event) => setBearing(event.target.getBearing())}
        onLoad={() => {
          setTerrainRevision((v) => v + 1);
        }}
        onStyleData={() => setTerrainRevision((v) => v + 1)}
      >
        {terrainAvailable ? (
          <Source
            key={`terrain-${terrainSource}`}
            id="terrain-dem"
            type="raster-dem"
            tiles={[`${apiBaseUrl}/api/terrain/{z}/{x}/{y}.png?source=${terrainSource}`]}
            tileSize={256}
            encoding="terrarium"
            maxzoom={15}
          >
            {!domMode && (
              <Layer
                id="terrain-hillshade"
                type="hillshade"
                paint={{
                  "hillshade-exaggeration": hillshadeStrength,
                  "hillshade-shadow-color": "#0f172a",
                  "hillshade-highlight-color": "#e2e8f0",
                }}
              />
            )}
          </Source>
        ) : null}

        {visibleLayers.map((layer) => {
          if (layer.layer_type === "raster") {
            return (
              <Source
                key={layer.id}
                id={layer.id}
                type="raster"
                tiles={[`${apiBaseUrl}/api/tiles/${layer.id}/{z}/{x}/{y}.png`]}
                tileSize={256}
              >
                <Layer
                  id={`${layer.id}-layer`}
                  type="raster"
                  paint={{
                    "raster-opacity": layer.default_opacity,
                    "raster-resampling": layer.value_type === "categorical" ? "nearest" : "linear",
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
              const modeSuffix = domMode ? "2d" : "3d";
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
              
              if (domMode) {
                return (
                  <Source key={`${layer.id}-${modeSuffix}`} id={layer.id} type="geojson" data={buildingsUrl}>
                    <Layer
                      id={`${layer.id}-fill-2d`}
                      type="fill"
                      paint={{
                        "fill-color": color,
                        "fill-opacity": Math.max(0.12, layer.default_opacity * 0.25),
                      }}
                    />
                    <Layer
                      id={`${layer.id}-outline-2d`}
                      type="line"
                      paint={{
                        "line-color": "#d1d5db",
                        "line-width": 0.8,
                        "line-opacity": 0.9,
                      }}
                    />
                    {selectedBuildingId ? (
                      <Layer
                        id={`${layer.id}-selected-fill`}
                        type="fill"
                        filter={["==", ["to-string", ["get", "id"]], selectedBuildingId]}
                        paint={{
                          "fill-color": "#fde047",
                          "fill-opacity": 0.45,
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
                          "line-width": 3,
                          "line-opacity": 1,
                        }}
                      />
                    ) : null}
                  </Source>
                );
              }

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
              const trunkBrown = "#6b4f2a";
              const modeSuffix = domMode ? "2d" : "3d";
              
              if (domMode) {
                return (
                  <Source
                    key={`${layer.id}-${modeSuffix}`}
                    id={layer.id}
                    type="geojson"
                    data={`${apiBaseUrl}/api/vectors/${layer.id}`}
                  >
                    <Layer
                      id={`${layer.id}-halo`}
                      type="circle"
                      minzoom={11}
                      filter={["==", ["get", "tree_part"], "point"]}
                      paint={{
                        "circle-color": treeGreen,
                        "circle-opacity": 0.16,
                        "circle-stroke-color": treeGreenDark,
                        "circle-stroke-opacity": 0.28,
                        "circle-stroke-width": 1,
                        "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 4, 14, 7, 17, 11],
                      }}
                    />
                    <Layer
                      id={`${layer.id}-point`}
                      type="circle"
                      minzoom={11}
                      filter={["==", ["get", "tree_part"], "point"]}
                      paint={{
                        "circle-color": treeGreenDark,
                        "circle-opacity": layer.default_opacity,
                        "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 1.1, 14, 1.8, 17, 2.7],
                      }}
                    />
                  </Source>
                );
              }

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
                    id={`${layer.id}-canopy`}
                    type="fill-extrusion"
                    minzoom={12}
                    filter={["==", ["get", "tree_part"], "canopy"]}
                    paint={{
                      "fill-extrusion-color": treeGreen,
                      "fill-extrusion-height": ["coalesce", ["to-number", ["get", "height"]], 12],
                      "fill-extrusion-base": ["coalesce", ["to-number", ["get", "canopy_base"]], 1.5],
                      "fill-extrusion-opacity": Math.max(0.7, layer.default_opacity * 0.88),
                      "fill-extrusion-vertical-gradient": true,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-canopy-outline`}
                    type="line"
                    minzoom={12}
                    filter={["==", ["get", "tree_part"], "canopy"]}
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
