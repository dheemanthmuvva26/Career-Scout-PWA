"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const [companies, setCompanies] = useState<{ name: string; url?: string; blacklisted: number }[]>([]);
  const [roles, setRoles] = useState<{ title: string }[]>([]);
  const [newCompany, setNewCompany] = useState("");
  const [newRole, setNewRole] = useState("");
  const [saving, setSaving] = useState("");
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    api.companies().then(setCompanies).catch(() => {});
    api.roles().then(setRoles).catch(() => {});
  }, []);

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

  async function signOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <div className="max-w-lg mx-auto px-4 pt-6 pb-8">
      <h1 className="text-xl font-bold text-white mb-5">Settings</h1>

      {/* Target Roles */}
      <section className="mb-6">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Target Roles</h2>
        <div className="flex gap-2 mb-3">
          <input
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addRole()}
            placeholder="e.g. Data Analyst"
            className="flex-1 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={addRole}
            disabled={saving === "role"}
            className="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            Add
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {roles.map((r) => (
            <span key={r.title} className="px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-sm text-white">
              {r.title}
            </span>
          ))}
        </div>
      </section>

      {/* Target Companies */}
      <section className="mb-6">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Target Companies</h2>
        <div className="flex gap-2 mb-3">
          <input
            value={newCompany}
            onChange={(e) => setNewCompany(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCompany()}
            placeholder="e.g. Google"
            className="flex-1 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={addCompany}
            disabled={saving === "company"}
            className="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            Add
          </button>
        </div>
        <div className="space-y-1">
          {companies.filter((c) => !c.blacklisted).map((c) => (
            <div key={c.name} className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-800 border border-slate-700">
              <span className="text-sm text-white">{c.name}</span>
              <button
                onClick={() => api.blacklist(c.name).then(() => setCompanies((prev) => prev.filter((x) => x.name !== c.name)))}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Blacklist
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Account */}
      <section>
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">Account</h2>
        <button
          onClick={signOut}
          className="w-full py-3 rounded-xl border border-red-800 text-red-400 hover:bg-red-900/20 text-sm font-medium transition"
        >
          Sign Out
        </button>
      </section>
    </div>
  );
}
