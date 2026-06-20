import BottomNav from "@/components/BottomNav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--background)" }}>
      <main className="flex-1 pb-20 overflow-y-auto">
        {children}
      </main>
      <BottomNav />
    </div>
  );
}
