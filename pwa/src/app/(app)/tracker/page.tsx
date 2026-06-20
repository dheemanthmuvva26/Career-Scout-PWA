"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Job } from "@/lib/api";
import JobCard from "@/components/JobCard";

const COLUMNS = [
  { label: "Applied",   status: "applied",   color: "text-blue-400" },
  { label: "Interview", status: "interview",  color: "text-purple-400" },
  { label: "Offer",     status: "offer",      color: "text-green-400" },
  { label: "Rejected",  status: "rejected",   color: "text-red-400" },
  { label: "Ghosted",   status: "ghosted",    color: "text-slate-400" },
];

export default function TrackerPage() {
  const [col, setCol] = useState("applied");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const loadAll = useCallback(async () => {
    try {
      const results = await Promise.all(
        COLUMNS.map((c) => api.jobs({ status: c.status, limit: "100" }))
      );
      const map: Record<string, number> = {};
      COLUMNS.forEach((c, i) => { map[c.status] = results[i].length; });
      setCounts(map);
      const active = COLUMNS.findIndex((c) => c.status === col);
      setJobs(results[active] || []);
    } catch {}
    setLoading(false);
  }, [col]);

  const loadCol = useCallback(async (status: string) => {
    setLoading(true);
    try {
      const data = await api.jobs({ status, limit: "100" });
      setJobs(Array.isArray(data) ? data : []);
    } catch {}
    setLoading(false);
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadAll(); }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadCol(col); }, [col]);

  function handleUpdate(id: string, changes: Partial<Job>) {
    if (changes.status && changes.status !== col) {
      setJobs((prev) => prev.filter((j) => j.id !== id));
    } else {
      setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...changes } : j)));
    }
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="px-4 pt-6 pb-3">
        <h1 className="text-xl font-bold text-white mb-4">Application Tracker</h1>

        {/* Column tabs with counts */}
        <div className="flex gap-1 overflow-x-auto no-scrollbar">
          {COLUMNS.map((c) => (
            <button
              key={c.status}
              onClick={() => setCol(c.status)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition ${
                col === c.status
                  ? "bg-slate-700 text-white"
                  : "bg-slate-800/50 text-slate-500 hover:text-white"
              }`}
            >
              <span className={col === c.status ? c.color : ""}>{c.label}</span>
              {counts[c.status] !== undefined && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${col === c.status ? "bg-slate-600 text-white" : "bg-slate-800 text-slate-500"}`}>
                  {counts[c.status]}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4">
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="rounded-2xl border border-slate-700 p-4 animate-pulse" style={{ background: "var(--card)" }}>
                <div className="h-3 bg-slate-700 rounded w-1/3 mb-2" />
                <div className="h-4 bg-slate-700 rounded w-2/3" />
              </div>
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-16 text-slate-500">
            <div className="text-4xl mb-3">📭</div>
            <p>No {col} applications yet.</p>
          </div>
        ) : (
          jobs.map((job) => (
            <JobCard key={job.id} job={job} onUpdate={handleUpdate} compact />
          ))
        )}
      </div>
    </div>
  );
}
