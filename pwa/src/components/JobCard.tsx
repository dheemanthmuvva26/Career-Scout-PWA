"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type Job } from "@/lib/api";
import { haptics } from "@/lib/haptics";
import { detectProfile, PROFILES, PROFILE_DISPLAY } from "@/lib/profiles";

const URGENCY: Record<string, { label: string; color: string }> = {
  hot:    { label: "Hot",    color: "#ef4444" },
  active: { label: "Active", color: "#f59e0b" },
  aging:  { label: "Aging",  color: "#52525b" },
  stale:  { label: "Stale",  color: "#3f3f46" },
};

const scoreColor = (s: number) => s >= 4 ? "#22c55e" : s >= 3 ? "#f59e0b" : "#ef4444";

type Props = { job: Job; onUpdate?: (id: string, changes: Partial<Job>) => void; compact?: boolean };

type ForgeSheet = {
  open: boolean;
  profile: string;
  display: string;
  matchedTags: string[];
  changing: boolean;
};
const CLOSED_FORGE: ForgeSheet = { open: false, profile: "", display: "", matchedTags: [], changing: false };

export default function JobCard({ job, onUpdate, compact = false }: Props) {
  const router = useRouter();
  const [expanded, setExpanded]   = useState(false);
  const [addingNote, setAddingNote] = useState(false);
  const [note, setNote]           = useState("");
  const [busy, setBusy]           = useState<string | null>(null);
  const [flash, setFlash]         = useState<string | null>(null);
  // Action confirm: "apply" | "rejected" | "ghosted" | null
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  // Forge profile sheet
  const [forgeSheet, setForgeSheet] = useState<ForgeSheet>(CLOSED_FORGE);

  const sid  = job.short_id || job.id;
  const tags: string[]    = Array.isArray(job.tags_matched) ? job.tags_matched : [];
  const detail            = (job.score_detail as Record<string, unknown>) || {};
  const missing: string[] = Array.isArray((detail as Record<string, string[]>).missing_skills)
    ? (detail as Record<string, string[]>).missing_skills.slice(0, 3) : [];
  const urg = URGENCY[job.urgency] || URGENCY.aging;

  // ── Swipe actions ──────────────────────────────────────────────────────────
  const swipe = job.status === "new"
    ? { right: { action: "apply",     label: "Apply",     color: "#22c55e" },
        left:  { action: "skip",      label: "Skip",       color: "#52525b" } }
    : job.status === "applied" && job.outcome === "pending"
    ? { right: { action: "interview", label: "Interview", color: "#a855f7" },
        left:  { action: "rejected",  label: "Rejected",   color: "#ef4444" } }
    : null;

  const cardRef       = useRef<HTMLDivElement>(null);
  const [dragX, setDragX]         = useState(0);
  const [dragSettling, setDragSettling] = useState(false);
  const dragStartX = useRef(0);
  const dragStartY = useRef(0);
  const axisLocked  = useRef<"x" | "y" | null>(null);
  const draggedPastThreshold = useRef(false);
  const SWIPE_THRESHOLD = 88;

  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (!swipe) return;
    dragStartX.current = e.touches[0].clientX;
    dragStartY.current = e.touches[0].clientY;
    axisLocked.current = null;
    draggedPastThreshold.current = false;
    setDragSettling(false);
  }, [swipe]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!swipe) return;
    const dx = e.touches[0].clientX - dragStartX.current;
    const dy = e.touches[0].clientY - dragStartY.current;
    if (axisLocked.current === null) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
      axisLocked.current = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    }
    if (axisLocked.current !== "x") return;
    e.preventDefault();
    setDragX(dx);
    const past = Math.abs(dx) >= SWIPE_THRESHOLD;
    if (past && !draggedPastThreshold.current) haptics.medium();
    draggedPastThreshold.current = past;
  }, [swipe]);

  const handleTouchEnd = useCallback(() => {
    if (!swipe || axisLocked.current !== "x") { setDragX(0); return; }
    if (draggedPastThreshold.current) {
      const goingRight = dragX > 0;
      const chosen = goingRight ? swipe.right : swipe.left;
      setDragSettling(true);
      setDragX(goingRight ? 480 : -480);
      haptics.success();
      // Swipe is intentional — no confirmation needed
      setTimeout(() => { act(chosen.action); setDragX(0); setDragSettling(false); }, 220);
    } else {
      setDragSettling(true);
      setDragX(0);
    }
  }, [swipe, dragX]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = cardRef.current;
    if (!el || !swipe) return;
    el.addEventListener("touchstart", handleTouchStart, { passive: true });
    el.addEventListener("touchmove",  handleTouchMove,  { passive: false });
    el.addEventListener("touchend",   handleTouchEnd,   { passive: true });
    return () => {
      el.removeEventListener("touchstart", handleTouchStart);
      el.removeEventListener("touchmove",  handleTouchMove);
      el.removeEventListener("touchend",   handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd, swipe]);

  const swipeProgress = swipe ? Math.min(Math.abs(dragX) / SWIPE_THRESHOLD, 1) : 0;
  const activeSwipeSide = swipe && dragX > 0 ? swipe.right : swipe && dragX < 0 ? swipe.left : null;

  async function act(action: string) {
    setConfirmAction(null);
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

  function openForgeSheet() {
    haptics.light();
    const { profile, display, matchedTags } = detectProfile(tags);
    setForgeSheet({ open: true, profile, display, matchedTags, changing: false });
  }

  function goToForge() {
    haptics.light();
    setForgeSheet(CLOSED_FORGE);
    router.push(`/forge?job=${job.id}`);
  }

  // ── Inline confirm banner (for Apply / Rejected / Ghosted) ─────────────────
  const confirmBanner = confirmAction && (
    <div className="mt-2 rounded-xl px-3 py-2.5 flex items-center gap-2"
      style={{
        background: confirmAction === "apply" ? "rgba(34,197,94,0.08)"
          : confirmAction === "rejected" ? "rgba(239,68,68,0.08)"
          : "rgba(82,82,91,0.12)",
        border: `1px solid ${confirmAction === "apply" ? "rgba(34,197,94,0.25)"
          : confirmAction === "rejected" ? "rgba(239,68,68,0.25)"
          : "rgba(82,82,91,0.3)"}`,
      }}>
      <p className="flex-1 text-xs font-semibold"
        style={{ color: confirmAction === "apply" ? "#86efac" : confirmAction === "rejected" ? "#fca5a5" : "var(--text-3)" }}>
        {confirmAction === "apply" ? "Mark as Applied?" : confirmAction === "rejected" ? "Mark as Rejected?" : "Mark as Ghosted?"}
      </p>
      <button onClick={() => { haptics.medium(); act(confirmAction); }}
        disabled={!!busy}
        className="px-3 py-1 rounded-lg text-xs font-bold transition active:scale-95 disabled:opacity-50"
        style={{
          background: confirmAction === "apply" ? "rgba(34,197,94,0.2)"
            : confirmAction === "rejected" ? "rgba(239,68,68,0.2)"
            : "rgba(82,82,91,0.3)",
          color: confirmAction === "apply" ? "#86efac" : confirmAction === "rejected" ? "#fca5a5" : "var(--text-2)",
        }}>
        {busy === confirmAction ? "…" : "Yes"}
      </button>
      <button onClick={() => setConfirmAction(null)}
        className="px-3 py-1 rounded-lg text-xs font-semibold transition active:scale-95"
        style={{ background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border)" }}>
        No
      </button>
    </div>
  );

  // ── Forge profile bottom sheet ──────────────────────────────────────────────
  const forgeSheetEl = forgeSheet.open && (
    <div className="fixed inset-0 z-50 flex items-end"
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) setForgeSheet(CLOSED_FORGE); }}>
      <div className="w-full max-w-lg mx-auto rounded-t-3xl p-5 pb-10 slide-up"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>

        <div className="w-10 h-1 rounded-full mx-auto mb-5" style={{ background: "var(--border)" }} />

        {!forgeSheet.changing ? (
          /* ── Profile preview ── */
          <>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--text-3)" }}>Forge resume for</p>
            <p className="font-semibold text-sm mb-0.5" style={{ color: "var(--text)" }}>{job.title}</p>
            <p className="text-xs mb-4" style={{ color: "var(--text-3)" }}>{job.company}{job.location ? ` · ${job.location}` : ""}</p>

            <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: "var(--text-3)" }}>Detected profile</p>
            <div className="flex items-center gap-3 mb-5">
              <span className="px-3 py-1.5 rounded-lg text-sm font-bold"
                style={{ background: "var(--accent-20)", color: "var(--accent)", border: "1px solid var(--accent-40)" }}>
                {forgeSheet.display}
              </span>
              {forgeSheet.matchedTags.length > 0 && (
                <span className="text-xs" style={{ color: "var(--text-3)" }}>
                  via: {forgeSheet.matchedTags.slice(0, 3).join(", ")}
                </span>
              )}
            </div>

            <div className="flex gap-2">
              <button onClick={goToForge}
                className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95 flex items-center justify-center gap-2"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                  <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Forge with {forgeSheet.display}
              </button>
              <button onClick={() => setForgeSheet(s => ({ ...s, changing: true }))}
                className="py-3 px-4 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
                Change
              </button>
            </div>
          </>
        ) : (
          /* ── Profile picker ── */
          <>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Choose a profile</p>
            <div className="flex flex-wrap gap-2 mb-5">
              {PROFILES.filter(p => p.id).map(p => {
                const active = forgeSheet.profile === p.id;
                return (
                  <button key={p.id}
                    onClick={() => setForgeSheet(s => ({ ...s, profile: p.id, display: PROFILE_DISPLAY[p.id] ?? p.label }))}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold transition active:scale-95"
                    style={{
                      background: active ? "var(--accent-20)" : "var(--surface-2)",
                      color: active ? "var(--accent)" : "var(--text-3)",
                      border: `1px solid ${active ? "var(--accent-40)" : "var(--border)"}`,
                    }}>
                    {p.label}
                  </button>
                );
              })}
            </div>
            <div className="flex gap-2">
              <button onClick={goToForge}
                className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                Forge with {forgeSheet.display || "Default"}
              </button>
              <button onClick={() => setForgeSheet(s => ({ ...s, changing: false }))}
                className="py-3 px-4 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
                Back
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );

  return (
    <>
    <div className="relative mb-3">
      {/* Swipe background reveal */}
      {swipe && dragX !== 0 && (
        <div className="absolute inset-0 rounded-2xl flex items-center px-5"
          style={{
            justifyContent: dragX > 0 ? "flex-start" : "flex-end",
            background: `${activeSwipeSide?.color}22`,
            border: `1px solid ${activeSwipeSide?.color}40`,
          }}>
          <span className="text-sm font-bold flex items-center gap-1.5"
            style={{ color: activeSwipeSide?.color, opacity: 0.5 + swipeProgress * 0.5 }}>
            {dragX < 0 && activeSwipeSide?.label}
            {dragX > 0 && (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-4 h-4">
                <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
            {dragX > 0 && activeSwipeSide?.label}
            {dragX < 0 && (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-4 h-4">
                <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </span>
        </div>
      )}

      <div ref={cardRef} className="card overflow-hidden"
        style={{
          transform: dragX !== 0 ? `translateX(${dragX}px)` : undefined,
          transition: dragSettling ? "transform 0.22s cubic-bezier(0.23,1,0.32,1)" : "none",
        }}>
      {/* Top accent line for urgency */}
      <div className="h-0.5" style={{ background: urg.color, opacity: 0.6 }} />

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
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
              {/* Apply — tapping shows confirm banner; swipe bypasses it */}
              <button
                onClick={() => { haptics.light(); setConfirmAction(confirmAction === "apply" ? null : "apply"); }}
                disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
                style={{
                  background: flash === "apply" ? "#15803d"
                    : confirmAction === "apply" ? "rgba(34,197,94,0.25)"
                    : "rgba(34,197,94,0.15)",
                  color: flash === "apply" ? "#fff" : "#86efac",
                  border: `1px solid ${confirmAction === "apply" ? "rgba(34,197,94,0.5)" : "rgba(34,197,94,0.2)"}`,
                }}>
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
              {/* Rejected + Ghosted show confirm banner */}
              <button
                onClick={() => { haptics.light(); setConfirmAction(confirmAction === "rejected" ? null : "rejected"); }}
                disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold active:scale-95 disabled:opacity-50"
                style={{
                  background: confirmAction === "rejected" ? "rgba(239,68,68,0.18)" : "rgba(239,68,68,0.08)",
                  color: "#fca5a5",
                  border: `1px solid ${confirmAction === "rejected" ? "rgba(239,68,68,0.4)" : "rgba(239,68,68,0.15)"}`,
                }}>
                {busy === "rejected" ? "…" : "Rejected"}
              </button>
              <button
                onClick={() => { haptics.light(); setConfirmAction(confirmAction === "ghosted" ? null : "ghosted"); }}
                disabled={!!busy}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold active:scale-95 disabled:opacity-50"
                style={{
                  background: confirmAction === "ghosted" ? "rgba(82,82,91,0.25)" : "var(--surface-2)",
                  color: "var(--text-3)",
                  border: `1px solid ${confirmAction === "ghosted" ? "rgba(82,82,91,0.5)" : "var(--border)"}`,
                }}>
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
          {/* Forge shortcut — opens profile sheet */}
          <button
            onClick={openForgeSheet}
            className="w-10 h-10 rounded-xl flex items-center justify-center transition active:scale-95 shrink-0"
            style={{ background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border)" }}
            title="Forge resume">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/>
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

        {/* Inline confirm banner */}
        {confirmBanner}

        {/* Date footer */}
        {job.posted_date && (
          <p className="text-[10px] mt-2 text-right" style={{ color: "var(--text-3)" }}>
            Posted {job.posted_date.slice(0, 10)}
          </p>
        )}
      </div>
      </div>
    </div>

    {/* Forge profile bottom sheet — rendered outside card to escape stacking context */}
    {forgeSheetEl}
    </>
  );
}
