import type { ReactNode } from "react";
import BottomNav from "@/components/BottomNav";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="sidebar-layout min-h-screen" style={{ background: "var(--background)" }}>
      <BottomNav />
      <main className="sidebar-content flex-1 pb-20 lg:pb-8 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
