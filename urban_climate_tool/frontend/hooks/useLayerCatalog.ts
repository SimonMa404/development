import { useQuery } from "@tanstack/react-query";

import { fetchJson } from "@/lib/api/client";
import type { CatalogLayer } from "@/types/layers";

export function useLayerCatalog() {
  return useQuery({
    queryKey: ["layer-catalog"],
    queryFn: () => fetchJson<CatalogLayer[]>("/api/layers"),
  });
}
