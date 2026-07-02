"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api, type Job } from "@/lib/api";

const PROFILES = [
  { id: "",                   label: "Auto" },
  // — AI / Tech —
  { id: "genai_engineer",     label: "GenAI Engineer" },
  { id: "ai_developer",       label: "AI Developer" },
  { id: "ml_engineer",        label: "ML Engineer" },
  { id: "data_scientist",     label: "Data Scientist" },
  { id: "bi_developer",       label: "Data Analyst" },
  // — Finance —
  { id: "credit_analyst",     label: "Credit Analyst" },
  { id: "financial_analyst",  label: "Financial Analyst" },
  { id: "quant_analyst",      label: "Quant Analyst" },
  { id: "risk_analyst",       label: "Risk Analyst" },
  { id: "compliance_analyst", label: "Compliance Analyst" },
];

const PROFILE_DISPLAY: Record<string, string> = Object.fromEntries(
  PROFILES.filter(p => p.id).map(p => [p.id, p.label])
);

// Most-specific first — mirrors backend _PROFILE_TAG_MAP
const PROFILE_TAG_MAP: Record<string, string[]> = {
  genai_engineer:    ["genai", "rag", "knowledge_graph", "langchain", "vector_db", "agentic", "graph_rag"],
  ai_developer:      ["ai_engineer", "applied_ai", "nlp", "chatbot", "automation", "dialogflow"],
  ml_engineer:       ["ml", "machine_learning", "machine_learning_engineer", "deep_learning", "pytorch", "tensorflow", "model_training"],
  credit_analyst:    ["credit_risk", "credit_analyst", "underwriting", "lending", "loan_analysis", "credit_scoring"],
  financial_analyst: ["financial_analyst", "financial_reporting", "financial_modeling", "investment", "equity_research", "valuation", "accounting"],
  quant_analyst:     ["quant_analyst", "quantitative", "quantitative_analysis", "statistical_modeling", "econometrics", "actuarial"],
  risk_analyst:      ["risk_analyst", "risk", "risk_management", "market_risk", "operational_risk", "banking"],
  compliance_analyst:["compliance", "regulatory", "aml", "audit", "kyc", "financial_crime"],
  data_scientist:    ["data_scientist", "predictive_modeling", "statistical_analysis"],
  bi_developer:      ["bi_developer", "bi", "data_analyst", "reporting", "dashboard", "visualization", "business_intelligence"],
};

// Keyword sets for description matching
const DESC_KEYWORDS: Record<string, string[]> = {
  genai_engineer:    ["rag", "llm", "langchain", "vector", "embedding", "generative", "knowledge graph", "agentic", "large language"],
  ai_developer:      ["artificial intelligence", "chatbot", "conversational", "nlp", "natural language", "automation", "dialogflow"],
  ml_engineer:       ["machine learning", "deep learning", "pytorch", "tensorflow", "model training", "mlops", "neural network"],
  data_scientist:    ["data scientist", "predictive", "statistical analysis", "eda", "experiment", "hypothesis"],
  bi_developer:      ["data analyst", "dashboard", "power bi", "tableau", "reporting", "business intelligence", "kpi", "sql analyst"],
  credit_analyst:    ["credit", "underwriting", "lending", "loan", "credit risk", "credit scoring", "nbfc"],
  financial_analyst: ["financial analyst", "financial model", "valuation", "equity research", "investment banking", "accounting", "p&l", "10-k"],
  quant_analyst:     ["quantitative", "quant", "statistical model", "algorithmic", "econometrics", "derivatives", "actuar"],
  risk_analyst:      ["risk management", "market risk", "operational risk", "risk framework", "risk officer", "risk assessment"],
  compliance_analyst:["compliance", "regulatory", "aml", "kyc", "audit", "financial crime", "anti-money"],
};

function detectProfile(tags: string[]): { profile: string; display: string; matchedTags: string[] } {
  for (const [prof, ptags] of Object.entries(PROFILE_TAG_MAP)) {
    const hits = tags.filter(t => ptags.includes(t));
    if (hits.length > 0) return { profile: prof, display: PROFILE_DISPLAY[prof] ?? prof, matchedTags: hits };
  }
  return { profile: "default", display: "Default", matchedTags: [] };
}

