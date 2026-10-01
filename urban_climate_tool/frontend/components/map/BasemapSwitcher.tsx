"use client";

import { BASEMAP_OPTIONS, type BasemapId } from "@/components/map/MapCanvas";

export function BasemapSwitcher({
  value,
  onChange,
}: {
  value: BasemapId;
  onChange: (id: BasemapId) => void;
}) {
  return (
    <div className="glass-panel flex items-center gap-1 rounded-lg p-1">
      {BASEMAP_OPTIONS.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
            value === option.id ? "bg-cyan-400/90 text-slate-950" : "text-slate-300 hover:bg-white/10"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
