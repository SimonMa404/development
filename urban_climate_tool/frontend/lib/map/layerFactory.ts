import type { CatalogLayer } from "@/types/layers";

export function buildRasterTileUrl(layer: CatalogLayer, baseUrl: string): string {
  return `${baseUrl}/api/tiles/${layer.id}/{z}/{x}/{y}.png`;
}

export function buildVectorUrl(layer: CatalogLayer, baseUrl: string): string {
  return `${baseUrl}/api/vectors/${layer.id}`;
}

export function getLegendSteps(layer: CatalogLayer): string[] {
  return layer.legend?.palette ?? ["#dbeafe", "#1d4ed8"];
}
