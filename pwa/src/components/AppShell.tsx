"use client";

import { useState, useEffect } from "react";
import type { ReactNode } from "react";
import { ViewModeCtx, type ViewMode } from "@/lib/viewMode";
import BottomNav from "./BottomNav";
import Sidebar from "./Sidebar";
import WarmUp from "./WarmUp";

export default function AppShell({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ViewMode>("mobile");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("cs_viewMode") as ViewMode | null;
    if (stored === "desktop" || stored === "mobile") setMode(stored);
    setReady(true);
  }, []);

  function toggle() {
    setMode(prev => {
      const next: ViewMode = prev === "mobile" ? "desktop" : "mobile";
      localStorage.setItem("cs_viewMode", next);
      return next;
    });
  }

  const isDesktop = ready && mode === "desktop";

  return (
    <ViewModeCtx.Provider value={{ mode, toggle }}>
      <WarmUp />
      {isDesktop && <Sidebar />}
      <main
        id="app-scroll"
        className="flex-1 overflow-y-auto no-scrollbar"
        style={{
          paddingBottom: isDesktop
            ? "2rem"
            : "calc(88px + env(safe-area-inset-bottom, 0px))",
          marginLeft: isDesktop ? 216 : 0,
          transition: ready ? "margin-left 0.25s cubic-bezier(0.23,1,0.32,1)" : "none",
        }}
      >
        <div style={{
          maxWidth: isDesktop ? 1100 : 512,
          margin: "0 auto",
          padding: isDesktop ? "0 2.5rem" : "0 1rem",
        }}>
          {children}
        </div>
      </main>
      {!isDesktop && <BottomNav />}

      {/* Desktop toggle pill — shown in mobile mode so user can switch */}
      {!isDesktop && (
        <button
          onClick={toggle}
          className="fixed z-50 flex items-center gap-1.5 transition-all active:scale-95"
          style={{
            top: 14,
            right: 16,
            padding: "5px 10px",
            borderRadius: 20,
            background: "rgba(4,11,18,0.85)",
            backdropFilter: "blur(12px) saturate(180%)",
            WebkitBackdropFilter: "blur(12px) saturate(180%)",
            border: "1px solid rgba(255,255,255,0.08)",
            color: "var(--text-3)",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.04em",
            boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          }}
        >
          <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="16" y2="21" strokeLinecap="round"/>
            <line x1="12" y1="17" x2="12" y2="21" strokeLinecap="round"/>
          </svg>
          Desktop
        </button>
      )}
    </ViewModeCtx.Provider>
  );
}
