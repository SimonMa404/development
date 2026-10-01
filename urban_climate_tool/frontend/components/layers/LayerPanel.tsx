import type { CatalogLayer } from "@/types/layers";

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between gap-2 text-[10px]">
      <span className="text-slate-500">{label}</span>
      <span className="truncate text-slate-300">{value}</span>
    </div>
  );
}

export function LayerPanel({
  layers,
  onToggleVisibility,
  onOpacityChange,
}: {
  layers: CatalogLayer[];
  onToggleVisibility: (id: string) => void;
  onOpacityChange: (id: string, opacity: number) => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 space-y-2 overflow-y-auto pr-1">
        {layers.map((layer) => (
          <div
            key={layer.id}
            className={`rounded-lg border p-3 transition ${
              layer.default_visible
                ? "border-cyan-400/30 bg-cyan-400/5"
                : "border-white/5 bg-white/[0.02]"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onToggleVisibility(layer.id)}
                    aria-label={`Toggle visibility for ${layer.title}`}
                    role="switch"
                    aria-checked={layer.default_visible}
                    className={`relative h-4 w-8 shrink-0 rounded-full transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400 ${
                      layer.default_visible ? "bg-cyan-400" : "bg-slate-700"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 h-3 w-3 rounded-full bg-slate-950 transition ${
                        layer.default_visible ? "left-4" : "left-0.5"
                      }`}
                    />
                  </button>
                  <span className="truncate text-sm font-medium text-slate-100">{layer.short_title ?? layer.title}</span>
                </div>
                {layer.is_demo ? (
                  <span className="mt-1 inline-flex rounded bg-amber-400/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
                    Demo data
                  </span>
                ) : null}
              </div>
              <span className="shrink-0 rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                {layer.layer_type}
              </span>
            </div>

            <div className="mt-2 space-y-0.5 border-t border-white/5 pt-2">
              <InfoRow label="Source" value={layer.source} />
              <InfoRow label="Acquired" value={layer.acquisition_date} />
              <InfoRow label="Resolution" value={layer.spatial_resolution ? `${layer.spatial_resolution} m` : undefined} />
              <InfoRow label="Units" value={layer.units} />
            </div>

            <div className="mt-2">
              <label htmlFor={`opacity-${layer.id}`} className="mb-1 block text-[10px] font-medium uppercase tracking-wide text-slate-500">
                Opacity
              </label>
              <input
                id={`opacity-${layer.id}`}
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={layer.default_opacity}
                onChange={(event) => onOpacityChange(layer.id, Number(event.target.value))}
                className="w-full accent-cyan-400"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
