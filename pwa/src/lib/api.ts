import { createClient } from "./supabase/client";

const BASE = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.NEXT_PUBLIC_API_KEY!;

async function apiFetch(path: string, init?: RequestInit) {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  };
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(BASE + path, { ...init, headers });
  if (!res.ok) {
    let detail = "";
    try { const j = await res.json(); detail = j.detail || j.error || ""; } catch {}
    throw new Error(`${res.status}${detail ? `: ${detail}` : ""}`);
  }
  return res.json();
}

export type Job = {
  id: string;
  short_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  description: string;
  score: number;
  score_detail: Record<string, unknown>;
  tags_matched: string[];
  status: string;
  outcome: string;
  urgency: string;
  posted_date: string;
  created_at: string;
  updated_at: string;
  follow_up_due: string | null;
  resume_path: string | null;
  notes: string | null;
};

export type Stats = {
  total: number;
  new: number;
  applied: number;
  interview: number;
  offer: number;
  rejected: number;
  ghosted: number;
  response_rate: number;
  interview_rate: number;
};

export const api = {
  stats: (): Promise<Stats> => apiFetch("/stats"),

  jobs: (params?: Record<string, string>): Promise<Job[]> => {
    const q = params ? "?" + new URLSearchParams(params).toString() : "";
    return apiFetch(`/jobs${q}`);
  },

  job: (id: string): Promise<Job> => apiFetch(`/jobs/${id}`),

  apply: (id: string) =>
    apiFetch(`/jobs/${id}/apply`, { method: "POST" }),

  setStatus: (id: string, status: string) =>
    apiFetch(`/jobs/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),

  setOutcome: (id: string, outcome: string, rejection_reason?: string) =>
    apiFetch(`/jobs/${id}/outcome`, {
      method: "POST",
      body: JSON.stringify({ outcome, rejection_reason }),
    }),

  note: (id: string, note: string) =>
    apiFetch(`/jobs/${id}/note`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),

  auditResume: (id: string) =>
    apiFetch(`/forge/${id}/audit`, { method: "POST" }),

  atsCheck: (id: string) =>
    apiFetch(`/forge/${id}/ats-check`, { method: "POST" }),

  forge: async (id: string, profile?: string, atsHints?: object) => {
    // POST returns a token immediately — forge runs in background on server
    const { token } = await apiFetch(
      `/forge/${id}${profile ? `?profile=${encodeURIComponent(profile)}` : ""}`,
      { method: "POST", body: JSON.stringify({ ats_hints: atsHints ?? null }) }
    );
    // Poll every 4s until done (up to 120s). Retry on transient errors
    // so a single dropped response doesn't kill the whole forge.
    const deadline = Date.now() + 120_000;
    let pollErrors = 0;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 4000));
      try {
        const result = await apiFetch(`/forge/poll/${token}`);
        if (result.status === "done") return result;
        pollErrors = 0; // reset on success
      } catch {
        pollErrors++;
        if (pollErrors >= 3) throw new Error("Forge poll failed 3 times — try again");
      }
    }
    throw new Error("Timed out waiting for resume — try again");
  },

  scout: () => apiFetch("/scout", { method: "POST" }),

  companies: () => apiFetch("/companies"),
  addCompany: (name: string, url?: string) =>
    apiFetch("/companies", { method: "POST", body: JSON.stringify({ name, url }) }),
  blacklist: (name: string) =>
    apiFetch("/companies/blacklist", { method: "POST", body: JSON.stringify({ name }) }),

  roles: () => apiFetch("/roles"),
  addRole: (title: string) =>
    apiFetch("/roles", { method: "POST", body: JSON.stringify({ title }) }),

  insights: () => apiFetch("/insights/weekly"),
  gaps: () => apiFetch("/insights/gaps"),
  signals: () => apiFetch("/insights/signals"),

  importJob: (url: string, location?: string) =>
    apiFetch("/import", { method: "POST", body: JSON.stringify({ url, location: location ?? "" }) }),
  importJobText: (text: string, location?: string) =>
    apiFetch("/import/text", { method: "POST", body: JSON.stringify({ text, location: location ?? "" }) }),
};
