import type { ReactNode } from "react";
import AppShell from "@/components/AppShell";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      <AppShell>{children}</AppShell>
    </div>
  );
}
