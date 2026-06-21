"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";

const PIPELINE = [
  { key: "applied",   label: "Applied",   color: "#60a5fa" },
  { key: "interview", label: "Interview", color: "#a855f7" },
  { key: "offer",     label: "Offer",     color: "#22c55e" },
  { key: "rejected",  label: "Rejected",  color: "#ef4444" },
];

function getGreeting(hour: number) {
  if (hour < 5)  return "Burning the midnight oil";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  if (hour < 21) return "Good evening";
  return "Late night grind";
}

function getMotivation(stats: Stats | null, hour: number, day: number): string {
  if (!stats) return "Let's find your next opportunity.";

  if (stats.interview > 0)
    return `${stats.interview} interview${stats.interview > 1 ? "s" : ""} in progress — you're close. 🔥`;
  if (stats.offer > 0)
    return "You have an offer on the table. Time to decide. 🎉";
  if (stats.new > 10)
    return `${stats.new} fresh jobs waiting for you. Let's get through them.`;
  if (stats.applied > 0 && stats.interview === 0)
    return "Applications out there. The callbacks are coming.";
  if (stats.total === 0)
    return "Hit Scout to find your first batch of jobs.";
  if (day === 1) return "New week, new opportunities. Let's go.";
  if (day === 5) return "Friday push — apply before the weekend.";
  if (hour < 9)  return "Early bird gets the offer. Let's go.";
  return "Your next job is one application away.";
}

function getFirstName(email: string): string {
  const local = email.split("@")[0];
  // handles dheemanth.muvva26 → Dheemanth, dheemanth26 → Dheemanth
  const name = local.replace(/[^a-zA-Z]/g, " ").trim().split(" ")[0];
  return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
}

function StatCard({ value, label, color, loading }: { value: number; label: string; color: string; loading: boolean }) {
  return (
    <div className="card p-4 flex flex-col gap-1">
      <span className="text-3xl font-bold tracking-tight mono" style={{ color: loading ? "transparent" : color }}>
        {loading ? <span className="skeleton inline-block w-10 h-8 rounded" /> : value}
      </span>
      <span className="text-xs font-medium" style={{ color: "var(--text-2)" }}>{label}</span>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats]       = useState<Stats | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [scouting, setScouting] = useState(false);
  const [scoutMsg, setScoutMsg] = useState("");
  const [name, setName]         = useState("D");

  const now  = new Date();
  const hour = now.getHours();
  const day  = now.getDay(); // 0=Sun, 1=Mon…

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => {
      if (data.user?.email) setName(getFirstName(data.user.email));
      else if (data.user?.user_metadata?.full_name)
        setName(data.user.user_metadata.full_name.split(" ")[0]);
    });

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
    <div className="pt-8 pb-4 fade-up">

      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <p className="text-xs font-medium mb-1" style={{ color: "var(--text-3)" }}>
            {now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" })}
          </p>
          <h1 className="text-2xl font-bold leading-tight" style={{ color: "var(--text)" }}>
            {getGreeting(hour)}, <span className="grad-text">{name}</span> 👋
          </h1>
          <p className="text-sm mt-1.5 leading-snug max-w-xs" style={{ color: "var(--text-2)" }}>
            {loading ? <span className="skeleton inline-block h-4 w-48 rounded" /> : motivation}
          </p>
        </div>

        <button onClick={runScout} disabled={scouting}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50 shrink-0 ml-3"
          style={{ background: "var(--accent)", color: "var(--on-accent)", boxShadow: "0 0 18px var(--accent-25)" }}>
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

      {/* ── Error / Scout message ── */}
      {error && (
        error.startsWith("waking:") ? (
          <div className="rounded-xl px-4 py-3 text-sm mb-4 flex items-center gap-2"
            style={{ background: "var(--surface-2)", border: "1px solid var(--border)", color: "var(--text-2)" }}>
            <svg className="spin w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/>
            </svg>
            API warming up — retrying automatically…
          </div>
        ) : (
          <div className="rounded-xl px-4 py-3 text-sm mb-4 flex items-center gap-2"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            {error}
          </div>
        )
      )}
      {scoutMsg && (
        <div className="rounded-xl px-4 py-3 text-sm mb-4"
          style={{ background: "var(--accent-10)", border: "1px solid var(--accent-25)", color: "var(--accent-text)" }}>
          {scoutMsg}
        </div>
      )}

      {/* ── Big stats ── */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <StatCard value={stats?.total ?? 0} label="Jobs Discovered" color="var(--text)" loading={loading} />
        <StatCard value={stats?.new   ?? 0} label="Waiting for You" color="var(--accent)" loading={loading} />
      </div>

      {/* ── Pipeline row ── */}
      <div className="grid grid-cols-4 gap-2 mb-5">
        {PIPELINE.map(({ key, label, color }) => (
          <Link key={key} href="/tracker">
            <div className="card p-3 text-center card-press">
              <div className="text-xl font-bold mono" style={{ color: loading ? "transparent" : color }}>
                {loading ? <span className="skeleton inline-block w-6 h-6" /> : stats?.[key as keyof Stats] ?? 0}
              </div>
              <div className="text-[10px] mt-0.5 leading-tight" style={{ color: "var(--text-3)" }}>{label}</div>
            </div>
          </Link>
        ))}
      </div>

      {/* ── Conversion ── */}
      {stats && !loading && (
        <div className="card p-4 mb-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-3)" }}>Your Funnel</p>
            {interviewRate >= 20 && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                style={{ background: "rgba(34,197,94,0.12)", color: "#86efac" }}>
                Above avg 🎯
              </span>
            )}
          </div>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: "var(--text-2)" }}>Apply rate</span>
                <span className="font-semibold" style={{ color: "var(--text)" }}>{applyRate}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                <div className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${applyRate}%`, background: "var(--accent)" }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: "var(--text-2)" }}>Interview rate</span>
                <span className="font-semibold" style={{ color: "var(--text)" }}>{interviewRate}%</span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--border)" }}>
                <div className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${interviewRate}%`, background: "#a855f7" }} />
              </div>
            </div>
            {stats.applied === 0 && (
              <p className="text-xs italic" style={{ color: "var(--text-3)" }}>
                Start applying to see your funnel stats here.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Quick access ── */}
      <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Quick access</p>
      <div className="space-y-2">
        {[
          {
            href: "/jobs",
            label: "Browse Jobs",
            sub: stats?.new ? `${stats.new} new jobs waiting to be reviewed` : "View & filter all discovered jobs",
            icon: "💼",
          },
          {
            href: "/forge",
            label: "Forge Resume",
            sub: "Generate an ATS-optimised PDF in 30s",
            icon: "⚡",
          },
          {
            href: "/tracker",
            label: "My Applications",
            sub: stats?.applied ? `${stats.applied} applications in flight` : "Track your full pipeline",
            icon: "📋",
          },
          {
            href: "/insights",
            label: "Skill Insights",
            sub: "See what skills employers want from you",
            icon: "📊",
          },
        ].map(({ href, label, sub, icon }) => (
          <Link key={href} href={href}>
            <div className="card card-press flex items-center gap-4 px-4 py-3.5">
              <span className="text-xl w-8 text-center shrink-0">{icon}</span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm" style={{ color: "var(--text)" }}>{label}</p>
                <p className="text-xs truncate" style={{ color: "var(--text-3)" }}>{sub}</p>
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
  );
}
