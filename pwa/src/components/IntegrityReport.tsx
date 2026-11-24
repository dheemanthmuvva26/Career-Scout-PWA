"use client";

import { useState } from "react";
import type { Integrity } from "@/lib/api";

/**
 * Shows what the fact checker found in a resume. For a forge (mode "repair")
 * it lists what was changed automatically; for an edit (mode "warn") it lists
 * problems the user should fix before sending.
 */
export default function IntegrityReport({ integrity }: { integrity?: Integrity | null }) {
  const [open, setOpen] = useState(false);
  if (!integrity) return null;

  const { issues, warnings, claim_check, mode } = integrity;
  const skipped = claim_check.startsWith("skipped");
  const clean = issues.length === 0 && warnings.length === 0 && !skipped;

  const tone = clean
    ? { bg: "rgba(34,197,94,0.06)", border: "rgba(34,197,94,0.25)", fg: "#86efac" }
    : mode === "warn" && issues.length > 0
      ? { bg: "rgba(239,68,68,0.06)", border: "rgba(239,68,68,0.25)", fg: "#fca5a5" }
      : { bg: "rgba(245,158,11,0.06)", border: "rgba(245,158,11,0.25)", fg: "var(--amber)" };

  const headline = clean
    ? "Fact check passed — every number matches your profile"
    : mode === "repair"
      ? `Fact check fixed ${issues.length} item${issues.length === 1 ? "" : "s"} the optimizer made up`
      : issues.length > 0
        ? `${issues.length} item${issues.length === 1 ? "" : "s"} not backed by your profile`
        : "Fact check: review the notes below";

  return (
    <div className="rounded-xl p-3 mt-3" style={{ background: tone.bg, border: `1px solid ${tone.border}` }}>
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-2 text-left"
        disabled={clean} aria-expanded={open}>
        <span className="text-xs font-semibold flex-1" style={{ color: tone.fg }}>
          {clean ? "✓" : "⚠"} {headline}
        </span>
        {!clean && (
          <span className="text-[11px]" style={{ color: "var(--text-3)" }}>{open ? "Hide" : "Details"}</span>
        )}
      </button>

      {open && !clean && (
        <div className="mt-3 space-y-2">
          {issues.map((i, k) => (
            <div key={k} className="rounded-lg p-2.5" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
              <p className="text-[11px] font-semibold mb-1" style={{ color: "var(--text-2)" }}>
                {i.section}{i.entry && i.entry !== i.text ? ` · ${i.entry.slice(0, 40)}` : ""}
                <span className="ml-1.5 font-normal" style={{ color: "var(--text-3)" }}>— {i.action}</span>
              </p>
              <p className="text-[11px] mb-1" style={{ color: "var(--text-3)" }}>{i.reason}</p>
              <p className="text-[11px] line-through" style={{ color: "var(--text-3)" }}>{i.text}</p>
              {i.replacement && (
                <p className="text-[11px] mt-1" style={{ color: "var(--text-2)" }}>→ {i.replacement}</p>
              )}
            </div>
          ))}
          {warnings.map((w, k) => (
            <p key={k} className="text-[11px]" style={{ color: "var(--amber)" }}>• {w}</p>
          ))}
        </div>
      )}
    </div>
  );
}
