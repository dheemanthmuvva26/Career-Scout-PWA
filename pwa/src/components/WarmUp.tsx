"use client";

import { useEffect } from "react";

const PING_URL = `${process.env.NEXT_PUBLIC_API_URL}/health`;
// Render free tier spins down after 15 min — ping every 12 min to stay warm
const KEEPALIVE_INTERVAL_MS = 12 * 60 * 1000;

export default function WarmUp() {
  useEffect(() => {
    // Initial ping on mount
    fetch(PING_URL, { method: "GET" }).catch(() => {});

    // Keep-alive so Render never spins down during an active session
    const id = setInterval(() => {
      fetch(PING_URL, { method: "GET" }).catch(() => {});
    }, KEEPALIVE_INTERVAL_MS);

    return () => clearInterval(id);
  }, []);

  return null;
}
