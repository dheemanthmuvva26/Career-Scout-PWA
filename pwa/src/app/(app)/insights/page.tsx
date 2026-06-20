"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

type Gap = { skill: string; count: number };
type Signal = { company: string; count: number; trend: string };

export default function InsightsPage() {
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [weekly, setWeekly] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"gaps" | "signals" | "report">("gaps");

  useEffect(() => {
    Promise.allSettled([api.gaps(), api.signals(), api.insights()])
      .then(([g, s, w]) => {
        if (g.status === "fulfilled") setGaps(Array.isArray(g.value) ? g.value : []);
        if (s.status === "fulfilled") setSignals(Array.isArray(s.value) ? s.value : []);
        if (w.status === "fulfilled") setWeekly(typeof w.value === "string" ? w.value : JSON.stringify(w.value));
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-lg mx-auto px-4 pt-6">
      <h1 className="text-xl font-bold text-white mb-4">Insights</h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-5">
        {(["gaps", "signals", "report"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-xl text-sm font-medium capitalize transition ${
              tab === t ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
            }`}
          >
            {t === "gaps" ? "🎯 Gaps" : t === "signals" ? "📡 Signals" : "📋 Report"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-12 rounded-xl bg-slate-800 animate-pulse" />)}
        </div>
      ) : (
        <>
          {/* Skill Gaps */}
          {tab === "gaps" && (
            <div>
              <p className="text-slate-400 text-sm mb-4">Skills appearing in jobs you don&apos;t have listed.</p>
              {gaps.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">No gap data yet — run weekly insights first.</p>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={Math.max(200, gaps.length * 36)}>
                    <BarChart data={gaps.slice(0, 10)} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="skill" width={80} tick={{ fill: "#94a3b8", fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#f1f5f9" }}
                        formatter={(v) => [`${v} jobs`, "Count"]}
                      />
                      <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                        {gaps.slice(0, 10).map((_, i) => (
                          <Cell key={i} fill={i < 3 ? "#ef4444" : i < 6 ? "#f59e0b" : "#3b82f6"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="mt-3 space-y-2">
                    {gaps.slice(0, 5).map((g) => (
                      <div key={g.skill} className="flex items-center justify-between rounded-xl px-3 py-2 bg-slate-800">
                        <span className="text-sm text-white">{g.skill}</span>
                        <span className="text-xs text-slate-400">{g.count} jobs need this</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Hiring Signals */}
          {tab === "signals" && (
            <div>
              <p className="text-slate-400 text-sm mb-4">Companies actively posting jobs this week.</p>
              {signals.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">No signal data yet.</p>
              ) : (
                <div className="space-y-2">
                  {signals.map((s) => (
                    <div key={s.company} className="rounded-xl border border-slate-700 px-4 py-3 flex items-center justify-between" style={{ background: "var(--card)" }}>
                      <div>
                        <div className="font-medium text-white text-sm">{s.company}</div>
                        <div className="text-xs text-slate-400">{s.count} jobs this week</div>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        s.trend === "up" ? "bg-green-900/50 text-green-300" : "bg-slate-700 text-slate-300"
                      }`}>
                        {s.trend === "up" ? "↑ Hiring" : "→ Stable"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Weekly Report */}
          {tab === "report" && (
            <div>
              {!weekly ? (
                <p className="text-slate-500 text-sm text-center py-8">No weekly report yet — runs every Sunday.</p>
              ) : (
                <div className="rounded-xl border border-slate-700 px-4 py-4 text-sm text-slate-300 leading-relaxed whitespace-pre-wrap" style={{ background: "var(--card)" }}>
                  {weekly}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
