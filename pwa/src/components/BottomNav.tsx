"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/dashboard", label: "Home",     icon: "🏠" },
  { href: "/jobs",      label: "Jobs",     icon: "💼" },
  { href: "/tracker",   label: "Track",    icon: "📊" },
  { href: "/forge",     label: "Forge",    icon: "📄" },
  { href: "/insights",  label: "Insights", icon: "📈" },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 safe-bottom border-t border-slate-800 z-50"
      style={{ background: "var(--card)" }}
    >
      <div className="flex items-stretch">
        {tabs.map((tab) => {
          const active = pathname === tab.href || (tab.href !== "/dashboard" && pathname.startsWith(tab.href));
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex-1 flex flex-col items-center justify-center py-2 text-xs transition-colors ${
                active ? "text-blue-400" : "text-slate-500"
              }`}
            >
              <span className="text-xl mb-0.5">{tab.icon}</span>
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
