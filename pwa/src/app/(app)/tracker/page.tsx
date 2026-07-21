"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Job } from "@/lib/api";
import JobCard from "@/components/JobCard";
import SearchBar from "@/components/SearchBar";

const COLUMNS = [
  { label: "Applied",   status: "applied",   color: "#60a5fa" },
  { label: "Interview", status: "interview",  color: "#a855f7" },
  { label: "Offer",     status: "offer",      color: "#22c55e" },
  { label: "Rejected",  status: "rejected",   color: "#ef4444" },
  { label: "Ghosted",   status: "ghosted",    color: "#52525b" },
];

export default function TrackerPage() {
  const [col, setCol]     = useState("applied");
  const [jobs, setJobs]   = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [counts, setCounts]   = useState<Record<string, number>>({});
  const [search, setSearch]   = useState("");

  const loadAll = useCallback(async () => {
    try {
      const results = await Promise.all(COLUMNS.map((c) => api.jobs({ status: c.status, limit: "100" })));
      const map: Record<string, number> = {};
      COLUMNS.forEach((c, i) => { map[c.status] = results[i].length; });
      setCounts(map);
      const idx = COLUMNS.findIndex((c) => c.status === col);
      setJobs(results[idx] || []);
    } catch {}
    setLoading(false);
  }, [col]);

  const loadCol = useCallback(async (status: string) => {
    setLoading(true);
    try { setJobs(await api.jobs({ status, limit: "100" })); } catch {}
    setLoading(false);
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadAll(); }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadCol(col); }, [col]);

  function handleUpdate(id: string, changes: Partial<Job>) {
    if (changes.status && changes.status !== col) {
      setJobs((p) => p.filter((j) => j.id !== id));
    } else {
      setJobs((p) => p.map((j) => (j.id === id ? { ...j, ...changes } : j)));
    }
  }

  const active = COLUMNS.find((c) => c.status === col);

  const filteredJobs = jobs.filter((j) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return j.title?.toLowerCase().includes(q)
      || j.company?.toLowerCase().includes(q)
      || j.location?.toLowerCase().includes(q);
  });

  return (
    <div className="pt-8 pb-4 fade-up">
      <h1 className="mb-1" style={{ color: "var(--text)" }}>Tracker</h1>
      <p className="text-sm mb-5" style={{ color: "var(--text-3)" }}>Manage your application pipeline</p>

      {/* Tab strip */}
      <div className="flex gap-1.5 overflow-x-auto no-scrollbar mb-5">
        {COLUMNS.map((c) => {
          const isActive = col === c.status;
          return (
            <button key={c.status} onClick={() => setCol(c.status)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition active:scale-95"
              style={{
                background: isActive ? `${c.color}15` : "var(--surface-2)",
                color: isActive ? c.color : "var(--text-3)",
                border: `1px solid ${isActive ? c.color + "35" : "var(--border)"}`,
              }}>
              {c.label}
              {counts[c.status] !== undefined && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full min-w-5 text-center"
                  style={{ background: isActive ? `${c.color}25` : "var(--border)", color: isActive ? c.color : "var(--text-3)" }}>
                  {counts[c.status]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Column header */}
      {active && (
        <div className="flex items-center gap-2 mb-4">
          <div className="w-2 h-2 rounded-full" style={{ background: active.color }} />
          <span className="text-sm font-semibold" style={{ color: active.color }}>{active.label}</span>
          <span className="text-xs ml-auto" style={{ color: "var(--text-3)" }}>
            {counts[col] ?? 0} application{(counts[col] ?? 0) !== 1 ? "s" : ""}
          </span>
        </div>
      )}

      <SearchBar value={search} onChange={setSearch} placeholder="Search title, company, location…" className="mb-4" />

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="card p-4">
              <div className="flex gap-3 mb-3">
                <div className="skeleton w-10 h-10 rounded-xl" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-3 w-1/3 rounded" />
                  <div className="skeleton h-4 w-2/3 rounded" />
                </div>
              </div>
              <div className="skeleton h-8 rounded-xl" />
            </div>
          ))}
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-3">📭</div>
          <p className="font-medium" style={{ color: "var(--text-2)" }}>
            {search.trim() ? "No applications match your search" : `No ${col} applications`}
          </p>
          {!search.trim() && (
            <p className="text-sm mt-1" style={{ color: "var(--text-3)" }}>
              {col === "applied" ? "Apply to jobs from the Jobs tab" : `No applications moved to ${col} yet`}
            </p>
          )}
        </div>
      ) : (
        filteredJobs.map((job) => <JobCard key={job.id} job={job} onUpdate={handleUpdate} compact />)
      )}
    </div>
  );
}
