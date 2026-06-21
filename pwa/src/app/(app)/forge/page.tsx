"use client";

import { useEffect, useState } from "react";
import { api, type Job } from "@/lib/api";

export default function ForgePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [forging, setForging] = useState(false);
  const [result, setResult] = useState<{ pdf_path?: string; error?: string } | null>(null);

  useEffect(() => {
    Promise.all([
      api.jobs({ status: "new", limit: "50" }),
      api.jobs({ status: "applied", limit: "50" }),
    ])
      .then(([n, a]) => setJobs([...n, ...a]))
      .finally(() => setLoading(false));
  }, []);

  async function forge() {
    if (!selected) return;
    setForging(true);
    setResult(null);
    try {
      const res = await api.forge(selected.short_id || selected.id);
      setResult(res);
    } catch {
      setResult({ error: "Forge failed. Make sure the API server is running." });
    }
    setForging(false);
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL;

  return (
    <div className="pt-8 pb-4 fade-up">
      <h1 className="mb-1" style={{ color: "var(--text)" }}>Resume Forge</h1>
      <p className="text-sm mb-6" style={{ color: "var(--text-3)" }}>Generate an ATS-optimised PDF tailored to a job</p>

      <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Select a job</p>

      {loading ? (
        <div className="space-y-2 mb-6">
          {[1, 2, 3].map((i) => <div key={i} className="skeleton h-16 rounded-xl" />)}
        </div>
      ) : jobs.length === 0 ? (
        <div className="card p-6 text-center mb-6">
          <p className="text-sm" style={{ color: "var(--text-3)" }}>No jobs found. Scout or import first.</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto no-scrollbar mb-6">
          {jobs.map((job) => {
            const isSelected = selected?.id === job.id;
            return (
              <button key={job.id} onClick={() => { setSelected(job); setResult(null); }}
                className="w-full text-left card card-press px-4 py-3 transition"
                style={{
                  background: isSelected ? "var(--accent-10)" : "var(--surface)",
                  borderColor: isSelected ? "var(--accent-40)" : "var(--border)",
                }}>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
                    style={{ background: isSelected ? "var(--accent-20)" : "var(--surface-2)", color: isSelected ? "var(--accent)" : "var(--text-3)" }}>
                    {job.company?.charAt(0)?.toUpperCase() ?? "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate" style={{ color: "var(--text)" }}>{job.title}</div>
                    <div className="text-xs truncate" style={{ color: "var(--text-3)" }}>{job.company}{job.location ? ` · ${job.location}` : ""}</div>
                  </div>
                  {isSelected && (
                    <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0" style={{ color: "var(--accent)" }}>
                      <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
                    </svg>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}

      <button onClick={forge} disabled={!selected || forging}
        className="w-full py-3.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-40 flex items-center justify-center gap-2"
        style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
        {forging ? (
          <>
            <svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/>
            </svg>
            Forging… (15–30s)
          </>
        ) : (
          <>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Generate Resume
          </>
        )}
      </button>

      {forging && (
        <p className="text-xs text-center mt-3" style={{ color: "var(--text-3)" }}>
          Analysing JD · Extracting keywords · Optimising match…
        </p>
      )}

      {result && (
        <div className="mt-5">
          {result.error ? (
            <div className="card p-4 flex gap-3 items-start"
              style={{ borderColor: "rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.06)" }}>
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "#ef4444" }}>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
              </svg>
              <p className="text-sm" style={{ color: "#fca5a5" }}>{result.error}</p>
            </div>
          ) : (
            <div className="card p-5 text-center"
              style={{ borderColor: "rgba(34,197,94,0.3)", background: "rgba(34,197,94,0.06)" }}>
              <div className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3"
                style={{ background: "rgba(34,197,94,0.15)" }}>
                <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6" style={{ color: "#22c55e" }}>
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
                </svg>
              </div>
              <p className="font-semibold mb-1" style={{ color: "#86efac" }}>Resume generated!</p>
              <p className="text-xs mb-4" style={{ color: "var(--text-3)" }}>Tailored and ATS-optimised</p>
              {result.pdf_path && (
                <a href={`${apiBase}/resumes/${result.pdf_path.split(/[\\/]/).pop()}`}
                  target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition active:scale-95"
                  style={{ background: "rgba(34,197,94,0.2)", color: "#86efac", border: "1px solid rgba(34,197,94,0.3)" }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" strokeLinecap="round"/>
                    <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Download PDF
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
