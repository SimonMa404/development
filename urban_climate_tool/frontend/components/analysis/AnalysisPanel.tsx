"use client";

import { useState } from "react";
import type {
  BuildingOverviewLayerStatistics,
  ClassBreakdownItem,
  HeatVulnerabilityResult,
  Histogram,
  LayerAreaStatistics,
  TreeStatisticsResult,
} from "@/types/analysis";

type ThresholdClass = {
  label: string;
  count: number;
  pct: number;
  color: string;
};

type PieSlice = {
  label: string;
  value: number;
  color: string;
};

type LstClassKey = "cool" | "mild" | "warm" | "hot";

const LST_CLASS_ORDER: LstClassKey[] = ["cool", "mild", "warm", "hot"];

function lstClassDefinitions(palette: string[]) {
  return [
    { key: "cool" as const, label: "Cool (<22°C)", min: -999, max: 22, color: palette[1] ?? "#4575b4" },
    { key: "mild" as const, label: "Mild (22–26°C)", min: 22, max: 26, color: palette[4] ?? "#e0f3f8" },
    { key: "warm" as const, label: "Warm (26–30°C)", min: 26, max: 30, color: palette[6] ?? "#fdae61" },
    { key: "hot" as const, label: "Hot (≥30°C)", min: 30, max: 999, color: palette[8] ?? "#d73027" },
  ];
}

function lstClassKeyFromLabel(label: string): LstClassKey | null {
  const normalized = label.toLowerCase();
  if (normalized.includes("cool")) return "cool";
  if (normalized.includes("mild")) return "mild";
  if (normalized.includes("warm")) return "warm";
  if (normalized.includes("hot")) return "hot";
  return null;
}

function thresholdClassesForLayer(layerId: string, histogram: Histogram, palette: string[]): ThresholdClass[] {
  const thresholds =
    layerId === "ndvi-planegg"
      ? [
          { label: "No vegetation", min: -999, max: 0, color: palette[0] ?? "#8B4513" },
          { label: "Low vegetation", min: 0, max: 0.2, color: palette[2] ?? "#fee08b" },
          { label: "Moderate vegetation", min: 0.2, max: 0.4, color: palette[3] ?? "#ffffbf" },
          { label: "Dense vegetation", min: 0.4, max: 0.6, color: palette[4] ?? "#a6d96a" },
          { label: "Very dense vegetation", min: 0.6, max: 999, color: palette[6] ?? "#00441b" },
        ]
      : lstClassDefinitions(palette);

  const total = histogram.counts.reduce((a, b) => a + b, 0) || 1;
  return thresholds.map((threshold) => {
    let count = 0;
    for (let i = 0; i < histogram.counts.length; i++) {
      const center = (histogram.bin_edges[i] + histogram.bin_edges[i + 1]) / 2;
      if (center >= threshold.min && center < threshold.max) count += histogram.counts[i] ?? 0;
    }
    return {
      label: threshold.label,
      count,
      pct: (count / total) * 100,
      color: threshold.color,
    };
  });
}

function ThresholdDistribution({
  layerId,
  histogram,
  units,
  palette,
}: {
  layerId: string;
  histogram: Histogram;
  units?: string;
  palette: string[];
}) {
  const classes = thresholdClassesForLayer(layerId, histogram, palette);

  return (
    <div className="mt-3 space-y-1.5">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Distribution by threshold</div>
      {classes.map((item) => (
        <div key={item.label} className="rounded border border-white/10 bg-white/[0.02] p-1.5">
          <div className="mb-1 flex items-center justify-between text-[11px] text-slate-300">
            <span className="inline-flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
              {item.label}
            </span>
            <span>{item.pct.toFixed(1)}%</span>
          </div>
          <div className="h-2 w-full rounded bg-white/5">
            <div className="h-2 rounded" style={{ width: `${Math.max(2, item.pct)}%`, backgroundColor: item.color }} />
          </div>
          <div className="mt-1 text-[10px] text-slate-500">{item.count.toLocaleString()} pixels{units ? ` (${units})` : ""}</div>
        </div>
      ))}
    </div>
  );
}

