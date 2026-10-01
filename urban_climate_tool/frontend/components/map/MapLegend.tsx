import type { CatalogLayer } from "@/types/layers";

export function MapLegend({ layer }: { layer: CatalogLayer }) {
  const isCategorical = layer.value_type === "categorical" || layer.legend?.type === "categorical";
  const isPopulationLayer = layer.style?.color_scale === "population";
  const palette = layer.legend?.palette ?? ["#334155", "#22d3ee"];
  const labels = layer.legend?.labels;
  const isNdvi = layer.id === "ndvi-planegg";
  const displayTitle = (layer.short_title ?? layer.title)
    .replace(/^Planegg\s+/i, "");

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-slate-200">{displayTitle}</span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500">{layer.units ?? "value"}</span>
      </div>

      {isPopulationLayer ? (
        <>
          <div className="h-3 w-full rounded-md" style={{ background: `linear-gradient(90deg, ${palette.join(", ")})` }} />
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
            <span>{labels?.[0] ?? "low"}</span>
            <span>{labels?.[labels.length - 1] ?? "high"}</span>
          </div>
        </>
      ) : isCategorical && labels ? (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          {labels.map((label, i) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: palette[i] ?? "#64748b" }} />
              <span className="truncate text-[10px] text-slate-400">{label}</span>
            </div>
          ))}
        </div>
      ) : (
        <>
          {isNdvi ? (
            <>
              <div className="h-3 w-full rounded-md" style={{ background: `linear-gradient(90deg, ${palette.join(", ")})` }} />
              <div className="mt-2 space-y-1">
                {(labels ?? ["No vegetation", "Low vegetation", "Moderate vegetation", "Dense vegetation", "Very dense vegetation"]).map((label, i) => {
                  const colorStops = [0.08, 0.3, 0.5, 0.7, 0.9];
                  const colorIndex = Math.round((palette.length - 1) * colorStops[Math.min(i, colorStops.length - 1)]);
                  return (
                    <div key={`${layer.id}-ndvi-label-${i}`} className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: palette[colorIndex] ?? "#64748b" }} />
                      <span className="text-[10px] text-slate-400">{label}</span>
                    </div>
                  );
                })}
              </div>
            </>
          ) : labels && labels.length === palette.length ? (
            <div className="space-y-1">
              {labels.map((label, i) => (
                <div key={`${layer.id}-label-${i}`} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: palette[i] ?? "#64748b" }} />
                  <span className="text-[10px] text-slate-400">{label}</span>
                </div>
              ))}
            </div>
          ) : null}
          {!isNdvi && (!labels || labels.length !== palette.length) ? (
            <>
              <div className="h-3 w-full rounded-md" style={{ background: `linear-gradient(90deg, ${palette.join(", ")})` }} />
              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                <span>{layer.value_range?.minimum ?? 0}</span>
                <span>{layer.value_range?.maximum ?? 1}</span>
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