function matchByDescription(desc: string): { profile: string; display: string } | null {
  const lower = desc.toLowerCase();
  let best = "";
  let bestScore = 0;
  for (const [prof, kws] of Object.entries(DESC_KEYWORDS)) {
    const score = kws.filter(kw => lower.includes(kw)).length;
    if (score > bestScore) { bestScore = score; best = prof; }
  }
  if (bestScore > 0 && best) return { profile: best, display: PROFILE_DISPLAY[best] ?? best };
  return null;
}

type AuditResult   = { score: number; missing_keywords: string[]; red_flags: string[] };
type ForgeResult   = { pdf_path?: string; ats_score?: number; profile_used?: string; error?: string };
type AtsResult     = { ats_pass?: string[]; flagged?: {section:string;issue:string;fix:string}[]; overall_verdict?: string; error?: string };

type ModalState = {
  open: boolean;
  profile: string;        // resolved profile ID
  display: string;        // human label
  matchedTags: string[];  // tags that triggered auto-detect
  source: "auto" | "manual";
  // "change" sub-screen
  changing: boolean;
  descText: string;
  descMatch: { profile: string; display: string } | null; // client-side match result
  descSearched: boolean;  // true after Match button clicked
};

const CLOSED_MODAL: ModalState = {
  open: false, profile: "", display: "", matchedTags: [], source: "auto",
  changing: false, descText: "", descMatch: null, descSearched: false,
};

