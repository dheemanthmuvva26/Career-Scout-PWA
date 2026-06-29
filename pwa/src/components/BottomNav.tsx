"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { haptics } from "@/lib/haptics";

const tabs = [
  {
    href: "/dashboard", label: "Home",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[22px] h-[22px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.7">
        <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z"/>
        <path d="M9 21V12h6v9" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/jobs", label: "Jobs",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[22px] h-[22px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.7">
        <rect x="2" y="7" width="20" height="14" rx="2.5"/>
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" strokeLinecap="round"/>
        <line x1="12" y1="12" x2="12" y2="16" strokeLinecap="round"/>
        <line x1="10" y1="14" x2="14" y2="14" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/tracker", label: "Track",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[22px] h-[22px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.7">
        <rect x="3" y="3" width="18" height="18" rx="2.5"/>
        <path d="M3 9h18M9 21V9" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/forge", label: "Forge",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[22px] h-[22px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.7">
        <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: "/settings", label: "More",
    icon: (a: boolean) => (
      <svg viewBox="0 0 24 24" className="w-[22px] h-[22px]"
        fill={a ? "currentColor" : "none"} stroke={a ? "none" : "currentColor"} strokeWidth="1.7">
        <circle cx="12" cy="12" r="2.8"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
          strokeLinecap="round"/>
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
  const router   = useRouter();

  function handleNav(e: React.MouseEvent, href: string) {
    if (isActive(pathname, href)) return;
    haptics.light();
    // Use View Transitions API if supported
    if ("startViewTransition" in document) {
      e.preventDefault();
      (document as Document & { startViewTransition: (cb: () => void) => void })
        .startViewTransition(() => router.push(href));
    }
    // else: let the Link handle it normally
  }

  return (
    <nav
      className="fixed z-50"
      style={{
        bottom: "max(16px, env(safe-area-inset-bottom, 16px))",
        left: "50%",
        transform: "translateX(-50%)",
        width: "calc(100% - 28px)",
        maxWidth: "450px",
      }}
    >
      {/* Glass pill */}
      <div style={{
        background: "rgba(4,11,18,0.78)",
        backdropFilter: "blur(24px) saturate(190%)",
        WebkitBackdropFilter: "blur(24px) saturate(190%)",
        borderRadius: "24px",
        border: "1px solid rgba(255,255,255,0.06)",
        borderTopColor: "rgba(255,255,255,0.09)",
        boxShadow:
          "0 1px 0 rgba(255,255,255,0.04) inset," +
          "0 -1px 0 rgba(0,0,0,0.4) inset," +
          "0 12px 48px rgba(0,0,0,0.6)," +
          "0 0 0 0.5px rgba(0,0,0,0.8)",
      }}>
        <div className="flex items-stretch h-[60px] px-1">
          {tabs.map((tab) => {
            const active = isActive(pathname, tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                onClick={(e) => handleNav(e, tab.href)}
                className="flex-1 flex flex-col items-center justify-center gap-[3px] relative select-none"
                style={{
                  color: active ? "var(--accent)" : "var(--text-3)",
                  WebkitTapHighlightColor: "transparent",
                  transition: "color 0.15s ease",
                }}
              >
                {/* Active background bubble */}
                {active && (
                  <span
                    className="absolute inset-[4px] rounded-[18px]"
                    style={{
                      background: "rgba(0,229,255,0.07)",
                      boxShadow: "inset 0 0 0 1px rgba(0,229,255,0.10)",
                    }}
                  />
                )}

                {/* Icon */}
                <span
                  className="relative z-10"
                  style={{
                    filter: active
                      ? "drop-shadow(0 0 8px rgba(0,229,255,0.65))"
                      : "none",
                    transition: "filter 0.2s ease, transform 0.15s cubic-bezier(0.34,1.56,0.64,1)",
                    transform: active ? "scale(1.08)" : "scale(1)",
                    display: "flex",
                  }}
                >
                  {tab.icon(active)}
                </span>

                {/* Label */}
                <span
                  className="relative z-10 font-semibold"
                  style={{
                    fontSize: "9px",
                    letterSpacing: "0.07em",
                    textTransform: "uppercase",
                    opacity: active ? 1 : 0.5,
                    transition: "opacity 0.15s ease",
                  }}
                >
                  {tab.label}
                </span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
