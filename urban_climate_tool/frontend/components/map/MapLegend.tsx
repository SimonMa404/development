import type { CatalogLayer } from "@/types/layers";

export function MapLegend({ layer }: { layer: CatalogLayer }) {
  const isCategorical = layer.value_type === "categorical" || layer.legend?.type === "categorical";
  const isContinuous = layer.value_type === "continuous" || layer.legend?.type === "continuous";
  const palette = layer.legend?.palette ?? ["#334155", "#22d3ee"];
  const labels = layer.legend?.labels;
  const displayTitle = (layer.short_title ?? layer.title)
    .replace(/^Planegg\s+/i, "");

  const gradient = `linear-gradient(90deg, ${palette.join(", ")})`;
  const midpointLabel = labels && labels.length > 2 ? labels[Math.floor(labels.length / 2)] : null;
  const hasThreeLabels = Boolean(labels && labels.length >= 3);

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-slate-200">{displayTitle}</span>
        <span className="text-[10px] uppercase tracking-wide text-slate-500">{layer.units ?? "value"}</span>
      </div>

      {isCategorical && labels ? (
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
          {isContinuous && labels ? (
            <>
              <div className="h-3 w-full rounded-md" style={{ background: gradient }} />
              <div className="mt-2 grid gap-2 text-[10px] text-slate-500" style={{ gridTemplateColumns: hasThreeLabels ? "1fr 1fr 1fr" : "1fr 1fr" }}>
                {hasThreeLabels ? (
                  <>
                    <span className="text-left">{labels[0]}</span>
                    <span className="text-center">{midpointLabel ?? labels[1]}</span>
                    <span className="text-right">{labels[labels.length - 1]}</span>
                  </>
                ) : (
                  <>
                    <span>{labels[0]}</span>
                    <span className="text-right">{labels[labels.length - 1]}</span>
                  </>
                )}
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
          {!isContinuous && (!labels || labels.length !== palette.length) ? (
            <>
              <div className="h-3 w-full rounded-md" style={{ background: gradient }} />
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