function InteractivePieChart({
  slices,
}: {
  slices: PieSlice[];
}) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const total = slices.reduce((sum, item) => sum + item.value, 0);

  if (!slices.length || total <= 0) {
    return <div className="text-[11px] text-slate-500">No distribution available.</div>;
  }

  const cx = 60;
  const cy = 60;
  const r = 58;

  let cumulative = 0;
  const paths = slices.map((slice, index) => {
    const start = cumulative / total;
    cumulative += slice.value;
    const end = cumulative / total;

    const startAngle = start * Math.PI * 2 - Math.PI / 2;
    const endAngle = end * Math.PI * 2 - Math.PI / 2;

    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const largeArc = end - start > 0.5 ? 1 : 0;
    const d = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;

    const pct = (slice.value / total) * 100;
    return { d, pct, slice, index };
  });

  const active = hoveredIndex !== null ? paths[hoveredIndex] : null;

  return (
    <div>
      <svg viewBox="0 0 120 120" className="mx-auto h-[120px] w-[120px] rounded-full border border-white/10">
        {paths.map((item) => (
          <path
            key={`${item.slice.label}-${item.index}`}
            d={item.d}
            fill={item.slice.color}
            opacity={hoveredIndex === null || hoveredIndex === item.index ? 1 : 0.35}
            stroke="rgba(15,23,42,0.45)"
            strokeWidth={0.7}
            onMouseEnter={() => setHoveredIndex(item.index)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <title>{`${item.slice.label}: ${item.pct.toFixed(1)}%`}</title>
          </path>
        ))}
      </svg>
      <div className="mt-1 min-h-[16px] text-center text-[10px] text-slate-400">
        {active ? `${active.slice.label}: ${active.pct.toFixed(1)}%` : "Hover a slice"}
      </div>
    </div>
  );
}

