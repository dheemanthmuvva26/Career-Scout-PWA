"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL;

function ShareHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [phase, setPhase] = useState<"waking" | "importing" | "paste-fallback" | "pasting" | "success" | "error">("waking");
  const [jobUrl, setJobUrl] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function run() {
      const raw =
        searchParams.get("url") ||
        searchParams.get("text") ||
        searchParams.get("title") ||
        "";
      const match = raw.match(/https?:\/\/[^\s]+/);
      const url = match ? match[0].replace(/[.,;!?]$/, "") : raw.trim();
      setJobUrl(url);

      if (!url) {
        setMessage("No URL found in the shared content.");
        setPhase("error");
        return;
      }

      // This route never mounts the app shell's keep-alive pinger, so on
      // Render's free tier the backend is very often asleep when a share
      // lands here — wake it up first so the real import doesn't just hang.
      try {
        await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(45_000) });
      } catch {}

      setPhase("importing");
      try {
        await api.importJob(url);
        setPhase("success");
        setMessage("Job saved to your feed.");
        setTimeout(() => router.replace("/jobs"), 2200);
      } catch {
        // Scraping failed (JS-rendered sites like Unstop) — show paste fallback
        setPhase("paste-fallback");
      }
    }
    run();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function importFromPaste() {
    if (!pasteText.trim()) return;
    setPhase("pasting");
    try {
      await api.importJobText(pasteText.trim());
      setPhase("success");
      setMessage("Job saved from pasted text.");
      setTimeout(() => router.replace("/jobs"), 2200);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "";
      setMessage(msg || "Import failed — try again.");
      setPhase("error");
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 safe-top"
      style={{ background: "var(--bg)" }}>

      {/* ── Waking server (Render free-tier cold start) ── */}
      {phase === "waking" && (
        <div className="text-center fade-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
            style={{ background: "var(--accent-10)", border: "1px solid var(--accent-25)" }}>
            <svg className="spin w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{ color: "var(--accent)" }}>
              <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
                strokeLinecap="round"/>
            </svg>
          </div>
          <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--text)" }}>Waking up the server…</h2>
          <p className="text-xs max-w-xs mx-auto" style={{ color: "var(--text-3)" }}>
            First request after a while can take up to 30s — hang tight.
          </p>
        </div>
      )}

      {/* ── Importing spinner ── */}
      {phase === "importing" && (
        <div className="text-center fade-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
            style={{ background: "var(--accent-10)", border: "1px solid var(--accent-25)" }}>
            <svg className="spin w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              style={{ color: "var(--accent)" }}>
              <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
                strokeLinecap="round"/>
            </svg>
          </div>
          <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--text)" }}>Importing job…</h2>
          {jobUrl && (
            <p className="text-xs max-w-xs mx-auto break-all" style={{ color: "var(--text-3)" }}>{jobUrl}</p>
          )}
        </div>
      )}

      {/* ── Paste fallback (JS-rendered sites: Unstop, etc.) ── */}
      {(phase === "paste-fallback" || phase === "pasting") && (
        <div className="w-full max-w-sm fade-up">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.25)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-6 h-6"
              style={{ color: "#f59e0b" }}>
              <path d="M9 12h6M9 16h6M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" strokeLinecap="round"/>
              <polyline points="13 2 13 9 20 9"/>
            </svg>
          </div>
          <h2 className="text-lg font-semibold mb-1 text-center" style={{ color: "var(--text)" }}>
            Paste the job description
          </h2>
          <p className="text-xs text-center mb-4" style={{ color: "var(--text-3)" }}>
            This site needs JavaScript to load — copy the job post and paste it below.
          </p>
          {jobUrl && (
            <p className="text-[11px] text-center mb-3 break-all" style={{ color: "var(--text-3)" }}>
              From: {jobUrl.replace(/https?:\/\//, "").slice(0, 60)}
            </p>
          )}
          <textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder="Paste the full job title, company, responsibilities, requirements…"
            rows={8}
            autoFocus
            className="w-full resize-none no-scrollbar mb-3"
            style={{ fontSize: 13, padding: "12px 14px", borderRadius: 14, lineHeight: 1.6 }}
          />
          <button
            onClick={importFromPaste}
            disabled={phase === "pasting" || !pasteText.trim()}
            className="w-full py-3 rounded-xl text-sm font-semibold transition active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
            style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
            {phase === "pasting"
              ? <><svg className="spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" strokeLinecap="round"/></svg>Importing…</>
              : "Import Job"}
          </button>
          <button onClick={() => router.replace("/jobs")}
            className="w-full mt-2 py-2.5 rounded-xl text-sm transition active:scale-95"
            style={{ color: "var(--text-3)" }}>
            Cancel
          </button>
        </div>
      )}

      {/* ── Success ── */}
      {phase === "success" && (
        <div className="text-center fade-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
            style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.25)" }}>
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8" style={{ color: "#22c55e" }}>
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
            </svg>
          </div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text)" }}>Job imported!</h2>
          <p className="text-sm" style={{ color: "var(--text-3)" }}>{message}</p>
          <p className="text-xs mt-3" style={{ color: "var(--text-3)" }}>Taking you to Jobs…</p>
        </div>
      )}

      {/* ── Error ── */}
      {phase === "error" && (
        <div className="text-center fade-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8" style={{ color: "#ef4444" }}>
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
          </div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text)" }}>Import failed</h2>
          <p className="text-sm mb-5" style={{ color: "var(--text-3)" }}>{message}</p>
          <button onClick={() => router.replace("/jobs")}
            className="px-6 py-2.5 rounded-xl text-sm font-semibold transition active:scale-95"
            style={{ background: "var(--surface-2)", color: "var(--text)", border: "1px solid var(--border)" }}>
            Go to Jobs
          </button>
        </div>
      )}
    </div>
  );
}

export default function ShareTargetPage() {
  return (
    <Suspense>
      <ShareHandler />
    </Suspense>
  );
}
