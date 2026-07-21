import type { ReactNode } from "react";
import AppShell from "@/components/AppShell";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col" style={{ background: "var(--bg)", height: "100dvh" }}>
      <AppShell>{children}</AppShell>
    </div>
  );
}
