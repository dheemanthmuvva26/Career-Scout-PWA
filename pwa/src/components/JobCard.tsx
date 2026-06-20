"use client";

import { useState } from "react";
import { api, type Job } from "@/lib/api";

const URGENCY_DOT: Record<string, string> = {
  hot: "🔴",
  active: "🟡",
  aging: "⚪",
  stale: "💀",
};

const SCORE_COLOR = (s: number) =>
  s >= 4 ? "text-green-400" : s >= 3 ? "text-yellow-400" : "text-red-400";

type Props = {
  job: Job;
  onUpdate?: (id: string, changes: Partial<Job>) => void;
  compact?: boolean;
};

export default function JobCard({ job, onUpdate, compact = false }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const sid = job.short_id || job.id;
  const tags: string[] = Array.isArray(job.tags_matched) ? job.tags_matched : [];
  const detail = (job.score_detail as Record<string, unknown>) || {};
  const missing: string[] = Array.isArray((detail as Record<string, string[]>).missing_skills)
    ? (detail as Record<string, string[]>).missing_skills.slice(0, 3)
    : [];

  async function doAction(action: string) {
    setBusy(action);
    try {
      if (action === "apply") {
        await api.apply(sid);
        onUpdate?.(job.id, { status: "applied" });
      } else if (action === "skip") {
        await api.setStatus(sid, "skipped");
        onUpdate?.(job.id, { status: "skipped" });
      } else if (action === "interview") {
        await api.setOutcome(sid, "interview");
        onUpdate?.(job.id, { outcome: "interview", status: "applied" });
      } else if (action === "rejected") {
        await api.setOutcome(sid, "rejected");
        onUpdate?.(job.id, { outcome: "rejected" });
      } else if (action === "ghosted") {
        await api.setOutcome(sid, "ghosted");
        onUpdate?.(job.id, { status: "ghosted" });
      }
    } catch (e) {
      console.error(e);
    }
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
    <div
      className="rounded-2xl border border-slate-700 p-4 mb-3"
      style={{ background: "var(--card)" }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
            <span>{URGENCY_DOT[job.urgency] || "⚪"}</span>
            <span className="truncate font-medium text-slate-300">{job.company}</span>
            {job.posted_date && (
              <span className="ml-auto shrink-0">{job.posted_date.slice(0, 10)}</span>
            )}
          </div>
          <p className="font-semibold text-white leading-tight truncate">{job.title}</p>
          {job.location && (
            <p className="text-xs text-slate-400 mt-0.5 truncate">{job.location}</p>
          )}
        </div>
        {job.score > 0 && (
          <span className={`text-sm font-bold shrink-0 ${SCORE_COLOR(job.score)}`}>
            ★ {job.score.toFixed(1)}
          </span>
        )}
      </div>

      {/* Skills */}
      {!compact && (tags.length > 0 || missing.length > 0) && (
        <div className="flex flex-wrap gap-1 mt-2">
          {tags.slice(0, 3).map((t) => (
            <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-green-900/50 text-green-300">
              ✓ {t}
            </span>
          ))}
          {missing.map((t) => (
            <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-red-900/30 text-red-400">
              ✗ {t}
            </span>
          ))}
        </div>
      )}

      {/* Expanded description */}
      {expanded && job.description && (
        <div className="mt-3 text-xs text-slate-300 leading-relaxed max-h-48 overflow-y-auto no-scrollbar whitespace-pre-wrap border-t border-slate-700 pt-3">
          {job.description.slice(0, 1500)}
          {job.description.length > 1500 && "..."}
        </div>
      )}

      {/* Note input */}
      {addingNote && (
        <div className="mt-3 flex gap-2">
          <input
            autoFocus
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note..."
            className="flex-1 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-600 text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={saveNote}
            disabled={busy === "note"}
            className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50"
          >
            {busy === "note" ? "..." : "Save"}
          </button>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-3 flex-wrap">
        {job.status === "new" && (
          <>
            <button
              onClick={() => doAction("apply")}
              disabled={!!busy}
              className="flex-1 py-1.5 rounded-lg bg-green-700 hover:bg-green-600 text-white text-sm font-medium transition disabled:opacity-50"
            >
              {busy === "apply" ? "..." : "✅ Apply"}
            </button>
            <button
              onClick={() => doAction("skip")}
              disabled={!!busy}
              className="flex-1 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium transition disabled:opacity-50"
            >
              {busy === "skip" ? "..." : "❌ Skip"}
            </button>
          </>
        )}
        {job.status === "applied" && job.outcome === "pending" && (
          <>
            <button
              onClick={() => doAction("interview")}
              disabled={!!busy}
              className="flex-1 py-1.5 rounded-lg bg-purple-700 hover:bg-purple-600 text-white text-sm font-medium transition disabled:opacity-50"
            >
              {busy === "interview" ? "..." : "🎉 Interview"}
            </button>
            <button
              onClick={() => doAction("rejected")}
              disabled={!!busy}
              className="flex-1 py-1.5 rounded-lg bg-red-900 hover:bg-red-800 text-white text-sm font-medium transition disabled:opacity-50"
            >
              {busy === "rejected" ? "..." : "👎 Rejected"}
            </button>
            <button
              onClick={() => doAction("ghosted")}
              disabled={!!busy}
              className="flex-1 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium transition disabled:opacity-50"
            >
              {busy === "ghosted" ? "..." : "👻 Ghosted"}
            </button>
          </>
        )}
        <button
          onClick={() => setExpanded(!expanded)}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition"
        >
          {expanded ? "▲" : "📋"}
        </button>
        <button
          onClick={() => setAddingNote(!addingNote)}
          className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition"
        >
          📝
        </button>
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition"
          >
            🔗
          </a>
        )}
      </div>

      {/* Notes display */}
      {job.notes && (
        <div className="mt-2 text-xs text-slate-400 bg-slate-800/50 rounded-lg px-3 py-2">
          {job.notes}
        </div>
      )}
    </div>
  );
}
