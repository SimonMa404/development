"use client";

import { type ReactNode } from "react";

export function CollapsiblePanel({
  title,
  isOpen,
  onToggle,
  children,
  widthClass = "w-80",
  badge,
}: {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
  widthClass?: string;
  badge?: ReactNode;
}) {
  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="glass-panel inline-flex items-center gap-2 rounded-xl px-3 py-2 text-left"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-cyan-300">{title}</span>
        {badge}
      </button>
    );
  }

  return (
    <div className={`glass-panel flex h-full min-h-0 flex-col rounded-xl ${widthClass}`}>
      <button
        type="button"
        onClick={onToggle}
        className="flex shrink-0 items-center justify-between gap-3 rounded-t-xl px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-cyan-300">
          {title}
          {badge}
        </span>
        <span className="flex shrink-0 items-center gap-1 text-[10px] font-medium text-slate-400">
          Hide
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            className="shrink-0"
          >
            <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </button>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">{children}</div>
    </div>
  );
}
