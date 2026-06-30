"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Job } from "@/lib/api";
import JobCard from "@/components/JobCard";
import PullToRefresh from "@/components/PullToRefresh";

const TABS = [
  { label: "New",       status: "new",       color: "#f59e0b" },
  { label: "Applied",   status: "applied",   color: "#60a5fa" },
  { label: "Interview", status: "interview", color: "#a855f7" },
  { label: "Offer",     status: "offer",     color: "#22c55e" },
];

export default function JobsPage() {
  const [tab, setTab]           = useState("new");
  const [jobs, setJobs]         = useState<Job[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [importMode, setImportMode] = useState<"url" | "paste">("url");
  const [importUrl, setImportUrl] = useState("");
  const [importText, setImportText] = useState("");
  const [importLocation, setImportLocation] = useState("");
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const data = await api.jobs({ status: tab, limit: "50" });
      setJobs(Array.isArray(data) ? data : []);
    } catch { setError("Failed to load jobs."); }
    setLoading(false);
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  function handleUpdate(id: string, changes: Partial<Job>) {
    if (changes.status && changes.status !== tab) {
      setJobs((p) => p.filter((j) => j.id !== id));
    } else {
      setJobs((p) => p.map((j) => j.id === id ? { ...j, ...changes } : j));
    }
  }

  async function handleImport() {
    const isPaste = importMode === "paste";
    if (isPaste ? !importText.trim() : !importUrl.trim()) return;
    setImporting(true); setImportMsg("");
    try {
      const res = isPaste
        ? await api.importJobText(importText.trim(), importLocation.trim() || undefined)
        : await api.importJob(importUrl.trim(), importLocation.trim() || undefined);
      setImportUrl("");
      setImportText("");
      setImportLocation("");
      setImportMsg(res?.action === "already_saved" ? "Already in your jobs — refreshing…" : "Imported! Refreshing…");
      if (tab === "new") load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Import failed.";
      setImportMsg(msg.replace(/^API.*→ \d+: /, ""));
    }
    setImporting(false);
    setTimeout(() => setImportMsg(""), 5000);
  }

  return (
    <PullToRefresh onRefresh={load}>
    <div className="pt-8 pb-4 fade-up">
      {/* Header */}
      <h1 className="mb-1" style={{ color: "var(--text)" }}>Job Feed</h1>
      <p className="text-sm mb-5" style={{ color: "var(--text-3)" }}>Browse, filter, and import listings</p>

      {/* Import bar */}
      <div className="card p-3 mb-5">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold" style={{ color: "var(--text-3)" }}>IMPORT JOB</p>
          <div className="flex gap-1 rounded-lg p-0.5" style={{ background: "var(--surface-2)" }}>
            {(["url", "paste"] as const).map((m) => (
              <button key={m} onClick={() => setImportMode(m)}
                className="px-2.5 py-1 rounded-md text-[11px] font-semibold transition active:scale-95"
                style={{
                  background: importMode === m ? "var(--accent)" : "transparent",
                  color: importMode === m ? "var(--on-accent)" : "var(--text-3)",
                }}>
                {m === "url" ? "URL" : "Paste text"}
              </button>
            ))}
          </div>
        </div>

        {importMode === "url" ? (
          <div className="flex gap-2 mb-2">
            <input value={importUrl} onChange={(e) => setImportUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleImport()}
              placeholder="LinkedIn, company site, or ATS job URL…"
              style={{ fontSize: 14 }} />
            <button onClick={handleImport} disabled={importing || !importUrl.trim()}
              className="px-4 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-50 transition active:scale-95"
              style={{ background: "var(--accent)", color: "var(--on-accent)", minWidth: 72 }}>
              {importing ? "…" : "Import"}
            </button>
          </div>
        ) : (
          <div className="mb-2">
            <textarea value={importText} onChange={(e) => setImportText(e.target.value)}
              placeholder="Paste a job post from WhatsApp, LinkedIn, email — anything. We'll extract the details automatically."
              rows={4}
              className="w-full resize-none no-scrollbar"
              style={{ fontSize: 14, padding: "10px 12px", borderRadius: 12, lineHeight: 1.5 }} />
            <button onClick={handleImport} disabled={importing || !importText.trim()}
              className="w-full mt-2 py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50 transition active:scale-95"
              style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
              {importing ? "Extracting…" : "Import from pasted text"}
            </button>
          </div>
        )}

        <input value={importLocation} onChange={(e) => setImportLocation(e.target.value)}
          placeholder="Location override (optional — e.g. Mumbai, Bengaluru)"
          style={{ fontSize: 13, padding: "8px 12px", borderRadius: 10 }} />
        {importMsg && (
          <p className="text-xs mt-2" style={{ color: importMsg.includes("failed") || importMsg.includes("Could not") ? "#fca5a5" : "var(--text-2)" }}>
            {importMsg}
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto no-scrollbar mb-4">
        {TABS.map((t) => {
          const active = tab === t.status;
          return (
            <button key={t.status} onClick={() => setTab(t.status)}
              className="px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap transition active:scale-95"
              style={{
                background: active ? `${t.color}18` : "var(--surface-2)",
                color: active ? t.color : "var(--text-3)",
                border: `1px solid ${active ? t.color + "40" : "var(--border)"}`,
              }}>
              {t.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="rounded-xl px-4 py-3 text-sm mb-4"
          style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
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
      ) : jobs.length === 0 ? (
        <div className="text-center py-20">
          <div className="text-4xl mb-3">🎯</div>
          <p className="font-medium mb-1" style={{ color: "var(--text-2)" }}>No {tab} jobs</p>
          {tab === "new" && (
            <p className="text-sm" style={{ color: "var(--text-3)" }}>Run Scout from the dashboard to find new listings</p>
          )}
        </div>
      ) : (
        jobs.map((job) => <JobCard key={job.id} job={job} onUpdate={handleUpdate} />)
      )}
    </div>
    </PullToRefresh>
  );
}
