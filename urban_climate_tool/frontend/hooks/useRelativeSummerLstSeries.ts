import { useQuery } from "@tanstack/react-query";

import { fetchRelativeSummerLstSeries } from "@/lib/api/analysis";

export function useRelativeSummerLstSeries() {
  return useQuery({
    queryKey: ["relative-summer-lst-series"],
    queryFn: fetchRelativeSummerLstSeries,
  });
}
