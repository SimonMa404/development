"use client";

import type {
  BuildingStatisticsResult,
  ElevationStatisticsResult,
  HeatVulnerabilityResult,
  LandUseCompositionResult,
  TreeStatisticsResult,
} from "@/types/analysis";

type KpiCardProps = {
  title: string;
  value: string;
  hint?: string;
};

function KpiCard({ title, value, hint }: KpiCardProps) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
      <div className="text-[11px] text-slate-400">{title}</div>
      <div className="text-base font-semibold text-white">{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-slate-500">{hint}</div> : null}
    </div>
  );
}

function formatInt(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatDecimal(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function nutzungColorForCategory(category: string): string {
  const palette: Record<string, string> = {
    "Wohnbaufläche": "#f59e0b",
    "Industrie- und Gewerbefläche": "#6b7280",
    "Fläche gemischter Nutzung": "#a855f7",
    "Sport-, Freizeit- und Erholungsfläche": "#84cc16",
    Landwirtschaft: "#eab308",
    Wald: "#15803d",
    Gehölz: "#22c55e",
    "Stehendes Gewässer": "#3b82f6",
    "Fließgewässer": "#06b6d4",
    Straßenverkehr: "#475569",
    Bahnverkehr: "#334155",
    Weg: "#94a3b8",
    Platz: "#cbd5e1",
    Friedhof: "#65a30d",
    "Fläche besonderer funktionaler Prägung": "#f97316",
    "Tagebau, Grube, Steinbruch": "#92400e",
    "Unland/Vegetationslose Fläche": "#78716c",
  };
  return palette[category] ?? "#64748b";
}

function LandUseCompositionPanel({ landUse }: { landUse: LandUseCompositionResult }) {
  return (
    <div className="space-y-2">
      <div className="text-[11px] text-slate-400">
        Covered area: {landUse.summary.covered_area_hectares.toFixed(2)} ha ({landUse.summary.covered_share_pct.toFixed(1)}%)
      </div>
      <div className="space-y-1.5">
        {landUse.classes.map((item) => {
          const color = nutzungColorForCategory(item.category);
          return (
          <div key={item.category} className="rounded border border-white/10 bg-white/[0.02] p-2">
            <div className="mb-1 flex items-center justify-between text-[11px] text-slate-200">
              <span className="inline-flex min-w-0 items-center gap-2 truncate pr-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: color }} />
                <span className="truncate">{item.category}</span>
              </span>
              <span className="text-white">{item.share_of_selected_pct.toFixed(1)}%</span>
            </div>
            <div className="h-2 w-full rounded bg-white/5">
              <div
                className="h-2 rounded"
                style={{
                  backgroundColor: color,
                  width: `${Math.max(1, Math.min(100, item.share_of_selected_pct))}%`,
                }}
              />
            </div>
            <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
              <span>{item.area_hectares.toFixed(2)} ha</span>
              <span>{item.feature_count} features</span>
            </div>
          </div>
          );
        })}
      </div>
      {landUse.summary.uncovered_area_hectares > 0.01 ? (
        <div className="text-[10px] text-slate-500">Uncovered in selection: {landUse.summary.uncovered_area_hectares.toFixed(2)} ha</div>
      ) : null}
    </div>
  );
}

export function AnalysisPanel({
  isPending,
  error,
  municipalityName = "Gemeinde Planegg",
  scopeLabel = "Gemeinde Planegg",
  latestLulcYear = null,
  latestLulcItems = [],
  treeStats = null,
  treeStatsPending = false,
  treeStatsError = null,
  buildingStats = null,
  buildingStatsPending = false,
  buildingStatsError = null,
  elevationStats = null,
  elevationStatsPending = false,
  elevationStatsError = null,
  vulnerability = null,
  vulnerabilityPending = false,
  vulnerabilityError = null,
  showBuildings = true,
  showVulnerability = true,
  showTrees = true,
  showLandUse = false,
  landUse = null,
  landUsePending = false,
  landUseError = null,
  totalAreaHectares = null,
}: {
  isPending: boolean;
  error: Error | null;
  municipalityName?: string;
  scopeLabel?: string;
  latestLulcYear?: number | null;
  latestLulcItems?: Array<{ key: string; label: string; color: string; value: number; unit: "ha" | "%" }>;
  treeStats?: TreeStatisticsResult | null;
  treeStatsPending?: boolean;
  treeStatsError?: Error | null;
  buildingStats?: BuildingStatisticsResult | null;
  buildingStatsPending?: boolean;
  buildingStatsError?: Error | null;
  elevationStats?: ElevationStatisticsResult | null;
  elevationStatsPending?: boolean;
  elevationStatsError?: Error | null;
  vulnerability?: HeatVulnerabilityResult | null;
  vulnerabilityPending?: boolean;
  vulnerabilityError?: Error | null;
  showBuildings?: boolean;
  showVulnerability?: boolean;
  showTrees?: boolean;
  showLandUse?: boolean;
  landUse?: LandUseCompositionResult | null;
  landUsePending?: boolean;
  landUseError?: Error | null;
  totalAreaHectares?: number | null;
}) {
  if (isPending) {
    return <div className="glass-panel rounded-lg p-4 text-sm text-slate-400">Loading My Commune overview…</div>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
        Failed to load overview: {error.message}
      </div>
    );
  }

  const populationCategories = vulnerability?.summary.population_categories ?? [];
  const latestLandCoverTotal = latestLulcItems.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="space-y-4">
      <div className="glass-panel rounded-xl border border-white/10 p-3">
        <div className="text-[11px] uppercase tracking-wide text-slate-500">My Commune</div>
        <div className="mt-0.5 text-lg font-semibold text-cyan-200">{municipalityName}</div>
        <div className="text-[11px] text-slate-400">Scope: {scopeLabel}</div>
      </div>

      <div className="glass-panel rounded-xl border border-white/10 p-3">
        <div className="mb-2 text-sm font-medium text-slate-100">Area & land cover 🗺️</div>
        <div className="rounded border border-white/10 bg-white/[0.02] p-2">
          <div className="text-[11px] text-slate-400">Total area</div>
          <div className="text-2xl font-semibold text-white">
            {totalAreaHectares !== null ? `${formatDecimal(totalAreaHectares, 2)} ha` : "—"}
          </div>
        </div>

        <div className="mt-2 text-[11px] text-slate-400">
          Latest land cover classes
          {latestLulcYear ? ` (${latestLulcYear})` : ""}
        </div>

        {latestLulcItems.length > 0 ? (
          <div className="mt-1.5 space-y-1.5">
            {latestLulcItems.map((item) => {
              const share = latestLandCoverTotal > 0 ? (item.value / latestLandCoverTotal) * 100 : 0;
              return (
                <div key={item.key} className="rounded border border-white/10 bg-white/[0.02] p-2">
                  <div className="mb-1 flex items-center justify-between text-[11px] text-slate-200">
                    <span className="inline-flex min-w-0 items-center gap-2 truncate pr-2">
                      <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: item.color }} />
                      <span className="truncate">{item.label}</span>
                    </span>
                    <span className="text-white">{share.toFixed(1)}%</span>
                  </div>
                  <div className="h-2 w-full rounded bg-white/5">
                    <div
                      className="h-2 rounded"
                      style={{
                        backgroundColor: item.color,
                        width: `${Math.max(1, Math.min(100, share))}%`,
                      }}
                    />
                  </div>
                  <div className="mt-1 text-[10px] text-slate-500">{formatDecimal(item.value, 1)} {item.unit}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="mt-1 text-[10px] text-slate-500">No land cover values available.</div>
        )}
      </div>

      {showTrees ? (
        <div className="glass-panel rounded-xl border border-white/10 p-3">
          <div className="mb-2 text-sm font-medium text-slate-100">Trees 🌳</div>
          {treeStatsPending ? <div className="text-[11px] text-slate-500">Computing tree statistics…</div> : null}
          {treeStatsError ? <div className="text-[11px] text-red-300">{treeStatsError.message}</div> : null}
          {treeStats ? (
            <div className="grid grid-cols-2 gap-2">
              <KpiCard title="Amount of trees" value={formatInt(treeStats.tree_count)} />
              <KpiCard title="Average tree height" value={`${formatDecimal(treeStats.mean_height)} m`} />
            </div>
          ) : null}
        </div>
      ) : null}

      {showBuildings ? (
        <div className="glass-panel rounded-xl border border-white/10 p-3">
          <div className="mb-2 text-sm font-medium text-slate-100">Buildings 🏢</div>
          {buildingStatsPending ? <div className="text-[11px] text-slate-500">Computing building statistics…</div> : null}
          {buildingStatsError ? <div className="text-[11px] text-red-300">{buildingStatsError.message}</div> : null}
          {buildingStats ? (
            <div className="grid grid-cols-2 gap-2">
              <KpiCard title="Amount of buildings" value={formatInt(buildingStats.building_count)} />
              <KpiCard title="Average building height" value={`${formatDecimal(buildingStats.mean_height)} m`} />
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="glass-panel rounded-xl border border-white/10 p-3">
        <div className="mb-2 text-sm font-medium text-slate-100">Elevation ⛰️</div>
        {elevationStatsPending ? <div className="text-[11px] text-slate-500">Computing elevation statistics…</div> : null}
        {elevationStatsError ? <div className="text-[11px] text-red-300">{elevationStatsError.message}</div> : null}
        {elevationStats ? (
          <div className="grid grid-cols-3 gap-2">
            <KpiCard title="Average" value={`${formatDecimal(elevationStats.mean_elevation)} m`} />
            <KpiCard title="Highest point" value={`${formatDecimal(elevationStats.maximum_elevation)} m`} />
            <KpiCard title="Lowest point" value={`${formatDecimal(elevationStats.minimum_elevation)} m`} />
          </div>
        ) : null}
      </div>

      {showVulnerability ? (
        <div className="glass-panel rounded-xl border border-white/10 p-3">
          <div className="mb-2 text-sm font-medium text-slate-100">Population breakdown 👥</div>
          {vulnerabilityPending ? <div className="text-[11px] text-slate-500">Computing population statistics…</div> : null}
          {vulnerabilityError ? <div className="text-[11px] text-red-300">{vulnerabilityError.message}</div> : null}
          {vulnerability ? (
            <div className="space-y-2">
              <div className="grid grid-cols-1 gap-2">
                <KpiCard title="Total population" value={formatInt(vulnerability.summary.total_population)} />
              </div>
              <div className="space-y-1">
                {(populationCategories.length > 0 ? populationCategories : [
                  { key: "children_u18", label: "Children (<18)", population: vulnerability.summary.children_population, share: vulnerability.summary.children_share },
                  { key: "elderly_65_plus", label: "Elderly (65+)", population: vulnerability.summary.elderly_population, share: vulnerability.summary.elderly_share },
                ]).map((item) => (
                  <div key={item.key} className="flex items-center justify-between rounded border border-white/10 bg-white/[0.02] px-2 py-1.5 text-[11px]">
                    <span className="text-slate-300">{item.label}</span>
                    <span className="font-semibold text-white">
                      {formatInt(item.population)}
                      {item.share !== null && item.share !== undefined ? (
                        <span className="ml-1 text-[10px] text-slate-500">({(item.share * 100).toFixed(1)}%)</span>
                      ) : null}
                    </span>
                  </div>
                ))}
              </div>
              {vulnerability.summary.missing_population ? (
                <div className="text-[10px] text-slate-500">
                  Missing population records: {formatInt(vulnerability.summary.missing_population)}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {showLandUse ? (
        <div className="glass-panel rounded-xl border border-white/10 p-3">
          <div className="mb-2 text-sm font-medium text-slate-100">ALKIS land-use composition 🗺️</div>
          {landUsePending ? <div className="text-[11px] text-slate-500">Computing ALKIS composition…</div> : null}
          {landUseError ? <div className="text-[11px] text-red-300">{landUseError.message}</div> : null}
          {landUse ? <LandUseCompositionPanel landUse={landUse} /> : null}
        </div>
      ) : null}
    </div>
  );
}