function LayerThresholdPie({ layerId, histogram, palette }: { layerId: string; histogram: Histogram; palette: string[] }) {
  const classes = thresholdClassesForLayer(layerId, histogram, palette).filter((item) => item.count > 0);
  const total = classes.reduce((sum, item) => sum + item.count, 0);
  if (!classes.length || total <= 0) {
    return <div className="text-[11px] text-slate-500">No distribution available.</div>;
  }

  const slices: PieSlice[] = classes.map((item) => ({ label: item.label, value: item.count, color: item.color }));

  return (
    <div className="mt-2 grid grid-cols-[120px_1fr] gap-3">
      <InteractivePieChart slices={slices} />
      <div className="space-y-1">
        {classes.map((item) => (
          <div key={item.label} className="rounded border border-white/10 bg-white/[0.02] px-2 py-1 text-[11px]">
            <div className="flex items-center justify-between text-slate-200">
              <span className="inline-flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
                {item.label}
              </span>
              <span>{item.pct.toFixed(1)}%</span>
            </div>
            <div className="mt-0.5 text-[10px] text-slate-500">{item.count.toLocaleString()} pixels</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BuildingClimateBars({
  items,
}: {
  items: BuildingOverviewLayerStatistics[];
}) {
  if (!items.length) return null;
  return (
    <div className="mt-3 space-y-2">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Average building climate</div>
      {items.map((item) => {
        const min = item.value_range?.minimum ?? item.buildings.minimum;
        const max = item.value_range?.maximum ?? item.buildings.maximum;
        const range = max - min || 1;
        const pct = Math.max(0, Math.min(100, ((item.buildings.mean - min) / range) * 100));
        const title = (item.title ?? item.layer_id).replace(/^Planegg\s+/i, "");
        return (
          <div key={item.layer_id} className="rounded border border-white/10 bg-white/[0.02] p-2">
            <div className="mb-1 flex items-center justify-between text-[11px] text-slate-300">
              <span>{title}</span>
              <span className="font-semibold text-cyan-300">{item.buildings.mean.toFixed(2)} {item.units ?? ""}</span>
            </div>
            <div className="relative h-4 rounded" style={{ background: `linear-gradient(90deg, ${(item.legend?.palette ?? ["#334155", "#22d3ee"]).join(", ")})` }}>
              <div className="absolute inset-y-0 w-[4px] rounded bg-white shadow-[0_0_8px_rgba(255,255,255,0.9)]" style={{ left: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LulcPie({ items }: { items: ClassBreakdownItem[] }) {
  const slices: PieSlice[] = items
    .filter((item) => item.count > 0)
    .map((item) => ({ label: item.label, value: item.count, color: item.color }));

  return (
    <div className="grid grid-cols-[120px_1fr] gap-3">
      <InteractivePieChart slices={slices} />
      <div className="space-y-1">
        {items.map((item) => (
          <div key={item.class_index} className="flex items-center justify-between gap-2 text-[11px] text-slate-300">
            <span className="flex items-center gap-2 truncate">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: item.color }} />
              <span className="truncate">{item.label}</span>
            </span>
            <span>{item.percentage.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HeatPopulationPie({ vulnerability, palette }: { vulnerability: HeatVulnerabilityResult; palette: string[] }) {
  const bins = (vulnerability.lst_exposure_bins ?? []).filter((item) => (item.population ?? 0) > 0);
  const total = bins.reduce((sum, item) => sum + (item.population ?? 0), 0);
  if (!bins.length || total <= 0) {
    return <div className="text-[11px] text-slate-500">No overlapping population/LST data in selection.</div>;
  }

  const lstDefs = lstClassDefinitions(palette);
  const defsByKey = new Map(lstDefs.map((item) => [item.key, item]));
  const classOrder = new Map(LST_CLASS_ORDER.map((key, index) => [key, index]));

  const slices = bins
    .map((bin, index) => {
      const key = lstClassKeyFromLabel(bin.label);
      const klass = key ? defsByKey.get(key) : undefined;
      return {
        ...bin,
        _key: key,
        label: klass?.label ?? bin.label,
        color: klass?.color ?? palette[index % Math.max(1, palette.length)] ?? "#64748b",
        pct: ((bin.population ?? 0) / total) * 100,
      };
    })
    .sort((a, b) => {
      const ai = a._key ? (classOrder.get(a._key) ?? 999) : 999;
      const bi = b._key ? (classOrder.get(b._key) ?? 999) : 999;
      return ai - bi;
    });

  const pieSlices: PieSlice[] = slices.map((item) => ({
    label: item.label,
    value: item.population ?? 0,
    color: item.color,
  }));

  return (
    <div className="mt-2 grid grid-cols-[120px_1fr] gap-3">
      <InteractivePieChart slices={pieSlices} />
      <div className="space-y-1">
        {slices.map((item) => (
          <div key={item.label} className="rounded border border-white/10 bg-white/[0.02] px-2 py-1 text-[11px]">
            <div className="flex items-center justify-between text-slate-200">
              <span className="inline-flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
                {item.label}
              </span>
              <span>{item.pct.toFixed(1)}%</span>
            </div>
            <div className="mt-0.5 text-[10px] text-slate-500">
              Pop: {(item.population ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NdviPopulationPie({ vulnerability, ndviPalette }: { vulnerability: HeatVulnerabilityResult; ndviPalette: string[] }) {
  const bins = (vulnerability.ndvi_exposure_bins ?? []).filter((item) => (item.population ?? 0) > 0);
  const total = bins.reduce((sum, item) => sum + (item.population ?? 0), 0);
  if (!bins.length || total <= 0) {
    return <div className="text-[11px] text-slate-500">No overlapping population/NDVI data in selection.</div>;
  }

  const colorByLabel: Record<string, string> = {
    "No vegetation": ndviPalette[0] ?? "#8B4513",
    "Low vegetation": ndviPalette[2] ?? "#fee08b",
    "Moderate vegetation": ndviPalette[3] ?? "#ffffbf",
    "Dense vegetation": ndviPalette[4] ?? "#a6d96a",
    "Very dense vegetation": ndviPalette[6] ?? "#00441b",
  };

  const slices = bins.map((bin, index) => ({
    ...bin,
    color: colorByLabel[bin.label] ?? ndviPalette[index % Math.max(1, ndviPalette.length)] ?? "#64748b",
    pct: ((bin.population ?? 0) / total) * 100,
  }));

  const pieSlices: PieSlice[] = slices.map((item) => ({
    label: item.label,
    value: item.population ?? 0,
    color: item.color,
  }));

  return (
    <div className="mt-2 grid grid-cols-[120px_1fr] gap-3">
      <InteractivePieChart slices={pieSlices} />
      <div className="space-y-1">
        {slices.map((item) => (
          <div key={item.label} className="rounded border border-white/10 bg-white/[0.02] px-2 py-1 text-[11px]">
            <div className="flex items-center justify-between text-slate-200">
              <span className="inline-flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
                {item.label}
              </span>
              <span>{item.pct.toFixed(1)}%</span>
            </div>
            <div className="mt-0.5 text-[10px] text-slate-500">
              Pop: {(item.population ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ComparisonScale({
  palette,
  min,
  max,
  selectedValue,
  averageValue,
  units,
}: {
  palette: string[];
  min: number;
  max: number;
  selectedValue: number;
  averageValue: number;
  units?: string;
}) {
  const range = max - min || 1;
  const selectedPct = Math.max(0, Math.min(100, ((selectedValue - min) / range) * 100));
  const averagePct = Math.max(0, Math.min(100, ((averageValue - min) / range) * 100));

  const delta = selectedValue - averageValue;
  const deltaLabel = delta > 0 ? "above" : delta < 0 ? "below" : "same as";

  return (
    <div className="mt-3">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">Where your selected area sits</div>
      <div className="relative h-6 rounded-md" style={{ background: `linear-gradient(90deg, ${palette.join(", ")})` }}>
        <div
          className="absolute inset-y-0 w-[4px] rounded border border-white/70 bg-black"
          style={{ left: `${selectedPct}%` }}
          title={`Selected area: ${selectedValue.toFixed(2)} ${units ?? ""}`}
        />
        <div
          className="absolute inset-y-0 w-[5px] rounded border border-white/70"
          style={{
            left: `${averagePct}%`,
            backgroundImage: "repeating-linear-gradient(to bottom, #000000 0 2px, transparent 2px 4px)",
            backgroundColor: "rgba(255,255,255,0.65)",
          }}
          title={`Area average: ${averageValue.toFixed(2)} ${units ?? ""}`}
        />
      </div>
      <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
        <span>{min.toFixed(2)}</span>
        <span>{max.toFixed(2)}</span>
      </div>
      <div className="mt-1 grid grid-cols-2 gap-2 text-[10px] text-slate-400">
        <span>Selected: {selectedValue.toFixed(2)} {units ?? ""}</span>
        <span>Area avg: {averageValue.toFixed(2)} {units ?? ""}</span>
      </div>
      <div className="mt-1 text-[10px] text-slate-300">
        Your area is <span className="font-semibold text-cyan-300">{Math.abs(delta).toFixed(2)} {units ?? ""}</span> {deltaLabel} the area average.
      </div>
    </div>
  );
}

function ClassBreakdownList({
  items,
  baselineItems,
}: {
  items: ClassBreakdownItem[];
  baselineItems?: ClassBreakdownItem[] | null;
}) {
  const [selectedClasses, setSelectedClasses] = useState<Set<number>>(new Set());

  function toggleClass(index: number) {
    setSelectedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  const baselineByIndex = new Map((baselineItems ?? []).map((item) => [item.class_index, item]));

  return (
    <div className="mt-3 space-y-1.5">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">Class breakdown (selected area)</div>
      {items.map((item) => {
        const isSelected = selectedClasses.has(item.class_index);
        const baselineItem = baselineByIndex.get(item.class_index);
        return (
          <button
            key={item.class_index}
            type="button"
            onClick={() => toggleClass(item.class_index)}
            className={`w-full rounded-md border px-2 py-1.5 text-left transition ${
              isSelected ? "border-cyan-400/50 bg-cyan-400/10" : "border-white/5 bg-white/[0.02] hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: item.color }} />
                <span className="truncate text-xs text-slate-200">{item.label}</span>
              </span>
              <span className="shrink-0 text-xs font-semibold text-slate-100">{item.percentage.toFixed(1)}%</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-white/5">
              <div className="h-1.5 rounded-full" style={{ width: `${item.percentage}%`, backgroundColor: item.color }} />
            </div>
            {isSelected ? (
              <div className="mt-1.5 grid grid-cols-2 gap-2 text-[10px] text-slate-400">
                <span>Pixels: {item.count.toLocaleString()}</span>
                <span>Area avg: {baselineItem ? `${baselineItem.percentage.toFixed(1)}%` : "0%"}</span>
              </div>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function AnalysisPanel({
  results,
  isPending,
  error,
  treeStats = null,
  treeStatsPending = false,
  treeStatsError = null,
  overviewMode = false,
  overviewBuildingStats = null,
  overviewBuildingClimate = [],
  vulnerability = null,
  vulnerabilityPending = false,
  vulnerabilityError = null,
  lstPalette = ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#fee090", "#fdae61", "#f46d43", "#d73027"],
  ndviPalette = ["#8B4513", "#d73027", "#fee08b", "#ffffbf", "#a6d96a", "#1a9850", "#00441b"],
  showBuildings = true,
  showVulnerability = true,
  showTrees = true,
  visibleLayerIds = [],
}: {
  results: LayerAreaStatistics[] | undefined;
  isPending: boolean;
  error: Error | null;
  treeStats?: TreeStatisticsResult | null;
  treeStatsPending?: boolean;
  treeStatsError?: Error | null;
  overviewMode?: boolean;
  overviewBuildingStats?: { count: number; averageHeight: number } | null;
  overviewBuildingClimate?: BuildingOverviewLayerStatistics[];
  vulnerability?: HeatVulnerabilityResult | null;
  vulnerabilityPending?: boolean;
  vulnerabilityError?: Error | null;
  lstPalette?: string[];
  ndviPalette?: string[];
  showBuildings?: boolean;
  showVulnerability?: boolean;
  showTrees?: boolean;
  visibleLayerIds?: string[];
}) {
  const hasRasterResults = Boolean(results && results.length > 0);

  if (isPending) {
    return (
      <div className="glass-panel rounded-lg p-4 text-sm text-slate-400">
        Computing area statistics…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
        Failed to compute statistics: {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {showTrees ? (
        <div className="glass-panel rounded-xl border border-white/10 p-3">
          <div className="mb-2 text-sm font-medium text-slate-100">Trees</div>
          {treeStatsPending ? <div className="text-[11px] text-slate-500">Computing tree statistics…</div> : null}
          {treeStatsError ? <div className="text-[11px] text-red-300">{treeStatsError.message}</div> : null}
          {treeStats ? (
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Tree count</div>
                <div className="text-base font-semibold text-emerald-300">{treeStats.tree_count.toLocaleString()}</div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Density</div>
                <div className="text-base font-semibold text-emerald-300">
                  {(treeStats.tree_density_per_hectare ?? 0).toFixed(1)} /ha
                </div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Average height</div>
                <div className="text-base font-semibold text-emerald-300">{(treeStats.mean_height ?? 0).toFixed(1)} m</div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Max height</div>
                <div className="text-base font-semibold text-emerald-300">{(treeStats.maximum_height ?? 0).toFixed(1)} m</div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Median height</div>
                <div className="text-base font-semibold text-emerald-300">{(treeStats.median_height ?? 0).toFixed(1)} m</div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Area</div>
                <div className="text-base font-semibold text-emerald-300">{treeStats.area_hectares.toFixed(2)} ha</div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {overviewMode && showBuildings ? (
        <div className="glass-panel rounded-xl border border-white/10 p-3">
          <div className="mb-2 text-sm font-medium text-slate-100">Buildings</div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="rounded border border-white/10 bg-white/[0.02] p-2">
              <div className="text-slate-400">Buildings</div>
              <div className="text-base font-semibold text-cyan-300">{overviewBuildingStats?.count ?? 0}</div>
            </div>
            <div className="rounded border border-white/10 bg-white/[0.02] p-2">
              <div className="text-slate-400">Avg building height</div>
              <div className="text-base font-semibold text-cyan-300">{(overviewBuildingStats?.averageHeight ?? 0).toFixed(1)} m</div>
            </div>
          </div>
          <BuildingClimateBars items={overviewBuildingClimate} />
        </div>
      ) : null}

      {showVulnerability ? (
      <div className="glass-panel rounded-xl border border-white/10 p-3">
        <div className="mb-2 text-sm font-medium text-slate-100">Population vulnerability (Zensus 2022, 100m)</div>
        {vulnerabilityPending ? <div className="text-[11px] text-slate-500">Computing Census/LST overlay…</div> : null}
        {vulnerabilityError ? <div className="text-[11px] text-red-300">{vulnerabilityError.message}</div> : null}
        {vulnerability ? (
          <>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Total population</div>
                <div className="text-base font-semibold text-cyan-300">
                  {(vulnerability.summary.total_population ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Census cells</div>
                <div className="text-base font-semibold text-cyan-300">{vulnerability.summary.census_cells}</div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Elderly (65+)</div>
                <div className="text-base font-semibold text-amber-300">
                  {(vulnerability.summary.elderly_population ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  <span className="ml-1 text-[10px] text-slate-500">
                    ({((vulnerability.summary.elderly_share ?? 0) * 100).toFixed(1)}%)
                  </span>
                </div>
              </div>
              <div className="rounded border border-white/10 bg-white/[0.02] p-2">
                <div className="text-slate-400">Children (&lt;18)</div>
                <div className="text-base font-semibold text-lime-300">
                  {(vulnerability.summary.children_population ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  <span className="ml-1 text-[10px] text-slate-500">
                    ({((vulnerability.summary.children_share ?? 0) * 100).toFixed(1)}%)
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-3 text-[10px] font-medium uppercase tracking-wide text-slate-500">
              Population by temperature class (LST)
            </div>
            <HeatPopulationPie vulnerability={vulnerability} palette={lstPalette} />

            <div className="mt-3 text-[10px] font-medium uppercase tracking-wide text-slate-500">
              Population by greenness class (NDVI)
            </div>
            <NdviPopulationPie vulnerability={vulnerability} ndviPalette={ndviPalette} />
          </>
        ) : null}
      </div>
      ) : null}

      {!hasRasterResults ? (
        <div className="glass-panel rounded-lg p-4 text-sm text-slate-400">
          No raster layer selected for area statistics. Enable at least one raster layer to see NDVI/LST/LULC summaries.
        </div>
      ) : null}

      {(results ?? [])
        .filter((result) => visibleLayerIds.includes(result.layer_id))
        .map((result) => {
          const isCategorical = result.value_type === "categorical";
          const palette = result.legend?.palette ?? ["#22d3ee", "#0ea5e9"];
          const displayTitle = (result.title ?? result.layer_id)
            .replace(/^Planegg\s+/i, "")
            .replace(/^NDVI Health$/i, "Vegetation Health (NDVI)");

          return (
          <div key={result.layer_id} className="glass-panel rounded-xl border border-white/10 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-slate-100">{displayTitle}</span>
              <span className="text-[10px] uppercase tracking-wide text-slate-500">{result.units ?? ""}</span>
            </div>

            {isCategorical ? (
              result.selected.class_breakdown ? (
                overviewMode && result.layer_id === "lulc-planegg" ? (
                  <LulcPie items={result.selected.class_breakdown} />
                ) : (
                  <ClassBreakdownList
                    items={result.selected.class_breakdown}
                    baselineItems={result.baseline.class_breakdown}
                  />
                )
              ) : (
                <p className="text-xs text-slate-500">No classes found in selected area.</p>
              )
            ) : (
              <>
                {overviewMode ? (
                  <>
                    <div className="text-[12px] text-slate-300">
                      Area average: <span className="font-semibold text-cyan-300">{result.baseline.mean.toFixed(2)} {result.units ?? ""}</span>
                    </div>
                    <div className="mt-1 text-[10px] text-slate-500">
                      Range: {result.baseline.minimum.toFixed(1)} to {result.baseline.maximum.toFixed(1)} {result.units ?? ""}
                    </div>
                  </>
                ) : (
                  <ComparisonScale
                    palette={palette}
                    min={result.value_range?.minimum ?? result.baseline.minimum}
                    max={result.value_range?.maximum ?? result.baseline.maximum}
                    selectedValue={result.selected.mean}
                    averageValue={result.baseline.mean}
                    units={result.units}
                  />
                )}
                {result.selected.histogram ? (
                  (result.layer_id === "ndvi-planegg" || result.layer_id === "lst-planegg") ? (
                    <LayerThresholdPie
                      layerId={result.layer_id}
                      histogram={result.selected.histogram}
                      palette={palette}
                    />
                  ) : (
                    <ThresholdDistribution
                      layerId={result.layer_id}
                      histogram={result.selected.histogram}
                      units={result.units}
                      palette={palette}
                    />
                  )
                ) : (
                  <div className="mt-2 text-[11px] text-slate-500">No histogram available for this layer.</div>
                )}
              </>
            )}
          </div>
        );
        })}
    </div>
  );
}
