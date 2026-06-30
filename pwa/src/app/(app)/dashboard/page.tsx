"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Stats } from "@/lib/api";
import Link from "next/link";
import PullToRefresh from "@/components/PullToRefresh";

const USER_NAME = "Dheemanth";

const PIPELINE = [
  { key: "applied",   label: "Applied",   color: "#60a5fa", glow: "rgba(96,165,250,0.20)" },
  { key: "interview", label: "Interview", color: "#a855f7", glow: "rgba(168,85,247,0.20)" },
  { key: "offer",     label: "Offer",     color: "#22c55e", glow: "rgba(34,197,94,0.20)"  },
  { key: "rejected",  label: "Rejected",  color: "#ef4444", glow: "rgba(239,68,68,0.15)"  },
];

function getGreeting(hour: number) {
  if (hour < 5)  return "Burning midnight oil";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  if (hour < 21) return "Good evening";
  return "Late night grind";
}

function getMotivation(stats: Stats | null, hour: number, day: number): string {
  if (!stats) return "Let's find your next opportunity.";
  if (stats.offer > 0)     return "You have an offer on the table. Time to decide.";
  if (stats.interview > 0) return `${stats.interview} interview${stats.interview > 1 ? "s" : ""} in progress — you're close.`;
  if (stats.new > 10)      return `${stats.new} fresh jobs waiting. Let's get through them.`;
  if (stats.applied > 0)   return "Applications out there. The callbacks are coming.";
  if (stats.total === 0)   return "Hit Scout to find your first batch of jobs.";
  if (day === 1)  return "New week, new opportunities. Let's go.";
  if (day === 5)  return "Friday push — apply before the weekend.";
  if (hour < 9)   return "Early bird gets the offer. Let's go.";
  return "Your next job is one application away.";
}

