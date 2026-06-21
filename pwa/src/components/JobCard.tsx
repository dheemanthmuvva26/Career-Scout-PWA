"use client";

import { useState } from "react";
import { api, type Job } from "@/lib/api";

const URGENCY: Record<string, { label: string; color: string }> = {
  hot:    { label: "Hot",    color: "#ef4444" },
  active: { label: "Active", color: "#f59e0b" },
  aging:  { label: "Aging",  color: "#52525b" },
  stale:  { label: "Stale",  color: "#3f3f46" },
};

const scoreColor = (s: number) => s >= 4 ? "#22c55e" : s >= 3 ? "#f59e0b" : "#ef4444";

type Props = { job: Job; onUpdate?: (id: string, changes: Partial<Job>) => void; compact?: boolean };

export default function JobCard({ job, onUpdate, compact = false }: Props) {
  const [expanded, setExpanded]   = useState(false);
  const [addingNote, setAddingNote] = useState(false);
  const [note, setNote]           = useState("");
  const [busy, setBusy]           = useState<string | null>(null);
  const [flash, setFlash]         = useState<string | null>(null);

  const sid  = job.short_id || job.id;
  const tags: string[]    = Array.isArray(job.tags_matched) ? job.tags_matched : [];
  const detail            = (job.score_detail as Record<string, unknown>) || {};
  const missing: string[] = Array.isArray((detail as Record<string, string[]>).missing_skills)
    ? (detail as Record<string, string[]>).missing_skills.slice(0, 3) : [];
  const urg = URGENCY[job.urgency] || URGENCY.aging;

  async function act(action: string) {
    setBusy(action);
    try {
      if (action === "apply")     { await api.apply(sid);                  onUpdate?.(job.id, { status: "applied" }); }
      if (action === "skip")      { await api.setStatus(sid, "skipped");    onUpdate?.(job.id, { status: "skipped" }); }
      if (action === "interview") { await api.setOutcome(sid, "interview"); onUpdate?.(job.id, { outcome: "interview" }); }
      if (action === "rejected")  { await api.setOutcome(sid, "rejected");  onUpdate?.(job.id, { outcome: "rejected" }); }
      if (action === "ghosted")   { await api.setOutcome(sid, "ghosted");   onUpdate?.(job.id, { status: "ghosted" }); }
      setFlash(action);
      setTimeout(() => setFlash(null), 1800);
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
    <div className="card mb-3 overflow-hidden">
      {/* Top accent line for urgency */}
      <div className="h-0.5" style={{ background: urg.color, opacity: 0.6 }} />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          {/* Company initial */}
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 text-sm font-bold"
            style={{ background: "var(--surface-2)", color: "var(--text-2)", border: "1px solid var(--border)" }}>
            {job.company?.charAt(0)?.toUpperCase() ?? "?"}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-xs font-medium truncate" style={{ color: "var(--text-2)" }}>{job.company}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                style={{ background: `${urg.color}18`, color: urg.color }}>
                {urg.label}
              </span>
            </div>
            <p className="font-semibold leading-snug" style={{ color: "var(--text)", fontSize: "0.95rem" }}>{job.title}</p>
            {job.location && (
              <p className="text-xs mt-0.5 truncate" style={{ color: "var(--text-3)" }}>{job.location}</p>
            )}
          </div>

          {job.score > 0 && (
            <div className="shrink-0 text-right">
              <div className="text-base font-bold tabular-nums" style={{ color: scoreColor(job.score) }}>
                {job.score.toFixed(1)}
              </div>
              <div className="text-[10px]" style={{ color: "var(--text-3)" }}>/ 5.0</div>
            </div>
          )}
        </div>

        {/* Skill chips */}
        {!compact && (tags.length > 0 || missing.length > 0) && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {tags.slice(0, 3).map((t) => (
              <span key={t} className="text-xs px-2.5 py-1 rounded-full font-medium"
                style={{ background: "rgba(34,197,94,0.1)", color: "#86efac", border: "1px solid rgba(34,197,94,0.2)" }}>
                ✓ {t}
              </span>
            ))}
            {missing.map((t) => (
              <span key={t} className="text-xs px-2.5 py-1 rounded-full font-medium"
                style={{ background: "rgba(239,68,68,0.08)", color: "#fca5a5", border: "1px solid rgba(239,68,68,0.15)" }}>
                ✗ {t}
              </span>
            ))}
          </div>
        )}

        {/* Job description (expanded) */}
        {expanded && job.description && (
          <div className="text-xs leading-relaxed max-h-48 overflow-y-auto no-scrollbar mb-3 pt-3"
            style={{ color: "var(--text-2)", borderTop: "1px solid var(--border)" }}>
            {job.description.slice(0, 1500)}{job.description.length > 1500 && "…"}
          </div>
        )}

        {/* Note display */}
        {job.notes && (
          <div className="text-xs px-3 py-2 rounded-xl mb-3"
            style={{ background: "var(--surface-2)", color: "var(--text-2)", borderLeft: "2px solid var(--accent)" }}>
            {job.notes}
          </div>
        )}

        {/* Note input */}
        {addingNote && (
          <div className="flex gap-2 mb-3">
            <input autoFocus value={note} onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveNote()}
              placeholder="Add a note… (Enter to save)" />
            <button onClick={saveNote} disabled={busy === "note"}
              className="px-4 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-50"
              style={{ background: "var(--accent)", color: "var(--on-accent)", minWidth: 64 }}>
              {busy === "note" ? "…" : "Save"}
            </button>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-2">
          {job.status === "new" && (
            <>
              <button onClick={() => act("apply")} disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
                style={{ background: flash === "apply" ? "#15803d" : "rgba(34,197,94,0.15)", color: flash === "apply" ? "#fff" : "#86efac", border: "1px solid rgba(34,197,94,0.2)" }}>
                {flash === "apply" ? "Applied ✓" : busy === "apply" ? "…" : "Apply"}
              </button>
              <button onClick={() => act("skip")} disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
                style={{ background: "var(--surface-2)", color: "var(--text-2)", border: "1px solid var(--border)" }}>
                {busy === "skip" ? "…" : "Skip"}
              </button>
            </>
          )}
          {job.status === "applied" && job.outcome === "pending" && (
            <>
              <button onClick={() => act("interview")} disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold active:scale-95 disabled:opacity-50"
                style={{ background: "rgba(168,85,247,0.12)", color: "#d8b4fe", border: "1px solid rgba(168,85,247,0.2)" }}>
                {flash === "interview" ? "Saved ✓" : busy === "interview" ? "…" : "Interview"}
              </button>
              <button onClick={() => act("rejected")} disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold active:scale-95 disabled:opacity-50"
                style={{ background: "rgba(239,68,68,0.08)", color: "#fca5a5", border: "1px solid rgba(239,68,68,0.15)" }}>
                {busy === "rejected" ? "…" : "Rejected"}
              </button>
              <button onClick={() => act("ghosted")} disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold active:scale-95 disabled:opacity-50"
                style={{ background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border)" }}>
                {busy === "ghosted" ? "…" : "Ghosted"}
              </button>
            </>
          )}

          {/* Utility */}
          <button onClick={() => setExpanded(!expanded)}
            className="w-10 h-10 rounded-xl flex items-center justify-center transition active:scale-95 shrink-0"
            style={{ background: "var(--surface-2)", color: expanded ? "var(--accent)" : "var(--text-3)", border: "1px solid var(--border)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
              {expanded
                ? <path d="M18 15l-6-6-6 6" strokeLinecap="round" strokeLinejoin="round"/>
                : <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round"/>}
            </svg>
          </button>
          <button onClick={() => setAddingNote(!addingNote)}
            className="w-10 h-10 rounded-xl flex items-center justify-center transition active:scale-95 shrink-0"
            style={{ background: addingNote ? "var(--accent-15)" : "var(--surface-2)", color: addingNote ? "var(--accent)" : "var(--text-3)", border: `1px solid ${addingNote ? "var(--accent-30)" : "var(--border)"}` }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" strokeLinecap="round"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" strokeLinecap="round"/>
            </svg>
          </button>
          {job.url && (
            <a href={job.url} target="_blank" rel="noopener noreferrer"
              className="w-10 h-10 rounded-xl flex items-center justify-center transition active:scale-95 shrink-0"
              style={{ background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border)" }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" strokeLinecap="round"/>
                <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
              </svg>
            </a>
          )}
        </div>

        {/* Date footer */}
        {job.posted_date && (
          <p className="text-[10px] mt-2 text-right" style={{ color: "var(--text-3)" }}>
            Posted {job.posted_date.slice(0, 10)}
          </p>
        )}
      </div>
    </div>
  );
}
