import type { ReactNode } from "react";
import BottomNav from "@/components/BottomNav";
import WarmUp from "@/components/WarmUp";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg)" }}>
      <WarmUp />
      <main className="flex-1 overflow-y-auto pb-24">
        <div className="max-w-lg mx-auto px-4">
          {children}
        </div>
      </main>
      <BottomNav />
    </div>
  );
}
