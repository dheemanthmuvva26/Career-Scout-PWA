"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { haptics } from "@/lib/haptics";
import { useViewMode } from "@/lib/viewMode";

const tabs = [
  {
    href: "/dashboard", label: "Home",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/>
        <path d="M9 21V12h6v9" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/jobs", label: "Jobs",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <rect x="2" y="7" width="20" height="14" rx="2.5"/>
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" strokeLinecap="round"/>
        <line x1="12" y1="12" x2="12" y2="16" strokeLinecap="round"/>
        <line x1="10" y1="14" x2="14" y2="14" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/tracker", label: "Tracker",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <rect x="3" y="3" width="18" height="18" rx="2.5"/>
        <path d="M3 9h18M9 21V9" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/forge", label: "Forge",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: "/settings", label: "Settings",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <circle cx="12" cy="12" r="2.8"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" strokeLinecap="round"/>
      </svg>
    ),
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href || pathname === "/";
  return pathname.startsWith(href);
}

export default function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();
  const { toggle } = useViewMode();

  function handleNav(e: React.MouseEvent, href: string) {
    if (isActive(pathname, href)) return;
    e.preventDefault();
    haptics.light();
    const go = () => router.replace(href);
    if ("startViewTransition" in document) {
      (document as Document & { startViewTransition: (cb: () => void) => void })
        .startViewTransition(go);
    } else {
      go();
    }
  }

  return (
    <aside
      className="flex flex-col fixed left-0 top-0 h-full z-50"
      style={{
        width: 216,
        background: "rgba(4,11,18,0.96)",
        borderRight: "1px solid rgba(255,255,255,0.055)",
        backdropFilter: "blur(24px) saturate(180%)",
        WebkitBackdropFilter: "blur(24px) saturate(180%)",
      }}
    >
      {/* Branding */}
      <div className="px-5 pt-7 pb-5 mb-1">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: "var(--accent)", boxShadow: "0 0 14px rgba(0,229,255,0.4)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" className="w-4 h-4">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-bold leading-tight" style={{ color: "var(--text)", letterSpacing: "-0.02em" }}>Career Scout</p>
            <p className="text-[10px] font-medium" style={{ color: "var(--text-3)" }}>AI Job Tracker</p>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-4 mb-3" style={{ height: 1, background: "rgba(255,255,255,0.05)" }} />

      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-0.5">
        {tabs.map((tab) => {
          const active = isActive(pathname, tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              onClick={(e) => handleNav(e, tab.href)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all select-none group"
              style={{
                color: active ? "var(--accent)" : "var(--text-3)",
                background: active ? "rgba(0,229,255,0.07)" : "transparent",
                border: active ? "1px solid rgba(0,229,255,0.11)" : "1px solid transparent",
                fontWeight: 600,
                fontSize: 13,
              }}
            >
              <span style={{
                filter: active ? "drop-shadow(0 0 7px rgba(0,229,255,0.65))" : "none",
                transition: "filter 0.15s ease",
                display: "flex",
                flexShrink: 0,
              }}>
                {tab.icon(active)}
              </span>
              <span style={{ transition: "color 0.15s ease" }}>{tab.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="mx-4 mb-3" style={{ height: 1, background: "rgba(255,255,255,0.05)" }} />
      <div className="px-5 pb-6">
        <p className="text-xs font-semibold" style={{ color: "var(--text-2)" }}>Dheemanth M.</p>
        <p className="text-[10px] mt-0.5 mb-3" style={{ color: "var(--text-3)" }}>B.Tech CSE · AI & Data Analytics</p>
        <button
          onClick={toggle}
          className="flex items-center gap-1.5 transition-all active:scale-95"
          style={{
            padding: "5px 10px",
            borderRadius: 12,
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)",
            color: "var(--text-3)",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: "0.04em",
          }}
        >
          <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="5" y="2" width="14" height="20" rx="2"/>
            <line x1="12" y1="18" x2="12" y2="18.01" strokeLinecap="round" strokeWidth="2.5"/>
          </svg>
          Mobile View
        </button>
      </div>
    </aside>
  );
}
