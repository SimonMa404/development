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
  population: "#3b82f6",
};

export type BasemapId = "satellite" | "hybrid" | "dark";

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
    [
      "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    ],
    "© OpenStreetMap contributors, © CARTO",
    20,
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
  basemap = "satellite",
  terrain3dEnabled = false,
  terrainAvailable = false,
  terrainExaggeration = 1.8,
  hillshadeStrength = 0.7,
  selectedBuildingId = null,
}: {
  layers: CatalogLayer[];
  apiBaseUrl: string;
  drawMode?: boolean;
  drawnPoints?: [number, number][];
  onMapClick?: (lngLat: [number, number]) => void;
  onBuildingClick?: (payload: {
    id: string;
    properties: Record<string, unknown>;
    geometry: Record<string, unknown>;
    lngLat: [number, number];
  }) => void;
  basemap?: BasemapId;
  terrain3dEnabled?: boolean;
  terrainAvailable?: boolean;
  terrainExaggeration?: number;
  hillshadeStrength?: number;
  selectedBuildingId?: string | null;
}) {
  const mapRef = useRef<MapRef>(null);
  const [bearing, setBearing] = useState(0);
  const [terrainRevision, setTerrainRevision] = useState(0);

  const visibleLayers = layers
    .filter((layer) => layer.default_visible && layer.available)
    .sort((a, b) => a.default_order - b.default_order);

  const interactiveLayerIds = useMemo(
    () =>
      visibleLayers
        .filter((layer) => layer.layer_type === "vector" && layer.style?.color_scale === "buildings3d")
        .flatMap((layer) => [`${layer.id}-extrusion`, `${layer.id}-outline`]),
    [visibleLayers],
  );

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const buildingFeature = event.features?.find((feature) =>
        String(feature.layer.id).endsWith("-extrusion") || String(feature.layer.id).endsWith("-outline"),
      );

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
    [onMapClick, onBuildingClick],
  );

  const polygon = drawnPolygonFeature(drawnPoints);
  const mapStyle = useMemo(() => BASEMAP_STYLES[basemap], [basemap]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const map = mapRef.current?.getMap();
      if (!map) return;

      const hasTerrainSource = Boolean(map.getSource("terrain-dem"));
      if (terrain3dEnabled && terrainAvailable && hasTerrainSource) {
        map.setTerrain({ source: "terrain-dem", exaggeration: terrainExaggeration });
        map.easeTo({ pitch: 55, duration: 350 });
        return;
      }
      map.setTerrain(null);
      map.easeTo({ pitch: 0, duration: 300 });
    }, 50);

    return () => window.clearTimeout(timer);
  }, [terrain3dEnabled, terrainAvailable, terrainExaggeration, terrainRevision, mapStyle]);

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
        onLoad={() => setTerrainRevision((v) => v + 1)}
        onStyleData={() => setTerrainRevision((v) => v + 1)}
      >
        {terrainAvailable ? (
          <Source
            id="terrain-dem"
            type="raster-dem"
            tiles={[`${apiBaseUrl}/api/terrain/{z}/{x}/{y}.png`]}
            tileSize={256}
            encoding="terrarium"
            maxzoom={15}
          >
            <Layer
              id="terrain-hillshade"
              type="hillshade"
              paint={{
                "hillshade-exaggeration": hillshadeStrength,
                "hillshade-shadow-color": "#0f172a",
                "hillshade-highlight-color": "#e2e8f0",
              }}
            />
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
              return (
                <Source key={layer.id} id={layer.id} type="geojson" data={`${apiBaseUrl}/api/vectors/${layer.id}`}>
                  <Layer
                    id={`${layer.id}-extrusion`}
                    type="fill-extrusion"
                    paint={{
                      "fill-extrusion-color": color,
                      "fill-extrusion-height": [
                        "*",
                        1.5,
                        ["coalesce", ["to-number", ["get", "height"]], 6],
                      ],
                      "fill-extrusion-base": ["coalesce", ["to-number", ["get", "min_height"]], 0],
                      "fill-extrusion-opacity": layer.default_opacity,
                    }}
                  />
                  <Layer
                    id={`${layer.id}-outline`}
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
                        "fill-extrusion-height": [
                          "*",
                          1.52,
                          ["coalesce", ["to-number", ["get", "height"]], 6],
                        ],
                        "fill-extrusion-base": ["coalesce", ["to-number", ["get", "min_height"]], 0],
                        "fill-extrusion-opacity": 1,
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
