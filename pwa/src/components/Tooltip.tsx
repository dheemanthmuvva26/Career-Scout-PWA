"use client";
import { ReactNode } from "react";

type Position = "top" | "bottom" | "left" | "right";

export default function Tooltip({
  text,
  children,
  position = "top",
  className = "",
}: {
  text: string;
  children: ReactNode;
  position?: Position;
  className?: string;
}) {
  const posClasses: Record<Position, string> = {
    top:    "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left:   "right-full top-1/2 -translate-y-1/2 mr-2",
    right:  "left-full top-1/2 -translate-y-1/2 ml-2",
  };
  const arrowClasses: Record<Position, string> = {
    top:    "top-full left-1/2 -translate-x-1/2 border-t-slate-800",
    bottom: "bottom-full left-1/2 -translate-x-1/2 border-b-slate-800",
    left:   "left-full top-1/2 -translate-y-1/2 border-l-slate-800",
    right:  "right-full top-1/2 -translate-y-1/2 border-r-slate-800",
  };

  return (
    <div className={`relative group/tip inline-flex ${className}`}>
      {children}
      <div
        className={`absolute z-50 px-2.5 py-1.5 text-xs bg-slate-800 text-slate-100
          rounded-lg border border-slate-700 shadow-xl whitespace-nowrap
          opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150
          pointer-events-none select-none ${posClasses[position]}`}
      >
        {text}
        <span
          className={`absolute border-4 border-transparent ${arrowClasses[position]}`}
        />
      </div>
    </div>
  );
}
