import { useMutation } from "@tanstack/react-query";

import { fetchAreaStatistics } from "@/lib/api/analysis";
import type { AreaStatisticsRequest, AreaStatisticsResponse } from "@/types/analysis";

export function useAreaStatistics() {
  return useMutation<AreaStatisticsResponse, Error, AreaStatisticsRequest>({
    mutationFn: (request) => fetchAreaStatistics(request),
  });
}