function ForgePageInner() {
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("job");

  const [jobs, setJobs]           = useState<Job[]>([]);
  const [selected, setSelected]   = useState<Job | null>(null);
  const [profile, setProfile]     = useState("");
  const [loading, setLoading]     = useState(true);
  const [modal, setModal]         = useState<ModalState>(CLOSED_MODAL);

  // Step 1 — Audit
  const [auditing, setAuditing]         = useState(false);
  const [auditResult, setAuditResult]   = useState<AuditResult | null>(null);

  // Step 2+3 — Forge
  const [forging, setForging]           = useState(false);
  const [forgeStatus, setForgeStatus]   = useState("");
  const [forgeResult, setForgeResult]   = useState<ForgeResult | null>(null);

  // Step 3 — ATS check
  const [checkingAts, setCheckingAts]   = useState(false);
  const [atsResult, setAtsResult]       = useState<AtsResult | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL;

  useEffect(() => {
    Promise.all([
      api.jobs({ status: "new",     limit: "50" }),
      api.jobs({ status: "applied", limit: "50" }),
    ])
      .then(([n, a]) => {
        const all = [...n, ...a];
        setJobs(all);
        if (preselectedId) {
          const match = all.find(j => j.id === preselectedId);
          if (match) selectJob(match);
        }
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectJob(job: Job) {
    setSelected(job);
    setAuditResult(null);
    setForgeResult(null);
    setAtsResult(null);
    setModal(CLOSED_MODAL);
  }

  async function runAudit() {
    if (!selected) return;
    setAuditing(true);
    setAuditResult(null);
    try {
      const res = await api.auditResume(selected.short_id || selected.id);
      setAuditResult(res);
    } catch { /* silent — audit is optional pre-step */ }
    setAuditing(false);
  }

  // Opens the confirmation modal before forging
  function openConfirmModal() {
    if (!selected) return;
    if (!profile) {
      // Auto-detect from job tags
      const { profile: det, display: disp, matchedTags } = detectProfile(selected.tags_matched ?? []);
      setModal({ ...CLOSED_MODAL, open: true, profile: det, display: disp, matchedTags, source: "auto" });
    } else {
      // Manual selection — confirm anyway so user can catch a wrong pick
      setModal({ ...CLOSED_MODAL, open: true, profile, display: PROFILE_DISPLAY[profile] ?? profile, matchedTags: [], source: "manual" });
    }
  }

  async function forge(profileOverride: string) {
    if (!selected) return;
    setModal(CLOSED_MODAL);
    setForging(true);
    setForgeResult(null);
    setAtsResult(null);
    setForgeStatus("Waking up server…");
    const useProfile = profileOverride === "default" ? undefined : profileOverride || undefined;
    try {
      try { await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(25_000) }); } catch {}
      setForgeStatus("Analysing JD · Optimising with XYZ format…");
      const res = await api.forge(selected.short_id || selected.id, useProfile, undefined);
      setForgeResult(res);
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : String(e);
      const msg = e instanceof Error && e.name === "AbortError"
        ? "Timed out — try again"
        : `Forge failed: ${raw}`;
      setForgeResult({ error: msg });
    }
    setForgeStatus("");
    setForging(false);
  }

  async function reforgeWithFixes() {
    if (!selected || !atsResult) return;
    setForging(true);
    setForgeResult(null);
    setAtsResult(null);
    setForgeStatus("Re-forging with ATS fixes…");
    const useProfile = profile === "default" ? undefined : profile || undefined;
    try {
      try { await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(25_000) }); } catch {}
      const hints = {
        flagged: atsResult.flagged ?? [],
        missing_keywords: (auditResult?.missing_keywords ?? []),
      };
      const res = await api.forge(selected.short_id || selected.id, useProfile, hints);
      setForgeResult(res);
    } catch (e: unknown) {
      setForgeResult({ error: e instanceof Error ? e.message : "Re-forge failed" });
    }
    setForgeStatus("");
    setForging(false);
  }

  async function runAtsCheck() {
    if (!selected) return;
    setCheckingAts(true);
    setAtsResult(null);
    try {
      const res = await api.atsCheck(selected.short_id || selected.id);
      setAtsResult(res);
    } catch (e: unknown) {
      setAtsResult({ error: e instanceof Error ? e.message : "ATS check failed" });
    }
    setCheckingAts(false);
  }

  function handleDescMatch() {
    const result = matchByDescription(modal.descText);
    setModal(m => ({ ...m, descMatch: result, descSearched: true }));
  }

  const scoreColor = (s: number) =>
    s >= 75 ? "var(--green)" : s >= 55 ? "var(--amber)" : "var(--red)";

  // ── Confirmation bottom sheet ───────────────────────────────────────────────
  const confirmModal = modal.open && (
    <div
      className="fixed inset-0 z-50 flex items-end"
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) setModal(CLOSED_MODAL); }}
    >
      <div className="w-full rounded-t-3xl p-5 pb-10 slide-up"
        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>

        {/* drag handle */}
        <div className="w-10 h-1 rounded-full mx-auto mb-5" style={{ background: "var(--border)" }} />

        {!modal.changing ? (
          /* ── Confirm screen ── */
          <>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>
              {modal.source === "auto" ? "Auto-detected profile" : "Selected profile"}
            </p>

            <div className="flex items-center gap-3 mb-1">
              <span className="px-3 py-1.5 rounded-lg text-sm font-bold"
                style={{ background: "var(--accent-20)", color: "var(--accent)", border: "1px solid var(--accent-40)" }}>
                {modal.display}
              </span>
              {modal.source === "auto" && modal.matchedTags.length > 0 && (
                <span className="text-xs" style={{ color: "var(--text-3)" }}>
                  via: {modal.matchedTags.slice(0, 3).join(", ")}
                </span>
              )}
            </div>

            <p className="text-sm mt-3 mb-5" style={{ color: "var(--text-2)" }}>
              Does <strong style={{ color: "var(--text)" }}>{modal.display}</strong> fit this job?
            </p>

            <div className="flex gap-2">
              <button
                onClick={() => forge(modal.profile)}
                className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                Yes, forge it
              </button>
              <button
                onClick={() => setModal(m => ({ ...m, changing: true }))}
                className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
                No, change it
              </button>
            </div>
          </>
        ) : (
          /* ── Change-profile screen ── */
          <>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>
              Choose a profile
            </p>

            {/* Profile pills (excluding Auto) */}
            <div className="flex flex-wrap gap-2 mb-4">
              {PROFILES.filter(p => p.id).map(p => {
                const active = modal.profile === p.id;
                return (
                  <button key={p.id}
                    onClick={() => setModal(m => ({ ...m, profile: p.id, display: p.label, descMatch: null }))}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold transition active:scale-95"
                    style={{
                      background: active ? "var(--accent-20)" : "var(--surface-2)",
                      color: active ? "var(--accent)" : "var(--text-3)",
                      border: `1px solid ${active ? "var(--accent-40)" : "var(--border)"}`,
                    }}>
                    {p.label}
                  </button>
                );
              })}
            </div>

            {/* Describe the role */}
            <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--text-3)" }}>
              Or describe the role — we'll find the closest match:
            </p>
            <div className="flex gap-2 mb-3">
              <input
                value={modal.descText}
                onChange={e => setModal(m => ({ ...m, descText: e.target.value, descMatch: null, descSearched: false }))}
                onKeyDown={e => e.key === "Enter" && handleDescMatch()}
                placeholder="e.g. Backend engineer building REST APIs…"
                style={{ fontSize: 13 }}
              />
              <button
                onClick={handleDescMatch}
                disabled={!modal.descText.trim()}
                className="px-3 py-2 rounded-xl text-xs font-semibold shrink-0 disabled:opacity-40 transition active:scale-95"
                style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
                Match
              </button>
            </div>

            {/* Description match result */}
            {modal.descSearched && modal.descMatch === null && (
              <div className="rounded-xl p-3 mb-3"
                style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}>
                <p className="text-xs" style={{ color: "#fca5a5" }}>
                  No matching profile found. Pick one above, or continue with Default (general resume).
                </p>
              </div>
            )}
            {modal.descMatch && (
              <div className="rounded-xl p-3 mb-3"
                style={{ background: "var(--accent-05)", border: "1px solid var(--accent-15)" }}>
                <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--accent)" }}>
                  Closest match: {modal.descMatch.display}
                </p>
                <button
                  onClick={() => setModal(m => ({ ...m, profile: m.descMatch!.profile, display: m.descMatch!.display }))}
                  className="text-xs font-semibold mt-1"
                  style={{ color: "var(--accent)" }}>
                  Apply this profile →
                </button>
              </div>
            )}

            <div className="flex gap-2 mt-1">
              <button
                onClick={() => forge(modal.profile || "default")}
                className="flex-1 py-3 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
                Forge with {modal.display || "Default"}
              </button>
              <button
                onClick={() => setModal(m => ({ ...m, changing: false, descText: "", descMatch: null, descSearched: false }))}
                className="py-3 px-4 rounded-xl text-sm font-semibold transition active:scale-95"
                style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
                Back
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div className="pt-6 pb-4 fade-up">
      <h1 className="mb-0.5" style={{ color: "var(--text)" }}>Resume Forge</h1>
      <p className="text-sm mb-5" style={{ color: "var(--text-3)" }}>
        3-step ATS optimisation · XYZ format · recruiter simulation
      </p>

      {/* ── Job selector ── */}
      <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: "var(--text-3)" }}>
        1 · Select a job
      </p>
      {loading ? (
        <div className="space-y-2 mb-4">{[1,2,3].map(i => <div key={i} className="skeleton h-14 rounded-xl"/>)}</div>
      ) : jobs.length === 0 ? (
        <div className="card p-5 text-center mb-4">
          <p className="text-sm" style={{ color: "var(--text-3)" }}>No jobs found. Scout or import first.</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-52 overflow-y-auto no-scrollbar mb-4">
          {jobs.map(job => {
            const active = selected?.id === job.id;
            return (
              <button key={job.id} onClick={() => selectJob(job)}
                className="w-full text-left card card-press px-4 py-3"
                style={{ background: active ? "var(--accent-10)" : "var(--surface)", borderColor: active ? "var(--accent-40)" : "var(--border)" }}>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
                    style={{ background: active ? "var(--accent-20)" : "var(--surface-2)", color: active ? "var(--accent)" : "var(--text-3)" }}>
                    {job.company?.charAt(0)?.toUpperCase() ?? "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate" style={{ color: "var(--text)" }}>{job.title}</div>
                    <div className="text-xs truncate" style={{ color: "var(--text-3)" }}>{job.company}{job.location ? ` · ${job.location}` : ""}</div>
                  </div>
                  {active && <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 shrink-0" style={{ color: "var(--accent)" }}><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Step 2: Audit ── */}
      {selected && (
        <>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: "var(--text-3)" }}>
            2 · Check fit before generating
          </p>
          <button onClick={runAudit} disabled={auditing}
            className="w-full py-3 rounded-xl text-sm font-semibold transition active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 mb-3"
            style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
            {auditing
              ? <><svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/></svg>Scoring…</>
              : <><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3" strokeLinecap="round"/></svg>Audit My Fit</>
            }
          </button>

          {auditResult && auditResult.score >= 0 && (
            <div className="rounded-2xl p-4 mb-4"
              style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-14 h-14 rounded-full flex items-center justify-center shrink-0"
                  style={{ background: `${scoreColor(auditResult.score)}18`, border: `2px solid ${scoreColor(auditResult.score)}` }}>
                  <span className="text-lg font-bold mono" style={{ color: scoreColor(auditResult.score) }}>
                    {auditResult.score}
                  </span>
                </div>
                <div>
                  <p className="font-semibold text-sm" style={{ color: "var(--text)" }}>Resume–JD Fit Score</p>
                  <p className="text-xs" style={{ color: "var(--text-3)" }}>
                    {auditResult.score >= 75 ? "Strong match — generate now" :
                     auditResult.score >= 55 ? "Decent match — forge will close gaps" :
                     "Weak match — forge will optimise keywords"}
                  </p>
                </div>
              </div>

              {auditResult.missing_keywords?.length > 0 && (
                <div className="mb-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "var(--text-3)" }}>
                    Top missing keywords
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {auditResult.missing_keywords.map(kw => (
                      <span key={kw} className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: "rgba(239,68,68,0.08)", color: "#fca5a5", border: "1px solid rgba(239,68,68,0.2)" }}>
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {auditResult.red_flags?.length > 0 && (
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest mb-1.5" style={{ color: "var(--text-3)" }}>
                    Red flags to fix
                  </p>
                  <ul className="space-y-1">
                    {auditResult.red_flags.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs" style={{ color: "var(--text-2)" }}>
                        <span style={{ color: "#f59e0b" }}>⚠</span> {f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Step 3: Profile selector ── */}
      {selected && (
        <>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color: "var(--text-3)" }}>
            3 · Resume profile
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {PROFILES.map(p => {
              const active = profile === p.id;
              return (
                <button key={p.id} onClick={() => setProfile(p.id)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition active:scale-95"
                  style={{
                    background: active ? "var(--accent-20)" : "var(--surface-2)",
                    color: active ? "var(--accent)" : "var(--text-3)",
                    border: `1px solid ${active ? "var(--accent-40)" : "var(--border)"}`,
                  }}>
                  {p.label}
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* ── Generate button (opens confirmation modal) ── */}
      <button onClick={openConfirmModal} disabled={!selected || forging}
        className="w-full py-3.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-40 flex items-center justify-center gap-2"
        style={{ background: "var(--accent)", color: "var(--on-accent)", boxShadow: selected ? "0 0 18px var(--accent-25)" : "none" }}>
        {forging
          ? <><svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/></svg>Forging…</>
          : <><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Generate {profile ? PROFILES.find(p=>p.id===profile)?.label : "Auto"} Resume</>
        }
      </button>
      {forging && (
        <p className="text-xs text-center mt-2" style={{ color: "var(--text-3)" }}>
          {forgeStatus || "Optimising bullets in XYZ format…"}
        </p>
      )}

      {/* ── Forge result ── */}
      {forgeResult && (
        <div className="mt-4">
          {forgeResult.error ? (
            <div className="card p-4 flex gap-3"
              style={{ borderColor: "rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.06)" }}>
              <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "#ef4444" }}>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
              </svg>
              <p className="text-sm" style={{ color: "#fca5a5" }}>{forgeResult.error}</p>
            </div>
          ) : (
            <div className="card p-5"
              style={{ borderColor: "rgba(34,197,94,0.3)", background: "rgba(34,197,94,0.06)" }}>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
                  style={{ background: "rgba(34,197,94,0.15)" }}>
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5" style={{ color: "#22c55e" }}>
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                  </svg>
                </div>
                <div>
                  <p className="font-semibold text-sm" style={{ color: "#86efac" }}>Resume generated!</p>
                  {forgeResult.profile_used && (
                    <p className="text-xs" style={{ color: "var(--text-3)" }}>Profile: {forgeResult.profile_used}</p>
                  )}
                </div>
                {forgeResult.ats_score !== undefined && forgeResult.ats_score >= 0 && (
                  <span className="ml-auto text-sm font-bold mono" style={{ color: "var(--accent)" }}>
                    ATS {forgeResult.ats_score}%
                  </span>
                )}
              </div>

              <div className="flex gap-2">
                {forgeResult.pdf_path && (
                  <a href={`${apiBase}/resumes/${forgeResult.pdf_path.split(/[\\/]/).pop()}`}
                    target="_blank" rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition active:scale-95"
                    style={{ background: "rgba(34,197,94,0.15)", color: "#86efac", border: "1px solid rgba(34,197,94,0.3)" }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" strokeLinecap="round"/>
                      <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    Download PDF
                  </a>
                )}
                <button onClick={runAtsCheck} disabled={checkingAts}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition active:scale-95 disabled:opacity-50"
                  style={{ background: "var(--accent-10)", color: "var(--accent)", border: "1px solid var(--accent-25)" }}>
                  {checkingAts
                    ? <><svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/></svg>Checking…</>
                    : <><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M9 12l2 2 4-4"/><path d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z" strokeLinecap="round"/></svg>ATS Check</>
                  }
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── ATS Check result ── */}
      {atsResult && (
        <div className="mt-3 rounded-2xl p-4"
          style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>
            ATS + Hiring Manager Report
          </p>

          {atsResult.error ? (
            <p className="text-sm" style={{ color: "#fca5a5" }}>{atsResult.error}</p>
          ) : (
            <>
              {atsResult.ats_pass && atsResult.ats_pass.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-semibold mb-1.5" style={{ color: "var(--green)" }}>✅ ATS passes</p>
                  <div className="flex flex-wrap gap-1.5">
                    {atsResult.ats_pass.map(s => (
                      <span key={s} className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: "rgba(34,197,94,0.10)", color: "#86efac", border: "1px solid rgba(34,197,94,0.2)" }}>
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {atsResult.flagged && atsResult.flagged.length > 0 && (
                <div className="mb-3 space-y-2">
                  <p className="text-xs font-semibold" style={{ color: "var(--amber)" }}>⚠ Flagged sections</p>
                  {atsResult.flagged.map((f, i) => (
                    <div key={i} className="rounded-xl p-3"
                      style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.2)" }}>
                      <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--amber)" }}>{f.section}</p>
                      <p className="text-xs mb-1" style={{ color: "var(--text-2)" }}>{f.issue}</p>
                      {f.fix && <p className="text-xs italic" style={{ color: "var(--text-3)" }}>→ {f.fix}</p>}
                    </div>
                  ))}
                </div>
              )}

              {atsResult.overall_verdict && (
                <div className="rounded-xl p-3 mb-3"
                  style={{ background: "var(--accent-05)", border: "1px solid var(--accent-15)" }}>
                  <p className="text-xs font-semibold mb-0.5" style={{ color: "var(--accent)" }}>Verdict</p>
                  <p className="text-xs" style={{ color: "var(--text-2)" }}>{atsResult.overall_verdict}</p>
                </div>
              )}

              {atsResult.flagged && atsResult.flagged.length > 0 && (
                <button onClick={reforgeWithFixes} disabled={forging}
                  className="w-full py-3 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                  style={{ background: "var(--blue-20)", color: "var(--blue-l)", border: "1px solid var(--blue-20)" }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                    <path d="M23 4v6h-6M1 20v-6h6" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Re-forge with ATS Fixes Applied
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Profile confirmation modal ── */}
      {confirmModal}
    </div>
  );
}

export default function ForgePage() {
  return (
    <Suspense>
      <ForgePageInner />
    </Suspense>
  );
}
