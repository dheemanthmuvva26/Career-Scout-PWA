"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { pushSupported, getPushSubscriptionStatus, subscribeToPush, unsubscribeFromPush } from "@/lib/push";

export default function SettingsPage() {
  const [companies, setCompanies] = useState<{ name: string; url?: string; blacklisted: number }[]>([]);
  const [roles, setRoles] = useState<{ title: string }[]>([]);
  const [newCompany, setNewCompany] = useState("");
  const [newRole, setNewRole] = useState("");
  const [saving, setSaving] = useState("");

  const [pushStatus, setPushStatus] = useState<"subscribed" | "unsubscribed" | "unsupported" | "loading">("loading");
  const [pushBusy, setPushBusy] = useState(false);
  const [pushError, setPushError] = useState("");

  useEffect(() => {
    api.companies().then(setCompanies).catch(() => {});
    api.roles().then(setRoles).catch(() => {});
    if (pushSupported()) {
      getPushSubscriptionStatus().then(setPushStatus).catch(() => setPushStatus("unsupported"));
    } else {
      setPushStatus("unsupported");
    }
  }, []);

  async function togglePush() {
    setPushBusy(true); setPushError("");
    try {
      if (pushStatus === "subscribed") {
        await unsubscribeFromPush();
        setPushStatus("unsubscribed");
      } else {
        await subscribeToPush();
        setPushStatus("subscribed");
      }
    } catch (e: unknown) {
      setPushError(e instanceof Error ? e.message : "Something went wrong.");
    }
    setPushBusy(false);
  }

  async function addCompany() {
    if (!newCompany.trim()) return;
    setSaving("company");
    await api.addCompany(newCompany.trim());
    setCompanies((prev) => [...prev, { name: newCompany.trim(), blacklisted: 0 }]);
    setNewCompany("");
    setSaving("");
  }

  async function addRole() {
    if (!newRole.trim()) return;
    setSaving("role");
    await api.addRole(newRole.trim());
    setRoles((prev) => [...prev, { title: newRole.trim() }]);
    setNewRole("");
    setSaving("");
  }

  return (
    <div className="pt-8 pb-4 fade-up">
      <h1 className="mb-1" style={{ color: "var(--text)" }}>Settings</h1>
      <p className="text-sm mb-6" style={{ color: "var(--text-3)" }}>Configure your job search preferences</p>

      {/* Notifications */}
      <section className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Notifications</p>
        <div className="card flex items-center justify-between px-4 py-3">
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Push notifications</p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-3)" }}>
              {pushStatus === "unsupported"
                ? "Not supported on this browser/device"
                : pushStatus === "subscribed"
                ? "Digest, scout results, and follow-up nudges will alert this device"
                : "Enable to get alerts without opening the app"}
            </p>
            {pushError && <p className="text-xs mt-1" style={{ color: "#fca5a5" }}>{pushError}</p>}
          </div>
          {pushStatus !== "unsupported" && pushStatus !== "loading" && (
            <button onClick={togglePush} disabled={pushBusy}
              className="px-4 py-2 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-50 transition active:scale-95"
              style={pushStatus === "subscribed"
                ? { background: "rgba(239,68,68,0.08)", color: "#fca5a5", border: "1px solid rgba(239,68,68,0.15)" }
                : { background: "var(--accent)", color: "var(--on-accent)" }}>
              {pushBusy ? "…" : pushStatus === "subscribed" ? "Disable" : "Enable"}
            </button>
          )}
        </div>
      </section>

      {/* Target Roles */}
      <section className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Target Roles</p>
        <div className="flex gap-2 mb-3">
          <input value={newRole} onChange={(e) => setNewRole(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addRole()}
            placeholder="e.g. Data Analyst" />
          <button onClick={addRole} disabled={saving === "role"}
            className="px-4 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-50 transition active:scale-95"
            style={{ background: "var(--accent)", color: "var(--on-accent)", minWidth: 64 }}>
            {saving === "role" ? "…" : "Add"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {roles.map((r) => (
            <span key={r.title} className="text-sm px-3 py-1.5 rounded-full"
              style={{ background: "var(--accent-10)", color: "var(--accent-text)", border: "1px solid var(--accent-20)" }}>
              {r.title}
            </span>
          ))}
        </div>
      </section>

      {/* Target Companies */}
      <section className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-widest mb-3" style={{ color: "var(--text-3)" }}>Target Companies</p>
        <div className="flex gap-2 mb-3">
          <input value={newCompany} onChange={(e) => setNewCompany(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCompany()}
            placeholder="e.g. Google" />
          <button onClick={addCompany} disabled={saving === "company"}
            className="px-4 rounded-xl text-sm font-semibold shrink-0 disabled:opacity-50 transition active:scale-95"
            style={{ background: "var(--accent)", color: "var(--on-accent)", minWidth: 64 }}>
            {saving === "company" ? "…" : "Add"}
          </button>
        </div>
        <div className="space-y-2">
          {companies.filter((c) => !c.blacklisted).map((c) => (
            <div key={c.name} className="card flex items-center justify-between px-4 py-3">
              <span className="text-sm font-medium" style={{ color: "var(--text)" }}>{c.name}</span>
              <button
                onClick={() => api.blacklist(c.name).then(() => setCompanies((prev) => prev.filter((x) => x.name !== c.name)))}
                className="text-xs font-medium transition active:scale-95 px-3 py-1.5 rounded-lg"
                style={{ color: "#fca5a5", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)" }}>
                Blacklist
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
