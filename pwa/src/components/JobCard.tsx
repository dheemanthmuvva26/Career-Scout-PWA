"use client";

import { useState } from "react";
import { api, type Job } from "@/lib/api";
import Tooltip from "./Tooltip";

const URGENCY: Record<string, { dot: string; label: string; color: string }> = {
  hot:    { dot: "●", label: "Hot — posted within 24h",       color: "text-red-400" },
  active: { dot: "●", label: "Active — posted within 7 days", color: "text-yellow-400" },
  aging:  { dot: "●", label: "Aging — over 7 days old",       color: "text-slate-400" },
  stale:  { dot: "●", label: "Stale — likely expired",        color: "text-slate-600" },
};

const scoreColor = (s: number) =>
  s >= 4 ? "text-green-400" : s >= 3 ? "text-yellow-400" : "text-red-400";

const scoreLabel = (s: number) =>
  s >= 4 ? "Strong match" : s >= 3 ? "Decent match" : "Weak match";

type Props = { job: Job; onUpdate?: (id: string, changes: Partial<Job>) => void; compact?: boolean; };

export default function JobCard({ job, onUpdate, compact = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const sid = job.short_id || job.id;
  const tags: string[] = Array.isArray(job.tags_matched) ? job.tags_matched : [];
  const detail = (job.score_detail as Record<string, unknown>) || {};
  const missing: string[] = Array.isArray((detail as Record<string, string[]>).missing_skills)
    ? (detail as Record<string, string[]>).missing_skills.slice(0, 3)
    : [];
  const urgencyInfo = URGENCY[job.urgency] || URGENCY.aging;

  async function doAction(action: string) {
    setBusy(action);
    try {
      if (action === "apply")     { await api.apply(sid);                     onUpdate?.(job.id, { status: "applied" }); }
      if (action === "skip")      { await api.setStatus(sid, "skipped");       onUpdate?.(job.id, { status: "skipped" }); }
      if (action === "interview") { await api.setOutcome(sid, "interview");    onUpdate?.(job.id, { outcome: "interview" }); }
      if (action === "rejected")  { await api.setOutcome(sid, "rejected");     onUpdate?.(job.id, { outcome: "rejected" }); }
      if (action === "ghosted")   { await api.setOutcome(sid, "ghosted");      onUpdate?.(job.id, { status: "ghosted" }); }
      setDone(action);
      setTimeout(() => setDone(null), 1500);
    } catch (e) { console.error(e); }
    setBusy(null);
  }

  async function saveNote() {
    if (!note.trim()) return;
    setBusy("note");
    await api.note(sid, note.trim());
    setBusy(null);
    setNote("");
    setAddingNote(false);
  }

  return (
    <div className="card-glow rounded-2xl p-4 mb-3 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-xs mb-1">
            <Tooltip text={urgencyInfo.label} position="top">
              <span className={`cursor-default ${urgencyInfo.color} text-[10px]`}>{urgencyInfo.dot}</span>
            </Tooltip>
            <span className="text-slate-300 font-semibold truncate">{job.company}</span>
            {job.posted_date && (
              <span className="ml-auto text-slate-600 shrink-0 tabular-nums">{job.posted_date.slice(0, 10)}</span>
            )}
          </div>
          <p className="font-bold text-white leading-snug">{job.title}</p>
          {job.location && (
            <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3 shrink-0"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
              {job.location}
            </p>
          )}
        </div>

        {job.score > 0 && (
          <Tooltip text={`${scoreLabel(job.score)} — ${job.score.toFixed(1)}/5.0`} position="left">
            <div className={`text-sm font-bold shrink-0 px-2 py-1 rounded-lg bg-slate-800 ${scoreColor(job.score)} cursor-default`}>
              ★ {job.score.toFixed(1)}
            </div>
          </Tooltip>
        )}
      </div>

      {/* Skills */}
      {!compact && (tags.length > 0 || missing.length > 0) && (
        <div className="flex flex-wrap gap-1 mb-2">
          {tags.slice(0, 3).map((t) => (
            <Tooltip key={t} text={`You have this skill — ${t}`} position="top">
              <span className="text-xs px-2 py-0.5 rounded-full bg-green-900/40 text-green-300 border border-green-800/40 cursor-default">✓ {t}</span>
            </Tooltip>
          ))}
          {missing.map((t) => (
            <Tooltip key={t} text={`Missing skill — consider adding ${t} to your profile`} position="top">
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-900/30 text-red-400 border border-red-800/30 cursor-default">✗ {t}</span>
            </Tooltip>
          ))}
        </div>
      )}

      {/* Expanded description */}
      {expanded && job.description && (
        <div className="text-xs text-slate-300 leading-relaxed max-h-48 overflow-y-auto no-scrollbar border-t border-slate-800 pt-3 mb-2 whitespace-pre-wrap">
          {job.description.slice(0, 1500)}{job.description.length > 1500 && "…"}
        </div>
      )}

      {/* Note input */}
      {addingNote && (
        <div className="flex gap-2 mb-2">
          <input
            autoFocus
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveNote()}
            placeholder="Add a note… (Enter to save)"
            className="flex-1 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
          />
          <button
            onClick={saveNote}
            disabled={busy === "note"}
            className="px-3 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium disabled:opacity-50 transition"
          >
            {busy === "note" ? "…" : "Save"}
          </button>
        </div>
      )}

      {/* Notes display */}
      {job.notes && (
        <div className="text-xs text-slate-400 bg-slate-800/60 rounded-xl px-3 py-2 mb-2 border-l-2 border-blue-800">
          {job.notes}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-1.5 flex-wrap">
        {job.status === "new" && (
          <>
            <Tooltip text="Mark this job as applied" position="top">
              <button onClick={() => doAction("apply")} disabled={!!busy}
                className={`flex-1 min-w-0 py-2 rounded-xl text-white text-xs font-semibold transition-all active:scale-95 disabled:opacity-50 ${done === "apply" ? "bg-green-500" : "bg-green-700 hover:bg-green-600"}`}>
                {done === "apply" ? "✓ Applied!" : busy === "apply" ? "…" : "✅ Apply"}
              </button>
            </Tooltip>
            <Tooltip text="Skip this job — won't apply" position="top">
              <button onClick={() => doAction("skip")} disabled={!!busy}
                className="flex-1 min-w-0 py-2 rounded-xl bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold transition-all active:scale-95 disabled:opacity-50">
                {busy === "skip" ? "…" : "❌ Skip"}
              </button>
            </Tooltip>
          </>
        )}
        {job.status === "applied" && job.outcome === "pending" && (
          <>
            <Tooltip text="You received an interview!" position="top">
              <button onClick={() => doAction("interview")} disabled={!!busy}
                className={`flex-1 min-w-0 py-2 rounded-xl text-white text-xs font-semibold transition-all active:scale-95 disabled:opacity-50 ${done === "interview" ? "bg-purple-500" : "bg-purple-700 hover:bg-purple-600"}`}>
                {done === "interview" ? "✓ Saved!" : busy === "interview" ? "…" : "🎉 Interview"}
              </button>
            </Tooltip>
            <Tooltip text="Application was rejected" position="top">
              <button onClick={() => doAction("rejected")} disabled={!!busy}
                className="flex-1 min-w-0 py-2 rounded-xl bg-red-900 hover:bg-red-800 text-white text-xs font-semibold transition-all active:scale-95 disabled:opacity-50">
                {busy === "rejected" ? "…" : "👎 Rejected"}
              </button>
            </Tooltip>
            <Tooltip text="No response in 14+ days" position="top">
              <button onClick={() => doAction("ghosted")} disabled={!!busy}
                className="flex-1 min-w-0 py-2 rounded-xl bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold transition-all active:scale-95 disabled:opacity-50">
                {busy === "ghosted" ? "…" : "👻 Ghost"}
              </button>
            </Tooltip>
          </>
        )}

        {/* Utility buttons */}
        <Tooltip text={expanded ? "Collapse description" : "Read full job description"} position="top">
          <button onClick={() => setExpanded(!expanded)}
            className="px-2.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-xs transition">
            {expanded ? "▲" : "📋"}
          </button>
        </Tooltip>
        <Tooltip text={addingNote ? "Cancel note" : "Add a private note to this job"} position="top">
          <button onClick={() => setAddingNote(!addingNote)}
            className="px-2.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-xs transition">
            📝
          </button>
        </Tooltip>
        {job.url && (
          <Tooltip text="Open original job posting" position="top">
            <a href={job.url} target="_blank" rel="noopener noreferrer"
              className="px-2.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-xs transition flex items-center">
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-3.5 h-3.5"><path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>
            </a>
          </Tooltip>
        )}
      </div>
    </div>
  );
}
