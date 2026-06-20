"use client";

import { useEffect } from "react";

export default function WarmUp() {
  useEffect(() => {
    // Fire-and-forget ping so Render wakes up before the user triggers real API calls
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`, { method: "GET" }).catch(() => {});
  }, []);

  return null;
}
