"use client";

import { useMemo, useState } from "react";

export type LulcClassSeries = {
  classKey: string;
  label: string;
  color: string;
};

export type LulcYearPoint = {
  year: number;
  layerId: string;
  title: string;
  available: boolean;
  builtAreaHectares?: number | null;
  totalAreaHectares?: number | null;
  classValues?: Record<string, number> | null;
};

export type LulcYearRange = {
  fromYear: number | null;
  toYear: number | null;
};

export function LulcChangePanel({
  points,
  classSeries,
  scope,
  selectedLayerId,
  onSelectYear,
  yearRange,
  onYearRangeChange,
  showYearList = true,
}: {
  points: LulcYearPoint[];
  classSeries: LulcClassSeries[];
  scope: "planegg" | "drawn";
  selectedLayerId: string | null;
  onSelectYear: (point: LulcYearPoint) => void;
  yearRange: LulcYearRange;
  onYearRangeChange: (range: LulcYearRange) => void;
  showYearList?: boolean;
}) {
  const [hoverX, setHoverX] = useState<number | null>(null);

  const allClassValues = points.flatMap((point) =>
    classSeries
      .map((series) => point.classValues?.[series.classKey])
      .filter((value): value is number => value !== null && value !== undefined && Number.isFinite(value)),
  );
  const maxValue = allClassValues.length ? Math.max(...allClassValues) : 1;
  const minValue = 0;
  const span = Math.max(0.1, maxValue - minValue);
  const plotWidth = 340;
  const plotHeight = 190;
  const paddingLeft = 34;
  const paddingRight = 10;
  const paddingTop = 16;
  const paddingBottom = 30;

  const withX = points.map((point, index) => {
    const x = points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * (plotWidth - paddingLeft - paddingRight) + paddingLeft;
    return { x, point };
  });

  const nearestHoverIndex = useMemo(() => {
    if (hoverX === null || withX.length === 0) return null;
    let bestIndex = 0;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let index = 0; index < withX.length; index += 1) {
      const distance = Math.abs(withX[index].x - hoverX);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    }
    return bestIndex;
  }, [hoverX, withX]);

  const seriesPaths = classSeries
    .map((series) => {
      const seriesPoints = withX.flatMap(({ x, point }) => {
        const value = point.classValues?.[series.classKey];
        if (value === null || value === undefined || !Number.isFinite(value)) return [];
        const y = plotHeight - paddingBottom - ((value - minValue) / span) * (plotHeight - paddingTop - paddingBottom);
        return [{ x, y, point, value }];
      });
      if (seriesPoints.length < 2) return null;
      const pathData = seriesPoints.map((item, index) => `${index === 0 ? "M" : "L"}${item.x.toFixed(1)} ${item.y.toFixed(1)}`).join(" ");
      return { series, points: seriesPoints, pathData };
    })
    .filter((entry): entry is { series: LulcClassSeries; points: Array<{ x: number; y: number; point: LulcYearPoint; value: number }>; pathData: string } => entry !== null);

  const firstYear = points[0]?.year;
  const lastYear = points[points.length - 1]?.year;
  const yAxisUnit = scope === "drawn" ? "%" : "ha";
  const yAxisLabel = scope === "drawn" ? "Class share (%)" : "Class area (ha)";
  const nearestHoverPoint = nearestHoverIndex !== null ? withX[nearestHoverIndex]?.point : null;

  if (!points.length) {
    return <p className="text-xs text-slate-400">No yearly LULC layers registered yet.</p>;
  }

  function handleChartHover(clientX: number, left: number, width: number) {
    const cursorPx = clientX - left;
    const clampedPx = Math.max(0, Math.min(width, cursorPx));
    const x = (clampedPx / width) * plotWidth;
    setHoverX(x);
  }

  function handleChartClick() {
    if (nearestHoverIndex === null) return;
    const point = withX[nearestHoverIndex]?.point;
    if (!point || !point.available) return;
    onSelectYear(point);
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-cyan-300">Land cover change</h3>
        <p className="mt-1 text-[11px] text-slate-400">
          <span>Select a year to show that LULC composite on the map. </span>
          <span>Each line is one Dynamic World class in the same color as the map legend. </span>
          <span>Or select two years for change detection.</span>
        </p>
      </div>

      <div className="rounded-md border border-white/10 bg-white/[0.02] p-2 text-[11px] text-slate-300">
        <div className="flex items-center justify-between gap-2">
          <span>Coverage</span>
          <span>{firstYear ?? "—"} → {lastYear ?? "—"}</span>
        </div>
        <div className="mt-1 text-[10px] text-slate-500">Scope: {scope === "drawn" ? "Drawn area" : "Planegg"} · Unit: {yAxisUnit}</div>
      </div>

      <div className="rounded-lg border border-white/10 bg-white/[0.02] p-2">
        {seriesPaths.length > 0 ? (
          <svg
            viewBox={`0 0 ${plotWidth} ${plotHeight}`}
            className="h-44 w-full cursor-crosshair"
            onMouseMove={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              handleChartHover(event.clientX, rect.left, rect.width);
            }}
            onMouseLeave={() => setHoverX(null)}
            onClick={handleChartClick}
          >
            <line x1={paddingLeft} y1={plotHeight - paddingBottom} x2={plotWidth - paddingRight} y2={plotHeight - paddingBottom} stroke="#334155" strokeWidth="1" />
            <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={plotHeight - paddingBottom} stroke="#334155" strokeWidth="1" />
            {hoverX !== null ? (
              <line
                x1={hoverX}
                y1={paddingTop}
                x2={hoverX}
                y2={plotHeight - paddingBottom}
                stroke="#67e8f9"
                strokeWidth="1"
                strokeDasharray="3 3"
                opacity="0.9"
              />
            ) : null}
            {seriesPaths.map(({ series, pathData }) => (
              <path key={series.classKey} d={pathData} fill="none" stroke={series.color} strokeWidth="1.8" />
            ))}
            <text x={paddingLeft - 4} y={paddingTop + 2} textAnchor="end" fontSize="9" fill="#94a3b8">{maxValue.toFixed(1)} {yAxisUnit}</text>
            <text x={paddingLeft - 4} y={plotHeight - paddingBottom + 3} textAnchor="end" fontSize="9" fill="#94a3b8">0 {yAxisUnit}</text>
            <text x={10} y={plotHeight / 2} fontSize="9" fill="#64748b" transform={`rotate(-90 10 ${plotHeight / 2})`}>{yAxisLabel}</text>
            {withX.map(({ x, point }, index) => {
              const selected = selectedLayerId === point.layerId;
              const hovered = nearestHoverPoint?.layerId === point.layerId;
              const showYear = points.length <= 10 || index % 2 === 0 || index === points.length - 1;
              const midClass = classSeries[0];
              const midValue = midClass ? point.classValues?.[midClass.classKey] : null;
              const y = midValue !== null && midValue !== undefined
                ? plotHeight - paddingBottom - ((midValue - minValue) / span) * (plotHeight - paddingTop - paddingBottom)
                : plotHeight - paddingBottom;
              return (
                <g key={point.layerId} onClick={() => point.available && onSelectYear(point)} className={point.available ? "cursor-pointer" : "opacity-60"}>
                  <circle cx={x} cy={y} r={selected ? 4.4 : hovered ? 4 : 3.2} fill={selected ? "#67e8f9" : hovered ? "#cbd5e1" : "#94a3b8"} />
                  {showYear ? (
                    <text x={x} y={plotHeight - 6} textAnchor="middle" fontSize="9" fill={hovered ? "#cbd5e1" : "#94a3b8"}>{point.year}</text>
                  ) : null}
                </g>
              );
            })}
            {nearestHoverPoint ? (
              <text x={plotWidth - 4} y={paddingTop + 2} textAnchor="end" fontSize="9" fill="#67e8f9">
                {nearestHoverPoint.year}
              </text>
            ) : null}
          </svg>
        ) : (
          <p className="text-[11px] text-slate-500">Need at least two years with class values to draw a line chart.</p>
        )}

        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] text-slate-400">
          {classSeries.map((series) => (
            <div key={series.classKey} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: series.color }} />
              <span>{series.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Change Detection Year Range Selector */}
      <div className="rounded-md border border-white/10 bg-white/[0.02] p-2 text-[11px] text-slate-300">
        <div className="mb-2 font-medium text-slate-200">Change Detection</div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="mb-1 block text-[10px] text-slate-400">From Year</label>
            <select
              value={yearRange.fromYear ?? ""}
              onChange={(e) =>
                onYearRangeChange({
                  fromYear: e.target.value ? parseInt(e.target.value, 10) : null,
                  toYear: yearRange.toYear,
                })
              }
              className="w-full rounded border border-white/10 bg-slate-900 px-2 py-1 text-[10px] text-slate-200"
            >
              <option value="">Select year</option>
              {points.filter((p) => p.available).map((point) => (
                <option key={point.layerId} value={point.year}>
                  {point.year}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] text-slate-400">To Year</label>
            <select
              value={yearRange.toYear ?? ""}
              onChange={(e) =>
                onYearRangeChange({
                  fromYear: yearRange.fromYear,
                  toYear: e.target.value ? parseInt(e.target.value, 10) : null,
                })
              }
              className="w-full rounded border border-white/10 bg-slate-900 px-2 py-1 text-[10px] text-slate-200"
            >
              <option value="">Select year</option>
              {points.filter((p) => p.available && (!yearRange.fromYear || p.year > yearRange.fromYear)).map((point) => (
                <option key={point.layerId} value={point.year}>
                  {point.year}
                </option>
              ))}
            </select>
          </div>
        </div>
        {yearRange.fromYear && yearRange.toYear && yearRange.fromYear !== yearRange.toYear ? (
          <div className="mt-2 rounded bg-cyan-400/10 px-2 py-1 text-[10px] text-cyan-200">
            Change detection: {yearRange.fromYear} → {yearRange.toYear}
          </div>
        ) : yearRange.fromYear === yearRange.toYear && yearRange.fromYear ? (
          <div className="mt-2 rounded bg-yellow-400/10 px-2 py-1 text-[10px] text-yellow-200">
            Select different years for change detection
          </div>
        ) : null}
      </div>

      {showYearList ? (
        <div className="space-y-1">
          {points.map((point) => {
          const selected = selectedLayerId === point.layerId;
          const classEntries = classSeries
            .map((series) => ({
              ...series,
              value: point.classValues?.[series.classKey],
            }))
            .filter((entry) => entry.value !== null && entry.value !== undefined && Number.isFinite(entry.value))
            .sort((a, b) => (b.value as number) - (a.value as number));
          const topEntries = classEntries.slice(0, 3);
          const dominant = classEntries[0] ?? null;

            return (
              <button
                key={point.layerId}
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
                  <span>{point.available ? "available" : "missing raster"}</span>
                </div>
                <div className="mt-0.5 text-[10px] text-slate-500">
                  {point.title} · Built: {point.builtAreaHectares !== null && point.builtAreaHectares !== undefined ? `${point.builtAreaHectares.toFixed(2)} ${yAxisUnit}` : "—"}
                </div>
                {dominant ? (
                  <div className="mt-1 text-[10px] text-slate-400">
                    Dominant: <span className="text-slate-300">{dominant.label}</span> ({(dominant.value as number).toFixed(2)} {yAxisUnit})
                  </div>
                ) : null}
                {topEntries.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {topEntries.map((entry) => (
                      <span
                        key={`${point.layerId}-${entry.classKey}`}
                        className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-slate-300"
                      >
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
                        <span>{entry.label}</span>
                        <span className="text-slate-400">{(entry.value as number).toFixed(1)} {yAxisUnit}</span>
                      </span>
                    ))}
                  </div>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
