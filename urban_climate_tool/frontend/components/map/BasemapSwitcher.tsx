"use client";

import { type BasemapId, type SatelliteBasemapSource } from "@/components/map/MapCanvas";

export function BasemapSwitcher({
  value,
  satelliteSource,
  onChange,
  onSatelliteSourceChange,
}: {
  value: BasemapId;
  satelliteSource: SatelliteBasemapSource;
  onChange: (id: BasemapId) => void;
  onSatelliteSourceChange: (source: SatelliteBasemapSource) => void;
}) {
  const baseButtonClass = "rounded-md px-2.5 py-1 text-[11px] font-medium transition";

  return (
    <div className="glass-panel relative z-50 flex items-center gap-1 rounded-lg p-1">
      <div className="relative z-50 group/satellite">
        <button
          type="button"
          onClick={() => onChange("satellite")}
          className={`${baseButtonClass} ${
            value === "satellite" ? "bg-cyan-400/90 text-slate-950" : "text-slate-300 hover:bg-white/10"
          }`}
        >
          Satellite
        </button>

        {value === "satellite" ? (
          <div className="pointer-events-none absolute left-0 top-full z-[80] min-w-[150px] rounded-md border border-white/15 bg-slate-900/95 p-1 opacity-0 shadow-xl transition group-hover/satellite:pointer-events-auto group-hover/satellite:opacity-100 group-focus-within/satellite:pointer-events-auto group-focus-within/satellite:opacity-100">
            <button
              type="button"
              onClick={() => onSatelliteSourceChange("bayern-20cm")}
              className={`block w-full rounded px-2 py-1 text-left text-[10px] font-medium transition ${
                satelliteSource === "bayern-20cm" ? "bg-cyan-400/85 text-slate-950" : "text-slate-200 hover:bg-white/10"
              }`}
            >
              Bayern 20cm
            </button>
            <button
              type="button"
              onClick={() => onSatelliteSourceChange("global")}
              className={`mt-1 block w-full rounded px-2 py-1 text-left text-[10px] font-medium transition ${
                satelliteSource === "global" ? "bg-cyan-400/85 text-slate-950" : "text-slate-200 hover:bg-white/10"
              }`}
            >
              Global
            </button>
          </div>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => onChange("hybrid")}
        className={`${baseButtonClass} ${
          value === "hybrid" ? "bg-cyan-400/90 text-slate-950" : "text-slate-300 hover:bg-white/10"
        }`}
      >
        Hybrid
      </button>

      <button
        type="button"
        onClick={() => onChange("dark")}
        className={`${baseButtonClass} ${
          value === "dark" ? "bg-cyan-400/90 text-slate-950" : "text-slate-300 hover:bg-white/10"
        }`}
      >
        Dark
      </button>
    </div>
  );
}
