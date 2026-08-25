"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { haptics } from "@/lib/haptics";

type Props = {
  skill: string;
  className?: string;
};

export default function MissingSkillChip({
  skill,
  className = "text-xs px-2.5 py-1 rounded-full font-medium",
}: Props) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<"missing" | "saving" | "confirmed">("missing");

  async function confirm() {
    setStatus("saving");
    try {
      await api.confirmSkill(skill);
      haptics.success();
      setStatus("confirmed");
      setTimeout(() => setOpen(false), 900);
    } catch {
      setStatus("missing");
      setOpen(false);
    }
  }

  const confirmed = status === "confirmed";

  return (
    <>
      <button
        type="button"
        onClick={() => { haptics.light(); setOpen(true); }}
        className={className}
        style={{
          background: confirmed ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.08)",
          color: confirmed ? "#86efac" : "#fca5a5",
          border: `1px solid ${confirmed ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.15)"}`,
          transition: "background 0.2s ease, color 0.2s ease, border-color 0.2s ease",
        }}
      >
        {confirmed ? "✓" : "✗"} {skill}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end"
          style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}
          onClick={(e) => { if (e.target === e.currentTarget && status !== "saving") setOpen(false); }}
        >
          <div
            className="w-full max-w-lg mx-auto rounded-t-3xl p-5 pb-10 slide-up"
            style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
          >
            <div className="w-10 h-1 rounded-full mx-auto mb-5" style={{ background: "var(--border)" }} />

            {status === "confirmed" ? (
              <div className="text-center py-2">
                <div
                  className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-3"
                  style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.25)" }}
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6" style={{ color: "#22c55e" }}>
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>Saved</p>
                <p className="text-xs mt-1" style={{ color: "var(--text-3)" }}>
                  Future scoring won&apos;t flag {skill} as missing.
                </p>
              </div>
            ) : (
              <>
                <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>
                  Missing skill
                </p>
                <p className="text-base font-semibold mb-1" style={{ color: "var(--text)" }}>
                  Do you actually have this skill?
                </p>
                <p className="text-sm mb-5" style={{ color: "var(--text-2)" }}>
                  <strong style={{ color: "var(--text)" }}>{skill}</strong> — if yes, we&apos;ll remember it so
                  future job matches don&apos;t flag it as missing, even if it&apos;s not explicitly on your
                  resume yet.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={confirm}
                    disabled={status === "saving"}
                    className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95 disabled:opacity-50"
                    style={{ background: "var(--accent)", color: "var(--on-accent)" }}
                  >
                    {status === "saving" ? "Saving…" : "Yes, I have this"}
                  </button>
                  <button
                    onClick={() => setOpen(false)}
                    disabled={status === "saving"}
                    className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95"
                    style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}
                  >
                    No
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
