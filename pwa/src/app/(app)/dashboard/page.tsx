"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";
import Link from "next/link";

const STAT_CARDS = [
  { key: "total",     label: "Jobs Found",    icon: "💼", href: "/jobs" },
  { key: "new",       label: "New Today",     icon: "🆕", href: "/jobs" },
  { key: "applied",   label: "Applied",       icon: "📤", href: "/tracker" },
  { key: "interview", label: "Interviews",    icon: "🎤", href: "/tracker" },
  { key: "offer",     label: "Offers",        icon: "🎉", href: "/tracker" },
  { key: "ghosted",   label: "Ghosted",       icon: "👻", href: "/tracker" },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scouting, setScouting] = useState(false);

  useEffect(() => {
    api.stats()
      .then(setStats)
      .catch(() => setError("Could not load stats — is the API running?"))
      .finally(() => setLoading(false));
  }, []);

  async function runScout() {
    setScouting(true);
    try {
      await api.scout();
    } catch {}
    setScouting(false);
  }

  const responseRate = stats
    ? stats.total > 0
      ? Math.round((stats.applied / stats.total) * 100)
      : 0
    : null;

  const interviewRate = stats
    ? stats.applied > 0
      ? Math.round((stats.interview / stats.applied) * 100)
      : 0
    : null;

  return (
    <div className="px-4 pt-6 pb-4 max-w-lg mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Career Scout</h1>
          <p className="text-slate-400 text-sm">
            {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}
          </p>
        </div>
        <button
          onClick={runScout}
          disabled={scouting}
          className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition disabled:opacity-50"
        >
          {scouting ? "Scanning..." : "🔍 Scout"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl bg-red-900/30 border border-red-800 text-red-300 px-4 py-3 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {STAT_CARDS.map(({ key, label, icon, href }) => (
          <Link key={key} href={href}>
            <div className="rounded-2xl border border-slate-700 p-3 text-center hover:border-blue-500 transition" style={{ background: "var(--card)" }}>
              <div className="text-xl mb-1">{icon}</div>
              <div className="text-2xl font-bold text-white">
                {loading ? "—" : stats?.[key as keyof Stats] ?? 0}
              </div>
              <div className="text-xs text-slate-400 leading-tight">{label}</div>
            </div>
          </Link>
        ))}
      </div>

      {/* Rates */}
      {stats && (
        <div className="rounded-2xl border border-slate-700 p-4 mb-4 flex justify-around" style={{ background: "var(--card)" }}>
          <div className="text-center">
            <div className="text-xl font-bold text-blue-400">{responseRate}%</div>
            <div className="text-xs text-slate-400">Apply Rate</div>
          </div>
          <div className="w-px bg-slate-700" />
          <div className="text-center">
            <div className="text-xl font-bold text-purple-400">{interviewRate}%</div>
            <div className="text-xs text-slate-400">Interview Rate</div>
          </div>
          <div className="w-px bg-slate-700" />
          <div className="text-center">
            <div className="text-xl font-bold text-yellow-400">{stats.rejected}</div>
            <div className="text-xs text-slate-400">Rejected</div>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3">
        <Link href="/jobs" className="rounded-2xl border border-slate-700 p-4 hover:border-blue-500 transition" style={{ background: "var(--card)" }}>
          <div className="text-2xl mb-1">💼</div>
          <div className="font-medium text-white text-sm">Browse Jobs</div>
          <div className="text-xs text-slate-400">New listings</div>
        </Link>
        <Link href="/forge" className="rounded-2xl border border-slate-700 p-4 hover:border-blue-500 transition" style={{ background: "var(--card)" }}>
          <div className="text-2xl mb-1">📄</div>
          <div className="font-medium text-white text-sm">Forge Resume</div>
          <div className="text-xs text-slate-400">AI-tailored PDF</div>
        </Link>
        <Link href="/tracker" className="rounded-2xl border border-slate-700 p-4 hover:border-blue-500 transition" style={{ background: "var(--card)" }}>
          <div className="text-2xl mb-1">📊</div>
          <div className="font-medium text-white text-sm">Tracker</div>
          <div className="text-xs text-slate-400">Pipeline status</div>
        </Link>
        <Link href="/insights" className="rounded-2xl border border-slate-700 p-4 hover:border-blue-500 transition" style={{ background: "var(--card)" }}>
          <div className="text-2xl mb-1">📈</div>
          <div className="font-medium text-white text-sm">Insights</div>
          <div className="text-xs text-slate-400">Gaps & signals</div>
        </Link>
      </div>
    </div>
  );
}
