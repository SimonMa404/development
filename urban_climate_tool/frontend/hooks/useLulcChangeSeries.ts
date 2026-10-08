import { useQuery } from "@tanstack/react-query";

import { fetchLulcChangeSeries } from "@/lib/api/analysis";

export function useLulcChangeSeries() {
  return useQuery({
    queryKey: ["lulc-change-series"],
    queryFn: fetchLulcChangeSeries,
  });
}
