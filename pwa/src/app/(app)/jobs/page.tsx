"use client";

import { useEffect, useState, useCallback, useRef } from "react";
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
  // Default: paste (best for mobile copy-paste); persisted across sessions
  const [importMode, setImportMode] = useState<"url" | "paste" | "batch">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("cs_importMode") as "url" | "paste" | "batch") || "paste";
    }
    return "paste";
  });
  const [importUrl, setImportUrl] = useState("");
  const [importText, setImportText] = useState("");
  const [importLocation, setImportLocation] = useState("");
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState("");

  // Batch mode
  const [batchUrls, setBatchUrls] = useState("");
  const [batchProfile, setBatchProfile] = useState("auto");
  const [batchRunning, setBatchRunning] = useState(false);
  type BatchEntry = {
    url: string;
    import_status?: string;
    job_id?: string;
    title?: string;
    company?: string;
    forge_token?: string;
    forge_status?: string;
    ats_score?: number;
    error?: string;
  };
  const [batchResults, setBatchResults] = useState<BatchEntry[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  async function handleBatch() {
    const urls = batchUrls.split("\n").map(u => u.trim()).filter(Boolean);
    if (!urls.length) return;
    setBatchRunning(true);
    setBatchResults(urls.map(url => ({ url, import_status: "importing…" })));

    let entries: BatchEntry[] = [];
    try {
      const res = await api.batchImport(urls, batchProfile, importLocation || undefined);
      entries = res.results as BatchEntry[];
      setBatchResults(entries);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Batch failed";
      setBatchResults(urls.map(url => ({ url, error: msg })));
      setBatchRunning(false);
      return;
    }

    // Poll forge tokens until all done
    const pending = () => entries.filter(e => e.forge_token && e.forge_status === "pending");
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      const stillPending = pending();
      if (!stillPending.length) {
        clearInterval(pollRef.current!);
        setBatchRunning(false);
        load();
        return;
      }
      await Promise.all(stillPending.map(async (entry) => {
        try {
          const poll = await api.forgePoll(entry.forge_token!);
          if (poll.status === "done") {
            entries = entries.map(e =>
              e.forge_token === entry.forge_token
                ? { ...e, forge_status: "done", ats_score: poll.ats_score, error: poll.error }
                : e
            );
            setBatchResults([...entries]);
          }
        } catch {}
      }));
    }, 4000);
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
            {(["paste", "url", "batch"] as const).map((m) => (
              <button key={m} onClick={() => { setImportMode(m); localStorage.setItem("cs_importMode", m); }}
                className="px-2.5 py-1 rounded-md text-[11px] font-semibold transition active:scale-95"
                style={{
                  background: importMode === m ? "var(--accent)" : "transparent",
                  color: importMode === m ? "var(--on-accent)" : "var(--text-3)",
                }}>
                {m === "url" ? "URL" : m === "paste" ? "Paste" : "Batch"}
              </button>
            ))}
          </div>
        </div>

        {importMode === "url" && (
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
        )}

        {importMode === "paste" && (
          <div className="mb-2">
            <p className="text-[10px] font-semibold mb-1.5" style={{ color: "var(--text-3)" }}>
              Copy the job post → long-press here → Paste
            </p>
            <textarea value={importText} onChange={(e) => setImportText(e.target.value)}
              placeholder="Paste a job post from WhatsApp, LinkedIn, Telegram, email — anything. We'll extract the details automatically."
              rows={6}
              className="w-full resize-none no-scrollbar"
              style={{ fontSize: 14, padding: "12px 14px", borderRadius: 12, lineHeight: 1.6 }} />
            <button onClick={handleImport} disabled={importing || !importText.trim()}
              className="w-full mt-2 py-3 rounded-xl text-sm font-semibold disabled:opacity-50 transition active:scale-95 flex items-center justify-center gap-2"
              style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
              {importing
                ? <><svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/></svg>Extracting…</>
                : <><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" strokeLinecap="round"/></svg>Import Job</>}
            </button>
          </div>
        )}

        {importMode === "batch" && (
          <div>
            <textarea
              value={batchUrls}
              onChange={(e) => setBatchUrls(e.target.value)}
              placeholder={"Paste one job URL per line:\nhttps://unstop.com/...\nhttps://linkedin.com/jobs/...\nhttps://greenhouse.io/..."}
              rows={5}
              className="w-full resize-none no-scrollbar mb-2"
              style={{ fontSize: 13, padding: "10px 12px", borderRadius: 12, lineHeight: 1.6 }}
            />
            <div className="flex gap-2 mb-2">
              <select
                value={batchProfile}
                onChange={(e) => setBatchProfile(e.target.value)}
                className="flex-1 rounded-xl text-sm"
                style={{ padding: "8px 12px", background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}
              >
                <option value="auto">Auto-detect profile</option>
                <optgroup label="AI / Tech">
                  <option value="genai_engineer">GenAI Engineer</option>
                  <option value="ai_developer">AI Developer</option>
                  <option value="ml_engineer">ML Engineer</option>
                  <option value="data_scientist">Data Scientist</option>
                  <option value="bi_developer">Data Analyst</option>
                </optgroup>
                <optgroup label="Finance">
                  <option value="credit_analyst">Credit Analyst</option>
                  <option value="financial_analyst">Financial Analyst</option>
                  <option value="quant_analyst">Quant Analyst</option>
                  <option value="risk_analyst">Risk Analyst</option>
                  <option value="compliance_analyst">Compliance Analyst</option>
                </optgroup>
                <option value="default">Default</option>
              </select>
              <button
                onClick={handleBatch}
                disabled={batchRunning || !batchUrls.trim()}
                className="px-4 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-50 transition active:scale-95"
                style={{ background: "var(--accent)", color: "var(--on-accent)", minWidth: 100 }}
              >
                {batchRunning ? "Running…" : "Import & Forge"}
              </button>
            </div>
            {batchResults.length > 0 && (
              <div className="mt-1 space-y-1.5">
                {batchResults.map((entry, i) => {
                  const isDone = entry.forge_status === "done";
                  const isErr = !!entry.error;
                  const isImporting = !entry.job_id && !isErr;
                  const isForging = entry.job_id && entry.forge_status === "pending";
                  const icon = isErr ? "✗" : isDone ? "✓" : isImporting ? "⋯" : "↻";
                  const iconColor = isErr ? "#fca5a5" : isDone ? "#4ade80" : "var(--accent)";
                  return (
                    <div key={i} className="flex items-start gap-2 rounded-xl px-3 py-2"
                      style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
                      <span className="text-sm font-bold mt-0.5 w-4 shrink-0" style={{ color: iconColor }}>{icon}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold truncate" style={{ color: "var(--text)" }}>
                          {entry.title ? `${entry.company} — ${entry.title}` : entry.url.replace(/https?:\/\//, "").slice(0, 50)}
                        </p>
                        <p className="text-[11px] mt-0.5" style={{ color: isErr ? "#fca5a5" : "var(--text-3)" }}>
                          {isErr ? entry.error
                            : isImporting ? "Importing…"
                            : isForging ? `Forging resume…`
                            : isDone && entry.ats_score ? `Done — ATS ${entry.ats_score}%`
                            : isDone ? "Done"
                            : entry.import_status}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {importMode !== "batch" && (
          <input value={importLocation} onChange={(e) => setImportLocation(e.target.value)}
            placeholder="Location override (optional — e.g. Mumbai, Bengaluru)"
            style={{ fontSize: 13, padding: "8px 12px", borderRadius: 10 }} />
        )}
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