export default function DashboardPage() {
  const [stats, setStats]       = useState<Stats | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [scouting, setScouting] = useState(false);
  const [scoutMsg, setScoutMsg] = useState("");

  const now  = new Date();
  const hour = now.getHours();
  const day  = now.getDay();

  useEffect(() => {
    let attempts = 0;
    function loadStats() {
      api.stats()
        .then((s) => { setStats(s); setError(""); setLoading(false); })
        .catch(() => {
          attempts++;
          if (attempts < 4) {
            setError(`waking:${attempts}`);
            setLoading(false);
            setTimeout(loadStats, 20000);
          } else {
            setError("API offline — pull down to refresh");
            setLoading(false);
          }
        });
    }
    loadStats();
  }, []);

  const refresh = useCallback(async () => {
    try {
      const s = await api.stats();
      setStats(s);
      setError("");
    } catch {
      setError("API offline — pull down to refresh");
    }
  }, []);

  async function runScout() {
    setScouting(true); setScoutMsg("");
    try {
      await api.scout();
      setScoutMsg("Scan started — new jobs will appear shortly.");
    } catch {
      setScoutMsg("Failed to start scan. API may still be waking up.");
    }
    setScouting(false);
  }

  const applyRate     = stats?.total   ? Math.round((stats.applied   / stats.total)   * 100) : 0;
  const interviewRate = stats?.applied ? Math.round((stats.interview / stats.applied) * 100) : 0;
  const motivation    = getMotivation(stats, hour, day);

  return (
    <PullToRefresh onRefresh={refresh}>
    <div className="pt-6 pb-4 fade-up">

      {/* ── Hero glass card ── */}
      <div className="rounded-2xl mb-5 px-5 py-5 relative overflow-hidden"
        style={{
          background: "rgba(5,15,21,0.60)",
          border: "1px solid rgba(0,229,255,0.12)",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(0,229,255,0.08)",
        }}>
        {/* Subtle inner gradient */}
        <div className="absolute inset-0 pointer-events-none" style={{
          background: "radial-gradient(ellipse 80% 60% at 0% 0%, rgba(0,229,255,0.05) 0%, transparent 60%)",
          borderRadius: "inherit",
        }}/>

        <div className="flex items-start justify-between relative">
          <div className="flex-1">
            <p className="text-xs font-mono mb-2" style={{ color: "var(--text-3)", letterSpacing: "0.08em" }}>
              {now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" }).toUpperCase()}
            </p>
            <p className="text-sm mb-0.5" style={{ color: "var(--text-2)" }}>{getGreeting(hour)},</p>
            <h1 className="text-3xl font-bold leading-tight mb-2 grad-text">{USER_NAME}</h1>
            <p className="text-sm leading-relaxed max-w-[220px]" style={{ color: "var(--text-2)" }}>
              {loading ? <span className="skeleton inline-block h-4 w-44 rounded" /> : motivation}
            </p>
          </div>

          {/* Scout button */}
          <button onClick={runScout} disabled={scouting}
            className="flex flex-col items-center gap-1.5 px-4 py-3 rounded-xl text-xs font-bold transition-all active:scale-95 disabled:opacity-50 shrink-0 ml-3"
            style={{
              background: scouting ? "var(--accent-10)" : "var(--accent)",
              color: scouting ? "var(--accent)" : "var(--on-accent)",
              border: scouting ? "1px solid var(--accent-30)" : "none",
              boxShadow: scouting ? "none" : "0 0 20px var(--accent-30), 0 4px 12px rgba(0,0,0,0.3)",
              letterSpacing: "0.04em",
            }}>
            {scouting ? (
              <svg className="spin w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/>
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" className="w-5 h-5">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35" strokeLinecap="round"/>
              </svg>
            )}
            {scouting ? "Scanning" : "Scout"}
          </button>
        </div>

        {/* AI active status */}
        <div className="flex items-center gap-2 mt-4 pt-4 relative"
          style={{ borderTop: "1px solid rgba(0,229,255,0.08)" }}>
          <span className="w-2 h-2 rounded-full pulse-glow shrink-0" style={{ background: "var(--accent)" }}/>
          <span className="text-xs font-mono" style={{ color: "var(--text-3)", letterSpacing: "0.06em" }}>
            AI SCOUT ACTIVE
          </span>
          <span className="ml-auto text-xs font-mono" style={{ color: "var(--text-3)" }}>
            {stats?.total ?? "—"} jobs tracked
          </span>
        </div>
      </div>

      {/* ── Messages ── */}
      {error && !error.startsWith("waking:") && (
        <div className="rounded-xl px-4 py-3 text-sm mb-4 flex items-center gap-2"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          {error}
        </div>
      )}
      {error.startsWith("waking:") && (
        <div className="rounded-xl px-4 py-3 text-sm mb-4 flex items-center gap-2"
          style={{ background: "var(--accent-05)", border: "1px solid var(--accent-15)", color: "var(--text-2)" }}>
          <svg className="spin w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/>
          </svg>
          Server warming up — retrying automatically…
        </div>
      )}
      {scoutMsg && (
        <div className="rounded-xl px-4 py-3 text-sm mb-4"
          style={{ background: "var(--accent-05)", border: "1px solid var(--accent-20)", color: "var(--accent-text)" }}>
          {scoutMsg}
        </div>
      )}

      {/* ── Two big stats ── */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* Discovered — cyan */}
        <div className="rounded-2xl p-4 flex flex-col gap-1.5"
          style={{
            background: "rgba(5,15,21,0.85)",
            border: "1px solid rgba(0,229,255,0.16)",
            boxShadow: "0 0 20px rgba(0,229,255,0.04)",
          }}>
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-3)" }}>Discovered</span>
          <span className="text-4xl font-bold mono" style={{ color: loading ? "transparent" : "var(--accent)" }}>
            {loading ? <span className="skeleton inline-block w-12 h-9 rounded" /> : stats?.total ?? 0}
          </span>
          <span className="text-xs" style={{ color: "var(--text-3)" }}>total jobs</span>
        </div>
        {/* Waiting — violet */}
        <div className="rounded-2xl p-4 flex flex-col gap-1.5"
          style={{
            background: "rgba(5,15,21,0.85)",
            border: "1px solid rgba(139,92,246,0.20)",
            boxShadow: "0 0 20px rgba(139,92,246,0.05)",
          }}>
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--text-3)" }}>Waiting</span>
          <span className="text-4xl font-bold mono" style={{ color: loading ? "transparent" : "var(--violet)" }}>
            {loading ? <span className="skeleton inline-block w-12 h-9 rounded" /> : stats?.new ?? 0}
          </span>
          <span className="text-xs" style={{ color: "var(--text-3)" }}>new for you</span>
        </div>
      </div>

      {/* ── Pipeline tiles ── */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {PIPELINE.map(({ key, label, color, glow }) => (
          <Link key={key} href="/tracker">
            <div className="rounded-xl p-3 text-center card-press"
              style={{
                background: "rgba(5,15,21,0.85)",
                border: `1px solid ${glow}`,
              }}>
              <div className="text-xl font-bold mono leading-none mb-1" style={{ color: loading ? "transparent" : color }}>
                {loading ? <span className="skeleton inline-block w-6 h-6" /> : stats?.[key as keyof Stats] ?? 0}
              </div>
              <div className="text-[9px] font-semibold uppercase tracking-wider leading-tight" style={{ color: "var(--text-3)" }}>
                {label}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* ── Funnel ── */}
      {stats && !loading && (stats.applied > 0 || stats.total > 0) && (
        <div className="rounded-2xl p-4 mb-4"
          style={{
            background: "rgba(5,15,21,0.85)",
            border: "1px solid var(--border)",
          }}>
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-3)" }}>Your Funnel</p>
            {interviewRate >= 20 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ background: "rgba(34,197,94,0.10)", color: "#86efac", border: "1px solid rgba(34,197,94,0.2)" }}>
                Above avg
              </span>
            )}
          </div>
          <div className="space-y-4">
            {[
              { label: "Apply rate",     pct: applyRate,     color: "var(--accent)" },
              { label: "Interview rate", pct: interviewRate, color: "var(--purple)" },
            ].map(({ label, pct, color }) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1.5">
                  <span style={{ color: "var(--text-2)" }}>{label}</span>
                  <span className="font-bold mono" style={{ color }}>{pct}%</span>
                </div>
                <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                  <div className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${pct}%`,
                      background: `linear-gradient(90deg, ${color}, ${color}dd)`,
                      boxShadow: `0 0 8px ${color}60`,
                    }} />
                </div>
              </div>
            ))}
            {stats.applied === 0 && (
              <p className="text-xs italic" style={{ color: "var(--text-3)" }}>
                Start applying to see your funnel stats here.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Quick access ── */}
      <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Quick access</p>
      <div className="space-y-2">
        {[
          {
            href: "/jobs",
            label: "Browse Jobs",
            sub: stats?.new ? `${stats.new} new jobs waiting` : "View & filter all discovered jobs",
            color: "var(--accent)",
            bg: "var(--accent-05)",
            border: "var(--accent-10)",
            svg: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" strokeLinecap="round"/></svg>,
          },
          {
            href: "/forge",
            label: "Forge Resume",
            sub: "ATS-optimised PDF tailored to a job",
            color: "var(--violet)",
            bg: "var(--violet-05)",
            border: "var(--violet-10)",
            svg: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5"><path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/></svg>,
          },
          {
            href: "/tracker",
            label: "My Applications",
            sub: stats?.applied ? `${stats.applied} in flight` : "Track your full pipeline",
            color: "#60a5fa",
            bg: "rgba(96,165,250,0.05)",
            border: "rgba(96,165,250,0.12)",
            svg: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9" strokeLinecap="round"/></svg>,
          },
          {
            href: "/insights",
            label: "Skill Insights",
            sub: "See what employers want from you",
            color: "#a855f7",
            bg: "rgba(168,85,247,0.05)",
            border: "rgba(168,85,247,0.12)",
            svg: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="w-5 h-5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
          },
        ].map(({ href, label, sub, color, bg, border, svg }) => (
          <Link key={href} href={href}>
            <div className="flex items-center gap-3.5 px-4 py-3.5 rounded-2xl card-press transition-all"
              style={{
                background: bg,
                border: `1px solid ${border}`,
              }}>
              <span className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: `${color}18`, color }}>
                {svg}
              </span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm" style={{ color: "var(--text)" }}>{label}</p>
                <p className="text-xs truncate mt-0.5" style={{ color: "var(--text-3)" }}>{sub}</p>
              </div>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className="w-4 h-4 shrink-0" style={{ color: "var(--text-3)" }}>
                <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </Link>
        ))}
      </div>
    </div>
    </PullToRefresh>
  );
}
