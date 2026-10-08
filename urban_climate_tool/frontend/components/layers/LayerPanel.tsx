import { useMemo, useState } from "react";
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
  onResetVisible,
}: {
  layers: CatalogLayer[];
  onToggleVisibility: (id: string) => void;
  onOpacityChange: (id: string, opacity: number) => void;
  onResetVisible: () => void;
}) {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [yearFilter, setYearFilter] = useState<string>("all");

  const availableYears = useMemo(() => {
    const years = new Set<number>();
    for (const layer of layers) {
      if (typeof layer.temporal_year === "number") {
        years.add(layer.temporal_year);
        continue;
      }
      const acq = layer.acquisition_date;
      if (acq && acq.length >= 4) {
        const y = Number(acq.slice(0, 4));
        if (Number.isFinite(y)) years.add(y);
      }
    }
    return [...years].sort((a, b) => b - a);
  }, [layers]);

  const groupedLayers = useMemo(() => {
    const groups: Array<{ key: string; title: string; layers: CatalogLayer[] }> = [
      { key: "overlays", title: "Overlays & Boundary", layers: [] },
      { key: "rgb", title: "RGB Imagery", layers: [] },
      { key: "lulc", title: "LULC", layers: [] },
      { key: "temperature", title: "Temperature", layers: [] },
      { key: "vegetation", title: "Vegetation", layers: [] },
      { key: "info", title: "Info (Census & ALKIS)", layers: [] },
      { key: "other", title: "Other Layers", layers: [] },
    ];

    const toGroup = (layer: CatalogLayer) => {
      const tags = layer.tags ?? [];
      const id = layer.id.toLowerCase();
      const thematic = String(layer.thematic_group ?? "").toLowerCase();
      const scale = String(layer.style?.color_scale ?? "").toLowerCase();

      if (
        scale === "buildings3d" ||
        scale === "trees3d" ||
        id.includes("buildings") ||
        id.includes("trees") ||
        id.includes("boundary")
      ) {
        return "overlays";
      }
      if (layer.value_type === "rgb" || scale === "rgb" || tags.includes("sentinel-rgb") || id.includes("rgb")) {
        return "rgb";
      }
      if (tags.includes("lulc") || tags.includes("dynamic-world") || id.startsWith("lulc")) {
        return "lulc";
      }
      if (
        tags.includes("ndvi") ||
        tags.includes("vegetation") ||
        id.includes("ndvi") ||
        thematic.includes("vegetation")
      ) {
        return "vegetation";
      }
      if (
        tags.includes("lst") ||
        id.includes("lst") ||
        thematic.includes("temperature") ||
        thematic.includes("heat")
      ) {
        return "temperature";
      }
      if (
        id.includes("census") ||
        id.includes("nutzung") ||
        thematic.includes("population") ||
        thematic.includes("land use") ||
        thematic.includes("alkis")
      ) {
        return "info";
      }
      return "other";
    };

    const filteredLayers = layers.filter((layer) => {
      if (yearFilter === "all") return true;
      const temporalYear = typeof layer.temporal_year === "number"
        ? layer.temporal_year
        : layer.acquisition_date && layer.acquisition_date.length >= 4
          ? Number(layer.acquisition_date.slice(0, 4))
          : null;
      return temporalYear !== null && String(temporalYear) === yearFilter;
    });

    for (const layer of [...filteredLayers].sort((a, b) => a.default_order - b.default_order)) {
      const groupKey = toGroup(layer);
      const group = groups.find((entry) => entry.key === groupKey);
      group?.layers.push(layer);
    }

    return groups.filter((group) => group.layers.length > 0);
  }, [layers, yearFilter]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center justify-end">
        <label className="mr-2 flex items-center gap-1 text-[10px] text-slate-400">
          Year
          <select
            value={yearFilter}
            onChange={(event) => setYearFilter(event.target.value)}
            className="rounded border border-white/10 bg-slate-900 px-1.5 py-0.5 text-[10px] text-slate-200"
          >
            <option value="all">All</option>
            {availableYears.map((year) => (
              <option key={`year-${year}`} value={String(year)}>
                {year}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onResetVisible}
          className="rounded border border-white/15 bg-white/[0.04] px-2 py-1 text-[10px] uppercase tracking-wide text-slate-300 hover:bg-white/[0.08]"
        >
          Reset active
        </button>
      </div>
      <div className="min-h-0 space-y-2 overflow-y-auto pr-1">
        {groupedLayers.map((group) => (
          <section key={group.key} className="space-y-2">
            <button
              type="button"
              onClick={() => setExpandedGroups((prev) => ({ ...prev, [group.key]: !prev[group.key] }))}
              className="sticky top-0 z-10 flex w-full items-center justify-between rounded bg-[#0b1220]/90 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-cyan-300 backdrop-blur hover:bg-[#0f172a]"
            >
              <span>{group.title} · {group.layers.length}</span>
              <span>{expandedGroups[group.key] ? "−" : "+"}</span>
            </button>

            {expandedGroups[group.key] ? group.layers.map((layer) => (
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
            )) : null}
          </section>
        ))}
      </div>
    </div>
  );
}
