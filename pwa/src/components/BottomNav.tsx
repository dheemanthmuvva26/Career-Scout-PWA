"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  {
    href: "/dashboard", label: "Home",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/>
        <path d="M9 21V12h6v9" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/jobs", label: "Jobs",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <rect x="2" y="7" width="20" height="14" rx="2"/>
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" strokeLinecap="round"/>
        <line x1="12" y1="12" x2="12" y2="16" strokeLinecap="round"/>
        <line x1="10" y1="14" x2="14" y2="14" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/tracker", label: "Track",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <rect x="3" y="3" width="18" height="18" rx="2"/>
        <path d="M3 9h18M9 21V9" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/forge", label: "Forge",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/settings", label: "More",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-5 h-5" fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.8">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" strokeLinecap="round"/>
      </svg>
    ),
  },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href || pathname === "/";
  return pathname.startsWith(href);
}

export default function BottomNav() {
  const pathname = usePathname();

  return (
    /* Floating pill nav */
    <nav
      className="fixed z-50"
      style={{
        bottom: "max(16px, env(safe-area-inset-bottom, 16px))",
        left: "50%",
        transform: "translateX(-50%)",
        width: "calc(100% - 32px)",
        maxWidth: "440px",
        background: "rgba(5,12,20,0.72)",
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
        borderRadius: "22px",
        border: "1px solid rgba(0,229,255,0.10)",
        boxShadow: "0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,229,255,0.04) inset, 0 1px 0 rgba(255,255,255,0.04) inset",
      }}
    >
      <div className="flex items-stretch h-[58px] px-1">
        {tabs.map((tab) => {
          const active = isActive(pathname, tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className="flex-1 flex flex-col items-center justify-center gap-1 relative transition-all active:opacity-60"
              style={{
                color: active ? "var(--accent)" : "var(--text-3)",
              }}
            >
              {/* Active pill background */}
              {active && (
                <span
                  className="absolute inset-1 rounded-xl"
                  style={{
                    background: "rgba(0,229,255,0.08)",
                    boxShadow: "inset 0 0 0 1px rgba(0,229,255,0.12)",
                  }}
                />
              )}
              {/* Icon with glow */}
              <span
                className="relative z-10"
                style={{
                  filter: active ? "drop-shadow(0 0 6px rgba(0,229,255,0.7))" : "none",
                  transition: "filter 0.2s",
                }}
              >
                {tab.icon(active)}
              </span>
              <span
                className="relative z-10 text-[9px] font-semibold tracking-wider uppercase"
                style={{ letterSpacing: "0.06em" }}
              >
                {tab.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
