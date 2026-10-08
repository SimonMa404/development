"use client";

import type { RelativeSummerLstPoint } from "@/types/analysis";

function formatSigned(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatMaybe(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

const LST_PALETTE = ["#313695", "#4575b4", "#74add1", "#abd9e9", "#e0f3f8", "#fee090", "#fdae61", "#f46d43", "#d73027"];

function hexToRgb(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

function rgbToHex(r: number, g: number, b: number): string {
  return `#${Math.round(r).toString(16).padStart(2, "0")}${Math.round(g).toString(16).padStart(2, "0")}${Math.round(b).toString(16).padStart(2, "0")}`;
}

function lerpPaletteColor(t: number, palette: string[]): string {
  if (palette.length === 0) return "#94a3b8";
  if (palette.length === 1) return palette[0];
  const clamped = Math.max(0, Math.min(1, t));
  const scaled = clamped * (palette.length - 1);
  const i0 = Math.floor(scaled);
  const i1 = Math.min(palette.length - 1, i0 + 1);
  const f = scaled - i0;
  const [r0, g0, b0] = hexToRgb(palette[i0]);
  const [r1, g1, b1] = hexToRgb(palette[i1]);
  return rgbToHex(r0 + (r1 - r0) * f, g0 + (g1 - g0) * f, b0 + (b1 - b0) * f);
}

function lstColor(temp: number, min: number, max: number): string {
  const span = Math.max(0.1, max - min);
  const t = Math.max(0, Math.min(1, (temp - min) / span));
  return lerpPaletteColor(t, LST_PALETTE);
}

export function RelativeSummerLstPanel({
  points,
  isPending,
  error,
  selectedLayerId,
  onSelectYear,
}: {
  points: RelativeSummerLstPoint[];
  isPending: boolean;
  error: Error | null;
  selectedLayerId: string | null;
  onSelectYear: (point: RelativeSummerLstPoint) => void;
}) {
  if (isPending) {
    return <p className="text-xs text-slate-400">Loading relative summer LST time series…</p>;
  }

  if (error) {
    return <p className="text-xs text-red-300">{error.message}</p>;
  }

  if (!points.length) {
    return <p className="text-xs text-slate-400">No yearly relative summer LST layers registered yet.</p>;
  }

  const withValues = points.filter((point) => point.mean_scene_lst_deg_c !== null && point.mean_scene_lst_deg_c !== undefined);
  const minValue = 0;
  const hottest = withValues.length ? Math.max(...withValues.map((point) => point.mean_scene_lst_deg_c as number)) : 35;
  const maxValue = Math.max(1, Math.ceil(hottest + 1));
  const span = Math.max(0.1, maxValue - minValue);

  const plotWidth = 340;
  const plotHeight = 178;
  const paddingLeft = 34;
  const paddingRight = 12;
  const paddingTop = 16;
  const paddingBottom = 24;

  const pathPoints = withValues.map((point, index) => {
    const x = withValues.length === 1
      ? plotWidth / 2
      : (index / (withValues.length - 1)) * (plotWidth - paddingLeft - paddingRight) + paddingLeft;
    const y = plotHeight - paddingBottom - (((point.mean_scene_lst_deg_c as number) - minValue) / span) * (plotHeight - paddingTop - paddingBottom);
    return { x, y, point };
  });

  const pathData = pathPoints
    .map((item, index) => `${index === 0 ? "M" : "L"}${item.x.toFixed(1)} ${item.y.toFixed(1)}`)
    .join(" ");

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Summer LST time series (absolute °C)</h3>
        <p className="mt-1 text-[11px] text-slate-400">Click a chart point or year row to update the map. Chart shows absolute summer mean LST (°C), while the map shows normalized anomaly (cooler/warmer than Planegg mean).</p>
        <p className="mt-1 text-[10px] text-slate-500">Thermal values are coarse (Landsat thermal 100m resampled to 30m).</p>
      </div>

      <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
        {withValues.length > 1 ? (
          <svg viewBox={`0 0 ${plotWidth} ${plotHeight}`} className="h-44 w-full">
            <defs>
              <linearGradient
                id="lst-series-gradient"
                gradientUnits="userSpaceOnUse"
                x1={pathPoints[0]?.x ?? paddingLeft}
                y1="0"
                x2={pathPoints[pathPoints.length - 1]?.x ?? plotWidth - paddingRight}
                y2="0"
              >
                {pathPoints.map(({ x, point }) => {
                  const value = point.mean_scene_lst_deg_c as number;
                  const offset = pathPoints.length <= 1
                    ? 0
                    : ((x - (pathPoints[0]?.x ?? 0)) / ((pathPoints[pathPoints.length - 1]?.x ?? 1) - (pathPoints[0]?.x ?? 0))) * 100;
                  return (
                    <stop
                      key={`stop-${point.layer_id}`}
                      offset={`${Math.max(0, Math.min(100, offset)).toFixed(2)}%`}
                      stopColor={lstColor(value, minValue, maxValue)}
                    />
                  );
                })}
              </linearGradient>
            </defs>
            <line x1={paddingLeft} y1={plotHeight - paddingBottom} x2={plotWidth - paddingRight} y2={plotHeight - paddingBottom} stroke="#334155" strokeWidth="1" />
            <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={plotHeight - paddingBottom} stroke="#334155" strokeWidth="1" />
            <path d={pathData} fill="none" stroke="url(#lst-series-gradient)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
            <text x={paddingLeft - 4} y={paddingTop + 2} textAnchor="end" fontSize="9" fill="#94a3b8">{maxValue.toFixed(1)}°C</text>
            <text x={paddingLeft - 4} y={plotHeight - paddingBottom + 3} textAnchor="end" fontSize="9" fill="#94a3b8">0°C</text>
            <text x={10} y={plotHeight / 2} fontSize="9" fill="#64748b" transform={`rotate(-90 10 ${plotHeight / 2})`}>LST (°C)</text>
            {pathPoints.map(({ x, y, point }) => {
              const selected = selectedLayerId === point.layer_id;
              const clickable = point.available;
              const value = point.mean_scene_lst_deg_c as number;
              const pointColor = lstColor(value, minValue, maxValue);
              return (
                <g
                  key={point.layer_id}
                  onClick={() => {
                    if (clickable) onSelectYear(point);
                  }}
                  className={clickable ? "cursor-pointer" : "opacity-60"}
                >
                  <circle cx={x} cy={y} r={selected ? 4.8 : 3.8} fill={selected ? "#67e8f9" : pointColor} />
                  <text x={x} y={Math.max(9, y - 7)} textAnchor="middle" fontSize="8.5" fill="#cbd5e1">{value.toFixed(1)}°</text>
                  <text x={x} y={plotHeight - 4} textAnchor="middle" fontSize="9" fill="#94a3b8">{point.year}</text>
                </g>
              );
            })}
          </svg>
        ) : (
          <p className="text-[11px] text-slate-500">Need at least two years with absolute LST values to draw a line chart.</p>
        )}
      </div>

      <div className="space-y-1">
        {points.map((point) => {
          const selected = selectedLayerId === point.layer_id;
          return (
            <button
              key={point.layer_id}
              type="button"
              disabled={!point.available}
              onClick={() => onSelectYear(point)}
              className={`w-full rounded-md border px-2 py-1.5 text-left text-[11px] transition ${
                selected
                  ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                  : "border-white/10 bg-white/[0.02] text-slate-300 hover:bg-white/10"
              } ${!point.available ? "cursor-not-allowed opacity-50" : ""}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{point.year}</span>
                <span>
                  {point.mean_scene_lst_deg_c !== null && point.mean_scene_lst_deg_c !== undefined
                    ? `${formatMaybe(point.mean_scene_lst_deg_c)} °C`
                    : "No summary"}
                </span>
              </div>
              <div className="mt-0.5 text-[10px] text-slate-500">
                Scenes: {point.n_scenes ?? "—"} · ROI anomaly mean: {point.mean_anomaly_deg_c !== null && point.mean_anomaly_deg_c !== undefined ? `${formatSigned(point.mean_anomaly_deg_c)} °C` : "—"}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
