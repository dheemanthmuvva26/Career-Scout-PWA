"use client";

import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";
import Link from "next/link";
import Tooltip from "@/components/Tooltip";

const STAT_CARDS = [
  { key: "total",     label: "Jobs Found",  accent: "accent-blue",   tooltip: "Total jobs discovered by Career Scout",              href: "/jobs" },
  { key: "new",       label: "New",         accent: "accent-sky",    tooltip: "Unreviewed jobs added in the last 24 hours",         href: "/jobs" },
  { key: "applied",   label: "Applied",     accent: "accent-green",  tooltip: "Jobs you've submitted an application for",           href: "/tracker" },
  { key: "interview", label: "Interviews",  accent: "accent-purple", tooltip: "Applications that progressed to an interview stage", href: "/tracker" },
  { key: "offer",     label: "Offers",      accent: "accent-amber",  tooltip: "Applications that resulted in a job offer",          href: "/tracker" },
  { key: "ghosted",   label: "Ghosted",     accent: "accent-rose",   tooltip: "No response received after 14+ days",               href: "/tracker" },
];

const QUICK_ACTIONS = [
  { href: "/jobs",     icon: <JobsIcon />,    label: "Browse Jobs",    sub: "New listings",      tooltip: "View and filter all discovered jobs" },
  { href: "/forge",    icon: <ForgeIcon />,   label: "Forge Resume",   sub: "AI-tailored PDF",   tooltip: "Generate an ATS-optimised resume for any job" },
  { href: "/tracker",  icon: <TrackIcon />,   label: "Tracker",        sub: "Pipeline status",   tooltip: "Track all your applications in one place" },
  { href: "/insights", icon: <InsightIcon />, label: "Insights",       sub: "Gaps & signals",    tooltip: "Skill gap analysis and hiring signals" },
];

function JobsIcon()    { return <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6"><path d="M20 6h-2.18c.07-.44.18-.86.18-1a3 3 0 0 0-6 0c0 .14.11.56.18 1H10C8.9 6 8 6.9 8 8v12c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-7-1c0-.55.45-1 1-1s1 .45 1 1-.45 1-1 1-1-.45-1-1zm2 14h-2v-2h2v2zm3.5-6l-4.5 4.5-2-2 1.06-1.06L12 17.44l3.44-3.44L16.5 15z"/></svg>; }
function ForgeIcon()   { return <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.89 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>; }
function TrackIcon()   { return <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>; }
function InsightIcon() { return <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>; }

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scouting, setScouting] = useState(false);
  const [scoutDone, setScoutDone] = useState(false);

  useEffect(() => {
    api.stats()
      .then(setStats)
      .catch(() => setError("Could not reach API — Render may be waking up (takes ~50s)"))
      .finally(() => setLoading(false));
  }, []);

  async function runScout() {
    setScouting(true);
    setScoutDone(false);
    try { await api.scout(); } catch {}
    setScouting(false);
    setScoutDone(true);
    setTimeout(() => setScoutDone(false), 3000);
  }

  const applyRate = stats?.total ? Math.round((stats.applied / stats.total) * 100) : 0;
  const interviewRate = stats?.applied ? Math.round((stats.interview / stats.applied) * 100) : 0;
  const offerRate = stats?.interview ? Math.round((stats.offer / stats.interview) * 100) : 0;

  return (
    <div className="pt-6 pb-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-7 px-1">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
          </p>
        </div>
        <Tooltip text={scouting ? "Scanning job boards..." : "Trigger a fresh job scan across all sources"} position="left">
          <button
            onClick={runScout}
            disabled={scouting}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              scoutDone
                ? "bg-green-600 text-white"
                : "bg-blue-600 hover:bg-blue-500 active:scale-95 text-white disabled:opacity-60"
            }`}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className={`w-4 h-4 ${scouting ? "animate-spin" : ""}`}>
              {scouting
                ? <path d="M12 4V2A10 10 0 0 0 2 12h2a8 8 0 0 1 8-8z"/>
                : <path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
              }
            </svg>
            {scoutDone ? "Done!" : scouting ? "Scanning…" : "Scout"}
          </button>
        </Tooltip>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-800/50 bg-amber-900/20 text-amber-300 px-4 py-3 text-sm mb-5 flex items-start gap-2">
          <span className="mt-0.5">⚠</span>
          <span>{error}</span>
        </div>
      )}

      {/* Stat grid */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2.5 mb-5">
        {STAT_CARDS.map(({ key, label, accent, tooltip, href }) => (
          <Tooltip key={key} text={tooltip} position="bottom">
            <Link href={href} className="block w-full">
              <div className={`card-glow rounded-2xl p-3.5 text-center hover:bg-slate-800/60 transition cursor-pointer ${accent}`}>
                <div className="text-2xl font-bold text-white mt-1">
                  {loading ? <span className="skeleton inline-block w-6 h-6 rounded" /> : stats?.[key as keyof Stats] ?? 0}
                </div>
                <div className="text-xs text-slate-400 mt-1 leading-tight font-medium">{label}</div>
              </div>
            </Link>
          </Tooltip>
        ))}
      </div>

      {/* Rates bar */}
      {stats && !loading && (
        <div className="card-glow rounded-2xl px-5 py-4 mb-5">
          <div className="text-xs text-slate-500 font-medium mb-3 uppercase tracking-wider">Conversion funnel</div>
          <div className="grid grid-cols-3 gap-4">
            <Tooltip text="Percentage of discovered jobs you applied to" position="top">
              <div className="text-center cursor-default">
                <div className="text-xl font-bold grad-blue">{applyRate}%</div>
                <div className="text-xs text-slate-500 mt-0.5">Apply rate</div>
              </div>
            </Tooltip>
            <Tooltip text="Percentage of applications that got an interview" position="top">
              <div className="text-center cursor-default">
                <div className="text-xl font-bold grad-purple">{interviewRate}%</div>
                <div className="text-xs text-slate-500 mt-0.5">Interview rate</div>
              </div>
            </Tooltip>
            <Tooltip text="Percentage of interviews that resulted in an offer" position="top">
              <div className="text-center cursor-default">
                <div className="text-xl font-bold grad-green">{offerRate}%</div>
                <div className="text-xs text-slate-500 mt-0.5">Offer rate</div>
              </div>
            </Tooltip>
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="text-xs text-slate-500 font-medium mb-2.5 uppercase tracking-wider">Quick access</div>
      <div className="grid grid-cols-2 gap-2.5">
        {QUICK_ACTIONS.map(({ href, icon, label, sub, tooltip }) => (
          <Tooltip key={href} text={tooltip} position="top">
            <Link
              href={href}
              className="card-glow rounded-2xl p-4 hover:bg-slate-800/60 transition cursor-pointer block w-full"
            >
              <div className="text-blue-400 mb-2">{icon}</div>
              <div className="font-semibold text-white text-sm">{label}</div>
              <div className="text-xs text-slate-500 mt-0.5">{sub}</div>
            </Link>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
