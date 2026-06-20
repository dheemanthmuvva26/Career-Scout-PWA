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
    <div className="max-w-lg mx-auto px-4 pt-6">
      <h1 className="text-xl font-bold text-white mb-1">Resume Forge</h1>
      <p className="text-slate-400 text-sm mb-5">Generate an ATS-optimised PDF tailored to a job.</p>

      {/* Job selector */}
      <label className="block text-sm text-slate-400 mb-2">Select a job</label>
      {loading ? (
        <div className="h-12 rounded-xl bg-slate-800 animate-pulse mb-4" />
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto no-scrollbar mb-5">
          {jobs.length === 0 && (
            <p className="text-slate-500 text-sm">No jobs found. Import or scout first.</p>
          )}
          {jobs.map((job) => (
            <button
              key={job.id}
              onClick={() => { setSelected(job); setResult(null); }}
              className={`w-full text-left rounded-xl px-4 py-3 border transition ${
                selected?.id === job.id
                  ? "border-blue-500 bg-blue-900/20"
                  : "border-slate-700 bg-slate-800 hover:border-slate-600"
              }`}
            >
              <div className="font-medium text-white text-sm">{job.title}</div>
              <div className="text-xs text-slate-400">{job.company} · {job.location}</div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <div className="rounded-2xl border border-blue-700 bg-blue-900/20 p-4 mb-5">
          <div className="text-sm text-blue-300 font-medium">{selected.title}</div>
          <div className="text-xs text-slate-400">{selected.company} · {selected.short_id || selected.id}</div>
        </div>
      )}

      <button
        onClick={forge}
        disabled={!selected || forging}
        className="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold transition disabled:opacity-40"
      >
        {forging ? "Forging... (this takes 15-30s)" : "⚡ Generate Resume"}
      </button>

      {forging && (
        <div className="mt-4 text-center text-slate-400 text-sm animate-pulse">
          Analysing JD · Extracting keywords · Optimising...
        </div>
      )}

      {result && (
        <div className="mt-5">
          {result.error ? (
            <div className="rounded-xl bg-red-900/30 border border-red-800 text-red-300 px-4 py-3 text-sm">
              {result.error}
            </div>
          ) : (
            <div className="rounded-2xl border border-green-700 bg-green-900/20 p-4 text-center">
              <div className="text-2xl mb-2">✅</div>
              <p className="text-green-300 font-medium mb-3">Resume generated!</p>
              {result.pdf_path && (
                <a
                  href={`${apiBase}/resumes/${result.pdf_path.split(/[\\/]/).pop()}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block px-6 py-2 rounded-xl bg-green-700 hover:bg-green-600 text-white text-sm font-medium transition"
                >
                  📥 Download PDF
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
