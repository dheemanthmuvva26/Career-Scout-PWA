import type { ReactNode } from "react";
import BottomNav from "@/components/BottomNav";
import WarmUp from "@/components/WarmUp";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      <WarmUp />
      <main className="flex-1 overflow-y-auto" style={{ paddingBottom: "calc(80px + env(safe-area-inset-bottom, 0px))" }}>
        <div className="max-w-lg mx-auto px-4">
          {children}
        </div>
      </main>
      <BottomNav />
    </div>
  );
}
