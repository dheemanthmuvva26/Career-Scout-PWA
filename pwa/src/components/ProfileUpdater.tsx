"use client";

import { useEffect, useState } from "react";
import { api, type ProfileEdit, type ProfileSuggestion } from "@/lib/api";

const STATUS_TEXT: Record<string, string> = {
  applied: "active",
  "already-present": "already in your profile file",
  stale: "original bullet changed — no longer applies",
  "unknown-entry": "entry no longer exists",
};

/**
 * Paste a results document → review suggested profile updates → approve.
 * Every number in a suggestion was checked against the pasted text on the
 * server; nothing changes until you approve each one.
 */
export default function ProfileUpdater() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestions, setSuggestions] = useState<ProfileSuggestion[] | null>(null);
  const [rejected, setRejected] = useState<ProfileSuggestion[]>([]);
  const [edits, setEdits] = useState<ProfileEdit[]>([]);
  const [saving, setSaving] = useState<number | null>(null);
  const [exported, setExported] = useState("");

  const loadEdits = () => api.profileEdits().then(setEdits).catch(() => {});
  useEffect(() => { loadEdits(); }, []);

  async function suggest() {
    setBusy(true); setError(""); setSuggestions(null); setRejected([]);
    try {
      const r = await api.profileSuggest(text);
      if (r.error) setError(r.error);
      setSuggestions(r.suggestions);
      setRejected(r.rejected);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't get suggestions");
    }
    setBusy(false);
  }

  async function approve(i: number) {
    if (!suggestions) return;
    setSaving(i);
    try {
      await api.addProfileEdit(suggestions[i]);
      setSuggestions(s => s && s.filter((_, k) => k !== i));
      await loadEdits();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save");
    }
    setSaving(null);
  }

  async function remove(id: string) {
    await api.deleteProfileEdit(id).catch(() => {});
    loadEdits();
  }

  async function exportYaml() {
    try {
      const y = await api.profileExport();
      await navigator.clipboard.writeText(y).catch(() => {});
      setExported("Copied the updated profile YAML — paste it into forge/master_profile.yaml to sync the repo.");
    } catch {
      setExported("Export failed — try again.");
    }
  }

  return (
    <div className="space-y-3">
      <textarea value={text} onChange={e => setText(e.target.value)} rows={5}
        aria-label="Results document text"
        placeholder="Paste a project report or results write-up. Suggestions only use numbers that appear in this text."
        className="w-full text-xs" style={{ resize: "vertical" }} />
      <button onClick={suggest} disabled={busy || text.trim().length < 40}
        className="w-full py-2.5 rounded-xl text-sm font-semibold disabled:opacity-50 transition active:scale-95"
        style={{ background: "var(--accent)", color: "var(--on-accent)" }}>
        {busy ? "Reading document…" : "Suggest profile updates"}
      </button>
      {error && <p className="text-xs" style={{ color: "#fca5a5" }}>{error}</p>}

      {suggestions && suggestions.length === 0 && !error && (
        <p className="text-xs" style={{ color: "var(--text-3)" }}>No updates found — your profile already matches this document.</p>
      )}

      {suggestions?.map((s, i) => (
        <div key={i} className="card p-3 space-y-1.5">
          <p className="text-[11px] font-semibold" style={{ color: "var(--text-2)" }}>
            {s.entry_name} · {s.old_text ? "replace bullet" : "new bullet"}
          </p>
          {s.old_text && <p className="text-[11px] line-through" style={{ color: "var(--text-3)" }}>{s.old_text}</p>}
          <p className="text-xs" style={{ color: "var(--text)" }}>{s.new_text}</p>
          {s.source_quote && (
            <p className="text-[11px] italic" style={{ color: "var(--text-3)" }}>
              Source: “{s.source_quote}”{s.quote_verified === false && " (not found word-for-word — check it)"}
            </p>
          )}
          {s.note && <p className="text-[11px]" style={{ color: "var(--amber)" }}>{s.note}</p>}
          <div className="flex gap-2 pt-1">
            <button onClick={() => approve(i)} disabled={saving === i}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-50"
              style={{ background: "var(--accent-20)", color: "var(--accent)", border: "1px solid var(--accent-40)" }}>
              {saving === i ? "Saving…" : "Approve"}
            </button>
            <button onClick={() => setSuggestions(x => x && x.filter((_, k) => k !== i))}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold"
              style={{ background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border)" }}>
              Skip
            </button>
          </div>
        </div>
      ))}

      {rejected.length > 0 && (
        <details className="text-[11px]" style={{ color: "var(--text-3)" }}>
          <summary>{rejected.length} suggestion{rejected.length === 1 ? "" : "s"} filtered out</summary>
          <ul className="mt-1.5 space-y-1">
            {rejected.map((r, i) => <li key={i}>• {r.new_text?.slice(0, 90)}… — {r.reason}</li>)}
          </ul>
        </details>
      )}

      {edits.length > 0 && (
        <div className="pt-2 space-y-2">
          <p className="text-[11px] font-semibold" style={{ color: "var(--text-2)" }}>Approved updates</p>
          {edits.map(e => (
            <div key={e.id} className="card px-3 py-2 flex gap-2 items-start">
              <div className="flex-1 min-w-0">
                <p className="text-[11px]" style={{ color: "var(--text)" }}>{e.new_text}</p>
                <p className="text-[10px] mt-0.5" style={{ color: "var(--text-3)" }}>
                  {e.entry_name} · {STATUS_TEXT[e.status] ?? e.status}
                </p>
              </div>
              <button onClick={() => remove(e.id)} aria-label="Remove update"
                className="text-[11px] px-2 py-1 rounded" style={{ color: "#fca5a5" }}>Remove</button>
            </div>
          ))}
          <button onClick={exportYaml} className="text-xs font-semibold" style={{ color: "var(--accent)" }}>
            Copy updated profile YAML
          </button>
          {exported && <p className="text-[11px]" style={{ color: "var(--text-3)" }}>{exported}</p>}
        </div>
      )}
    </div>
  );
}
