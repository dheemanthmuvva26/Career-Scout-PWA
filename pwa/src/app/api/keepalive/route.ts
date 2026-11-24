// Daily Vercel Cron → backend /health (see vercel.json).
//
// Why this exists: Supabase's free tier pauses a project after ~7 idle days,
// which took the whole app down in November. The GitHub Actions keepalive was
// meant to prevent that, but GitHub's free scheduler is best-effort — it ran
// every 2-5h instead of every 10 min, then stopped entirely after Oct 26.
// Vercel Cron runs reliably. /health reads a real table and pings the
// Supabase Storage API, so one call a day keeps the project active.
//
// It also wakes Render, but once a day can't stop Render's 15-minute sleep;
// that would need an every-few-minutes external pinger.

export const dynamic = "force-dynamic";
export const maxDuration = 60; // Render cold starts take 30-60s

export async function GET(request: Request) {
  // When CRON_SECRET is set in Vercel, only Vercel Cron (which sends it as a
  // bearer token) may trigger this. Without it the route is still harmless:
  // it only calls the public /health endpoint.
  const secret = process.env.CRON_SECRET;
  if (secret && request.headers.get("authorization") !== `Bearer ${secret}`) {
    return new Response("Unauthorized", { status: 401 });
  }

  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base) return Response.json({ ok: false, error: "NEXT_PUBLIC_API_URL not set" }, { status: 500 });

  const started = Date.now();
  try {
    const res = await fetch(`${base}/health`, { cache: "no-store", signal: AbortSignal.timeout(55_000) });
    const body = await res.json().catch(() => ({}));
    // 503 = API up but database down (paused?) — surface it as a failed cron run.
    return Response.json({ ok: res.ok, status: res.status, ms: Date.now() - started, health: body },
      { status: res.ok ? 200 : 502 });
  } catch (e) {
    return Response.json({ ok: false, error: String(e), ms: Date.now() - started }, { status: 504 });
  }
}
