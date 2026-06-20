"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Job } from "@/lib/api";
import JobCard from "@/components/JobCard";

const TABS = [
  { label: "New",       status: "new" },
  { label: "Applied",   status: "applied" },
  { label: "Interview", status: "interview" },
  { label: "Offer",     status: "offer" },
];

export default function JobsPage() {
  const [tab, setTab] = useState("new");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.jobs({ status: tab, limit: "50" });
      setJobs(Array.isArray(data) ? data : []);
    } catch {
      setError("Failed to load jobs. Is the API reachable?");
    }
    setLoading(false);
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  function handleUpdate(id: string, changes: Partial<Job>) {
    setJobs((prev) =>
      prev.map((j) => (j.id === id ? { ...j, ...changes } : j))
        .filter((j) => j.status === tab || tab === "new")
    );
    // Remove from feed if status changed away from current tab
    if (changes.status && changes.status !== tab) {
      setJobs((prev) => prev.filter((j) => j.id !== id));
    }
  }

  async function handleImport() {
    if (!importUrl.trim()) return;
    setImporting(true);
    try {
      await api.importJob(importUrl.trim());
      setImportUrl("");
      if (tab === "new") load();
    } catch {}
    setImporting(false);
  }

  return (
    <div className="max-w-lg mx-auto">
      {/* Header */}
      <div className="px-4 pt-6 pb-3">
        <h1 className="text-xl font-bold text-white mb-3">Job Feed</h1>

        {/* Import bar */}
        <div className="flex gap-2 mb-3">
          <input
            value={importUrl}
            onChange={(e) => setImportUrl(e.target.value)}
            placeholder="Paste LinkedIn job URL..."
            className="flex-1 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleImport}
            disabled={importing || !importUrl.trim()}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition disabled:opacity-50"
          >
            {importing ? "..." : "Import"}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 overflow-x-auto no-scrollbar">
          {TABS.map((t) => (
            <button
              key={t.status}
              onClick={() => setTab(t.status)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition ${
                tab === t.status
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Job list */}
      <div className="px-4">
        {error && (
          <div className="rounded-xl bg-red-900/30 border border-red-800 text-red-300 px-4 py-3 text-sm mb-3">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-2xl border border-slate-700 p-4 animate-pulse" style={{ background: "var(--card)" }}>
                <div className="h-3 bg-slate-700 rounded w-1/3 mb-2" />
                <div className="h-4 bg-slate-700 rounded w-2/3 mb-2" />
                <div className="h-3 bg-slate-700 rounded w-1/4" />
              </div>
            ))}
          </div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-16 text-slate-500">
            <div className="text-4xl mb-3">🎯</div>
            <p>No {tab} jobs right now.</p>
            {tab === "new" && (
              <p className="text-sm mt-1">Try tapping Scout on the dashboard.</p>
            )}
          </div>
        ) : (
          jobs.map((job) => (
            <JobCard key={job.id} job={job} onUpdate={handleUpdate} />
          ))
        )}
      </div>
    </div>
  );
}
