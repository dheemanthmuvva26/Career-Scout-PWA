"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Tooltip from "./Tooltip";

const tabs = [
  { href: "/dashboard", label: "Home",     icon: "⌂",  tooltip: "Dashboard overview" },
  { href: "/jobs",      label: "Jobs",     icon: "◈",  tooltip: "Browse & import jobs" },
  { href: "/tracker",   label: "Track",    icon: "⊟",  tooltip: "Application pipeline" },
  { href: "/forge",     label: "Forge",    icon: "⬡",  tooltip: "Generate tailored resume" },
  { href: "/insights",  label: "Insights", icon: "⬗",  tooltip: "Skill gaps & signals" },
];

const SVG_ICONS: Record<string, React.ReactNode> = {
  "/dashboard": (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
    </svg>
  ),
  "/jobs": (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M20 6h-2.18c.07-.44.18-.86.18-1a3 3 0 0 0-6 0c0 .14.11.56.18 1H10C8.9 6 8 6.9 8 8v12c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-7-1c0-.55.45-1 1-1s1 .45 1 1-.45 1-1 1-1-.45-1-1zm2 14h-2v-2h2v2zm3.5-6l-4.5 4.5-2-2 1.06-1.06L12 17.44l3.44-3.44L16.5 15z"/>
    </svg>
  ),
  "/tracker": (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
    </svg>
  ),
  "/forge": (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
    </svg>
  ),
  "/insights": (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>
    </svg>
  ),
};

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  return pathname.startsWith(href);
}

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="sidebar-rail">
        <div className="px-5 mb-8">
          <div className="text-base font-bold text-white tracking-tight">Career Scout</div>
          <div className="text-xs text-slate-500 mt-0.5">Job Intelligence</div>
        </div>
        <nav className="flex flex-col gap-1 px-3 flex-1">
          {tabs.map((tab) => {
            const active = isActive(pathname, tab.href);
            return (
              <Tooltip key={tab.href} text={tab.tooltip} position="right">
                <Link
                  href={tab.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl w-full transition-all duration-150 text-sm font-medium ${
                    active
                      ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                  }`}
                >
                  <span className={active ? "text-blue-400" : "text-slate-500"}>
                    {SVG_ICONS[tab.href]}
                  </span>
                  {tab.label}
                  {active && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400" />
                  )}
                </Link>
              </Tooltip>
            );
          })}
        </nav>
        <div className="px-5 mt-auto">
          <div className="text-xs text-slate-600">v2.0 · Cloud</div>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav
        className="bottom-nav-mobile fixed bottom-0 left-0 right-0 safe-bottom border-t border-slate-800/80 z-50 backdrop-blur-md"
        style={{ background: "rgba(8,14,26,0.92)" }}
      >
        <div className="flex items-stretch h-14">
          {tabs.map((tab) => {
            const active = isActive(pathname, tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex-1 flex flex-col items-center justify-center gap-0.5 text-xs transition-colors relative ${
                  active ? "text-blue-400" : "text-slate-500"
                }`}
              >
                {active && (
                  <span className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-0.5 rounded-full bg-blue-400" />
                )}
                <span className={active ? "text-blue-400" : "text-slate-500"}>
                  {SVG_ICONS[tab.href]}
                </span>
                <span className="font-medium">{tab.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
