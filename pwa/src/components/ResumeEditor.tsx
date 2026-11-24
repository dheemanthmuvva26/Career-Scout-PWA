"use client";

import { useEffect, useState } from "react";
import { api, type Integrity, type ResumeContent, type ResumeEntry } from "@/lib/api";
import IntegrityReport from "@/components/IntegrityReport";

type Props = {
  jobId: string;
  onRendered: (pdfPath: string) => void;
  onClose: () => void;
};

const label = (k: string) =>
  k.replace(/_/g, " ").replace(/\b(ml|ai|bi|llm|rag|nlp|sql|etl|api)\b/gi, s => s.toUpperCase())
    .replace(/\b\w/g, c => c.toUpperCase());

/**
 * Edit a forged resume's text and re-render the PDF — no AI call, so nothing
 * gets rewritten behind your back. The fact checker still flags anything not
 * backed by your profile after each render.
 */
export default function ResumeEditor({ jobId, onRendered, onClose }: Props) {
  const [content, setContent] = useState<ResumeContent | null>(null);
  const [error, setError] = useState("");
  const [rendering, setRendering] = useState(false);
  const [integrity, setIntegrity] = useState<Integrity | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    api.forgeContent(jobId)
      .then(r => { setContent(r.content); setIntegrity(r.content.integrity ?? null); })
      .catch(e => setError(e instanceof Error ? e.message : "Couldn't load the resume"));
  }, [jobId]);

  function update(fn: (c: ResumeContent) => void) {
    setContent(prev => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
  }

  async function render() {
    if (!content) return;
    setRendering(true);
    setError("");
    try {
      const res = await api.renderResume(jobId, content);
      if (res.error) throw new Error(res.error);
      setContent(res.content);          // what actually landed on the PDF
      setIntegrity(res.integrity ?? null);
      setDirty(false);
      onRendered(res.pdf_path);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Re-render failed");
    }
    setRendering(false);
  }

  if (error && !content) {
    return <p className="text-sm mt-3" style={{ color: "#fca5a5" }}>{error}</p>;
  }
  if (!content) {
    return <div className="skeleton h-40 rounded-xl mt-3" />;
  }

  const skillsOrder = [
    ...(content.skills_order ?? []).filter(k => content.skills_section[k]),
    ...Object.keys(content.skills_section).filter(k => !(content.skills_order ?? []).includes(k)),
  ];

  const moveSkill = (i: number, dir: -1 | 1) => update(c => {
    const order = [...skillsOrder];
    const j = i + dir;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j], order[i]];
    c.skills_order = order;
  });

  const entryEditor = (kind: "selected_experience" | "selected_projects", e: ResumeEntry, ei: number) => (
    <div key={`${kind}-${ei}`} className="rounded-xl p-3" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <p className="text-xs font-semibold mb-2" style={{ color: "var(--text)" }}>
        {kind === "selected_experience" ? `${e.role} — ${e.company}` : e.name}
      </p>
      <div className="space-y-2">
        {e.bullets.map((b, bi) => (
          <div key={bi} className="flex gap-1.5 items-start">
            <textarea value={b} rows={3}
              aria-label={`Bullet ${bi + 1}`}
              onChange={ev => update(c => { c[kind][ei].bullets[bi] = ev.target.value; })}
              className="flex-1 text-xs leading-snug"
              style={{ minHeight: 70, resize: "vertical" }} />
            <div className="flex flex-col gap-1">
              <button aria-label="Move bullet up" disabled={bi === 0}
                onClick={() => update(c => { const a = c[kind][ei].bullets; [a[bi - 1], a[bi]] = [a[bi], a[bi - 1]]; })}
                className="text-[11px] px-1.5 rounded disabled:opacity-30" style={{ color: "var(--text-3)" }}>▲</button>
              <button aria-label="Move bullet down" disabled={bi === e.bullets.length - 1}
                onClick={() => update(c => { const a = c[kind][ei].bullets; [a[bi + 1], a[bi]] = [a[bi], a[bi + 1]]; })}
                className="text-[11px] px-1.5 rounded disabled:opacity-30" style={{ color: "var(--text-3)" }}>▼</button>
              <button aria-label="Delete bullet"
                onClick={() => update(c => { c[kind][ei].bullets.splice(bi, 1); })}
                className="text-[11px] px-1.5 rounded" style={{ color: "#fca5a5" }}>✕</button>
            </div>
          </div>
        ))}
      </div>
      <button onClick={() => update(c => { c[kind][ei].bullets.push(""); })}
        className="text-[11px] font-semibold mt-2" style={{ color: "var(--accent)" }}>+ Add bullet</button>
    </div>
  );

  return (
    <div className="mt-3 rounded-2xl p-4 space-y-4" style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
      <div className="flex items-center">
        <p className="text-[10px] font-bold uppercase tracking-widest flex-1" style={{ color: "var(--text-3)" }}>
          Edit resume
        </p>
        <button onClick={onClose} className="text-xs" style={{ color: "var(--text-3)" }}>Close</button>
      </div>

      <div>
        <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--text-2)" }}>Summary</p>
        <textarea value={content.summary} rows={4} aria-label="Summary"
          onChange={ev => update(c => { c.summary = ev.target.value; })}
          className="w-full text-xs leading-snug" style={{ resize: "vertical" }} />
      </div>

      <div>
        <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--text-2)" }}>Skills (top row shows first)</p>
        <div className="space-y-1.5">
          {skillsOrder.map((k, i) => (
            <div key={k} className="flex gap-1.5 items-center">
              <span className="text-[11px] w-20 shrink-0 font-semibold" style={{ color: "var(--text-3)" }}>{label(k)}</span>
              <input value={content.skills_section[k].join(", ")} aria-label={`${label(k)} skills`}
                onChange={ev => update(c => {
                  c.skills_section[k] = ev.target.value.split(",").map(s => s.trim()).filter(Boolean);
                })}
                className="flex-1 text-xs" style={{ fontSize: 12 }} />
              <button aria-label={`Move ${label(k)} up`} disabled={i === 0} onClick={() => moveSkill(i, -1)}
                className="text-[11px] px-1 disabled:opacity-30" style={{ color: "var(--text-3)" }}>▲</button>
              <button aria-label={`Move ${label(k)} down`} disabled={i === skillsOrder.length - 1} onClick={() => moveSkill(i, 1)}
                className="text-[11px] px-1 disabled:opacity-30" style={{ color: "var(--text-3)" }}>▼</button>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold" style={{ color: "var(--text-2)" }}>Projects</p>
        {content.selected_projects.map((e, i) => entryEditor("selected_projects", e, i))}
      </div>
      <div className="space-y-2">
        <p className="text-xs font-semibold" style={{ color: "var(--text-2)" }}>Experience</p>
        {content.selected_experience.map((e, i) => entryEditor("selected_experience", e, i))}
      </div>

      {error && <p className="text-xs" style={{ color: "#fca5a5" }}>{error}</p>}

      <button onClick={render} disabled={rendering || !dirty}
        className="w-full py-3 rounded-xl text-sm font-semibold transition active:scale-95 disabled:opacity-50"
        style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
        {rendering ? "Rendering PDF…" : dirty ? "Re-render PDF" : "No changes yet"}
      </button>
      <p className="text-[11px] text-center" style={{ color: "var(--text-3)" }}>
        No AI rewrite — your text goes onto the PDF as written. If it doesn&apos;t fit one page, the last bullet of the lowest section is trimmed.
      </p>

      <IntegrityReport integrity={integrity} />
    </div>
  );
}
