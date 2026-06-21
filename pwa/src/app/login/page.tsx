"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const router = useRouter();
  const supabase = createClient();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    if (mode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setError(error.message);
      else router.push("/");
    } else {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) setError(error.message);
      else setMessage("Check your email to confirm your account.");
    }
    setLoading(false);
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-5 safe-top" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-sm fade-up">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: "var(--accent)", boxShadow: "0 0 40px var(--accent-30)" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="w-7 h-7">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35" strokeLinecap="round"/>
            </svg>
          </div>
          <h1 style={{ color: "var(--text)" }}>Career Scout</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-3)" }}>Your AI-powered job search assistant</p>
        </div>

        {/* Mode toggle */}
        <div className="flex rounded-xl p-1 mb-5" style={{ background: "var(--surface-2)" }}>
          {(["signin", "signup"] as const).map((m) => (
            <button key={m} onClick={() => { setMode(m); setError(""); setMessage(""); }}
              className="flex-1 py-2 rounded-lg text-sm font-semibold transition"
              style={{
                background: mode === m ? "var(--surface)" : "transparent",
                color: mode === m ? "var(--text)" : "var(--text-3)",
                boxShadow: mode === m ? "0 1px 3px rgba(0,0,0,0.4)" : "none",
              }}>
              {m === "signin" ? "Sign in" : "Sign up"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input type="email" placeholder="Email address"
            value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />

          {error && (
            <div className="rounded-xl px-3 py-2.5 text-xs"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
              {error}
            </div>
          )}
          {message && (
            <div className="rounded-xl px-3 py-2.5 text-xs"
              style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)", color: "#86efac" }}>
              {message}
            </div>
          )}

          <button type="submit" disabled={loading}
            className="w-full py-3.5 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-50"
            style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
            {loading ? "…" : mode === "signin" ? "Sign In" : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
