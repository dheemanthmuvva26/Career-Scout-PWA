const BASE = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.NEXT_PUBLIC_API_KEY!;

async function apiFetch(path: string, init?: RequestInit) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  };

  let res: Response;
  try {
    // Safety net so a request never hangs forever (e.g. Render cold start
    // taking longer than usual, or a dropped connection) — surfaces a clear,
    // actionable error instead of a spinner stuck on screen indefinitely.
    res = await fetch(BASE + path, { ...init, headers, signal: AbortSignal.timeout(60_000) });
  } catch (e) {
    if (e instanceof Error && e.name === "TimeoutError") {
      throw new Error("Request timed out — the server may be waking up, try again in a moment");
    }
    throw e;
  }
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

export type GmailSummary = {
  status: "ok" | "error" | "busy" | "disabled" | "not_configured";
  trigger: string;
  emails_seen: number;
  emails_processed: number;
  jobs_found: number;
  jobs_new: number;
  jobs_filtered: number;
  errors: string[];
  finished_at: string;
};

// ── Resume integrity / editor / profile types ──────────────────────────────

export type IntegrityIssue = {
  section: string; entry: string; text: string; reason: string;
  action: string; replacement?: string;
};
export type Integrity = {
  ok: boolean; mode: "repair" | "warn"; issues: IntegrityIssue[];
  warnings: string[]; claim_check: string;
};

export type ResumeEntry = {
  company?: string; role?: string; dates?: string; location?: string;
  name?: string; tech?: string[]; github?: string; bullets: string[];
};
export type ResumeContent = {
  summary: string;
  skills_section: Record<string, string[]>;
  selected_experience: ResumeEntry[];
  selected_projects: ResumeEntry[];
  selected_certifications: { name: string; issuer: string; date: string }[];
  ats_keywords?: string[];
  profile_id?: string;
  skills_order?: string[];
  integrity?: Integrity;
};

export type AtsFlag = {
  section: string; issue: string; fix: string;
  honest?: boolean; why_not?: string; alternative?: string;
};

export type ProfileSuggestion = {
  kind: "project" | "experience"; entry_name: string;
  old_text: string | null; new_text: string;
  source_quote?: string; note?: string; quote_verified?: boolean; reason?: string;
};
export type SuggestResult = { suggestions: ProfileSuggestion[]; rejected: ProfileSuggestion[]; error?: string };
export type ProfileEdit = ProfileSuggestion & { id: string; created_at: string; status: string };

// Poll a background forge/render token every 4s (up to 120s). Retries on
// transient errors so a single dropped response doesn't kill the job.
async function pollToken(token: string) {
  const deadline = Date.now() + 120_000;
  let pollErrors = 0;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, 4000));
    try {
      const result = await apiFetch(`/forge/poll/${token}`);
      if (result.status === "done") return result;
      pollErrors = 0;
    } catch {
      pollErrors++;
      if (pollErrors >= 3) throw new Error("Poll failed 3 times — try again");
    }
  }
  throw new Error("Timed out waiting for resume — try again");
}

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
      body: JSON.stringify({ text: note }),
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
    return pollToken(token);
  },

  forgeContent: (id: string): Promise<{ content: ResumeContent; pdf_path: string | null }> =>
    apiFetch(`/forge/${id}/content`),

  renderResume: async (id: string, content: ResumeContent) => {
    const { token } = await apiFetch(`/forge/${id}/render`, {
      method: "POST", body: JSON.stringify({ content }),
    });
    return pollToken(token);
  },

  profileSuggest: (text: string): Promise<SuggestResult> =>
    apiFetch("/profile/suggest", { method: "POST", body: JSON.stringify({ text }) }),
  profileEdits: (): Promise<ProfileEdit[]> => apiFetch("/profile/edits"),
  addProfileEdit: (s: ProfileSuggestion) =>
    apiFetch("/profile/edits", {
      method: "POST",
      body: JSON.stringify({
        kind: s.kind, entry_name: s.entry_name, old_text: s.old_text,
        new_text: s.new_text, source_quote: s.source_quote ?? "",
      }),
    }),
  deleteProfileEdit: (editId: string) => apiFetch(`/profile/edits/${editId}`, { method: "DELETE" }),
  profileExport: async (): Promise<string> => {
    const res = await fetch(BASE + "/profile/export", { headers: { "X-API-Key": API_KEY } });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.text();
  },

  scout: () => apiFetch("/scout", { method: "POST" }),

  companies: () => apiFetch("/companies"),
  addCompany: (name: string, url?: string) =>
    apiFetch("/companies", { method: "POST", body: JSON.stringify({ name, careers_url: url }) }),
  blacklist: (name: string) =>
    apiFetch(`/companies/blacklist?${new URLSearchParams({ name }).toString()}`, { method: "POST" }),

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

  batchImport: (urls: string[], profile: string, location?: string) =>
    apiFetch("/batch", {
      method: "POST",
      body: JSON.stringify({ urls, profile, location: location ?? "" }),
    }),

  forgePoll: (token: string) => apiFetch(`/forge/poll/${token}`),

  confirmSkill: (skill: string) =>
    apiFetch("/skills/confirm", { method: "POST", body: JSON.stringify({ skill }) }),
  confirmedSkills: () => apiFetch("/skills/confirmed"),

  gmailSync: () => apiFetch("/gmail/sync", { method: "POST" }),
  gmailStatus: (): Promise<{ configured: boolean; last: GmailSummary | null }> => apiFetch("/gmail/status"),

  pushVapidPublicKey:(): Promise<{ publicKey: string }> => apiFetch("/push/vapid-public-key"),
  pushSubscribe: (endpoint: string, p256dh: string, auth: string) =>
    apiFetch("/push/subscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint, keys: { p256dh, auth } }),
    }),
  pushUnsubscribe: (endpoint: string) =>
    apiFetch("/push/unsubscribe", { method: "POST", body: JSON.stringify({ endpoint }) }),
};
