"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";
import Link from "next/link";

const PIPELINE = [
  { key: "applied",   label: "Applied",   color: "#60a5fa" },
  { key: "interview", label: "Interview", color: "#a855f7" },
  { key: "offer",     label: "Offer",     color: "#22c55e" },
  { key: "rejected",  label: "Rejected",  color: "#ef4444" },
];

function StatCard({ value, label, color, loading }: { value: number; label: string; color: string; loading: boolean }) {
  return (
    <div className="card p-4 flex flex-col gap-1">
      <span className="text-3xl font-bold tracking-tight" style={{ color: loading ? "transparent" : color }}>
        {loading ? <span className="skeleton inline-block w-10 h-8 rounded" /> : value}
      </span>
      <span className="text-xs font-medium" style={{ color: "var(--text-2)" }}>{label}</span>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scouting, setScouting] = useState(false);
  const [scoutMsg, setScoutMsg] = useState("");

  useEffect(() => {
    api.stats()
      .then(setStats)
      .catch(() => setError("API offline — Render may be waking up (~50s)"))
      .finally(() => setLoading(false));
  }, []);

  async function runScout() {
    setScouting(true);
    setScoutMsg("");
    try {
      await api.scout();
      setScoutMsg("Scan started! Check back in a few minutes.");
    } catch {
      setScoutMsg("Failed to start scan.");
    }
    setScouting(false);
  }

  const applyRate = stats?.total ? Math.round((stats.applied / stats.total) * 100) : 0;
  const interviewRate = stats?.applied ? Math.round((stats.interview / stats.applied) * 100) : 0;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="pt-8 pb-4 fade-up">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="text-sm font-medium mb-0.5" style={{ color: "var(--text-3)" }}>{greeting}</p>
          <h1 style={{ color: "var(--text)" }}>Career Scout</h1>
          <p className="text-xs mt-1" style={{ color: "var(--text-3)" }}>
            {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short", year: "numeric" })}
          </p>
        </div>
        <button
          onClick={runScout}
          disabled={scouting}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
          style={{ background: "var(--accent)", color: "#fff" }}
        >
          {scouting ? (
            <svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="w-4 h-4">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35" strokeLinecap="round"/>
            </svg>
          )}
          {scouting ? "Scanning…" : "Scout"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl px-4 py-3 text-sm mb-5 flex items-center gap-2"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          {error}
        </div>
      )}

      {scoutMsg && (
        <div className="rounded-xl px-4 py-3 text-sm mb-5"
          style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.25)", color: "#a5b4fc" }}>
          {scoutMsg}
        </div>
      )}

      {/* Top stats — 2 big cards */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <StatCard value={stats?.total ?? 0} label="Jobs Discovered" color="var(--text)" loading={loading} />
        <StatCard value={stats?.new ?? 0} label="New Unreviewed" color="var(--accent)" loading={loading} />
      </div>

      {/* Pipeline row */}
      <div className="grid grid-cols-4 gap-2 mb-5">
        {PIPELINE.map(({ key, label, color }) => (
          <Link key={key} href="/tracker">
            <div className="card p-3 text-center card-press">
              <div className="text-xl font-bold" style={{ color: loading ? "transparent" : color }}>
                {loading ? <span className="skeleton inline-block w-6 h-6" /> : stats?.[key as keyof Stats] ?? 0}
              </div>
              <div className="text-[10px] mt-0.5 leading-tight" style={{ color: "var(--text-3)" }}>{label}</div>
            </div>
          </Link>
        ))}
      </div>

      {/* Conversion rates */}
      {stats && !loading && (
        <div className="card p-4 mb-5">
          <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Conversion</p>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: "var(--text-2)" }}>Apply rate</span>
                <span className="font-semibold" style={{ color: "var(--text)" }}>{applyRate}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${applyRate}%`, background: "var(--accent)" }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: "var(--text-2)" }}>Interview rate</span>
                <span className="font-semibold" style={{ color: "var(--text)" }}>{interviewRate}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${interviewRate}%`, background: "#a855f7" }} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Quick access</p>
      <div className="space-y-2">
        {[
          { href: "/jobs",     label: "Browse Jobs",    sub: "View & filter all discovered jobs",    icon: "💼" },
          { href: "/forge",    label: "Forge Resume",   sub: "Generate ATS-optimised PDF",           icon: "⚡" },
          { href: "/tracker",  label: "Tracker",        sub: "Full application pipeline",            icon: "📋" },
          { href: "/insights", label: "Insights",       sub: "Skill gaps & hiring signals",          icon: "📊" },
        ].map(({ href, label, sub, icon }) => (
          <Link key={href} href={href}>
            <div className="card card-press flex items-center gap-4 px-4 py-3.5">
              <span className="text-xl w-8 text-center shrink-0">{icon}</span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm" style={{ color: "var(--text)" }}>{label}</p>
                <p className="text-xs truncate" style={{ color: "var(--text-3)" }}>{sub}</p>
              </div>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4 shrink-0" style={{ color: "var(--text-3)" }}>
                <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
