"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

function ShareHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"importing" | "success" | "error">("importing");
  const [jobUrl, setJobUrl] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    // The share target receives: url, text, title
    // LinkedIn "Share" sends the URL in the `url` param
    // Some apps put the URL in `text` or embed it in a sentence
    const raw = searchParams.get("url") || searchParams.get("text") || searchParams.get("title") || "";
    const match = raw.match(/https?:\/\/[^\s]+/);
    const resolved = match ? match[0].replace(/[.,;!?]$/, "") : raw.trim();
    setJobUrl(resolved);

    if (!resolved) {
      setStatus("error");
      setMessage("No URL found in the shared content.");
      return;
    }

    api.importJob(resolved)
      .then(() => {
        setStatus("success");
        setMessage("Job saved to your feed.");
        setTimeout(() => router.push("/jobs"), 2200);
      })
      .catch(() => {
        setStatus("error");
        setMessage("Import failed — check it's a supported job URL.");
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 safe-top"
      style={{ background: "var(--bg)" }}>

      {status === "importing" && (
        <div className="text-center fade-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
            style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)" }}>
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

      {status === "success" && (
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

      {status === "error" && (
        <div className="text-center fade-up">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
            style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8" style={{ color: "#ef4444" }}>
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
          </div>
          <h2 className="text-lg font-semibold mb-1" style={{ color: "var(--text)" }}>Import failed</h2>
          <p className="text-sm mb-5" style={{ color: "var(--text-3)" }}>{message}</p>
          <button onClick={() => router.push("/jobs")}
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
