import type { ReactNode } from "react";
import BottomNav from "@/components/BottomNav";
import Sidebar from "@/components/Sidebar";
import WarmUp from "@/components/WarmUp";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg)" }}>
      <WarmUp />

      {/* Sidebar — desktop only (md+) */}
      <Sidebar />

      {/* Main scroll area */}
      <main
        id="app-scroll"
        className="flex-1 overflow-y-auto no-scrollbar md:ml-[216px]"
        style={{ paddingBottom: "calc(88px + env(safe-area-inset-bottom, 0px))" }}
      >
        {/* On desktop remove bottom-nav padding, add top breathing room */}
        <style>{`@media (min-width: 768px) { #app-scroll { padding-bottom: 32px !important; } }`}</style>

        <div className="max-w-lg md:max-w-4xl mx-auto px-4 md:px-10">
          {children}
        </div>
      </main>

      {/* Bottom nav — mobile only */}
      <div className="md:hidden">
        <BottomNav />
      </div>
    </div>
  );
}
