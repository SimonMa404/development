export function DrawToolbar({
  drawMode,
  pointCount,
  onStart,
  onFinish,
  onClear,
}: {
  drawMode: boolean;
  pointCount: number;
  onStart: () => void;
  onFinish: () => void;
  onClear: () => void;
}) {
  return (
    <div className="glass-panel flex items-center gap-2 rounded-lg p-2">
      {!drawMode ? (
        <button
          type="button"
          onClick={onStart}
          className="rounded-md bg-cyan-400/90 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-cyan-300"
        >
          Draw analysis area
        </button>
      ) : (
        <>
          <span className="text-xs text-slate-300">
            Click the map to add points ({pointCount} added, min. 3)
          </span>
          <button
            type="button"
            onClick={onFinish}
            disabled={pointCount < 3}
            className="rounded-md bg-emerald-400/90 px-3 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-400"
          >
            Finish
          </button>
          <button
            type="button"
            onClick={onClear}
            className="rounded-md bg-white/10 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-white/20"
          >
            Cancel
          </button>
        </>
      )}
    </div>
  );
}
