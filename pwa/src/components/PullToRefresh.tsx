"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { haptics } from "@/lib/haptics";

interface PullToRefreshProps {
  onRefresh: () => Promise<void>;
  children: React.ReactNode;
  threshold?: number;
  /** ms the pull must be held past threshold before refresh fires */
  holdMs?: number;
  /** id of the actual scrolling ancestor (defaults to the app shell's <main>) */
  scrollContainerId?: string;
}

export default function PullToRefresh({
  onRefresh,
  children,
  threshold = 72,
  holdMs = 1800,
  scrollContainerId = "app-scroll",
}: PullToRefreshProps) {
  const [pullY, setPullY]             = useState(0);
  const [refreshing, setRefreshing]   = useState(false);
  const [triggered, setTriggered]     = useState(false);   // past threshold, holding
  const [holdProgress, setHoldProgress] = useState(0);      // 0..1 fill while holding
  const startY   = useRef(0);
  const startX   = useRef(0);
  const pulling  = useRef(false);
  const decided  = useRef(false); // has the gesture been classified as vertical-pull yet?
  const holdStartedAt = useRef(0);
  const holdTimer     = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdRaf       = useRef<number | null>(null);
  const firing        = useRef(false); // hold completed, refresh is running/about to run

  const progress = Math.min(pullY / threshold, 1);
  const visible  = pullY > 8;

  const getScrollEl = useCallback(
    () => document.getElementById(scrollContainerId),
    [scrollContainerId]
  );

  const clearHold = useCallback(() => {
    if (holdTimer.current) { clearTimeout(holdTimer.current); holdTimer.current = null; }
    if (holdRaf.current) { cancelAnimationFrame(holdRaf.current); holdRaf.current = null; }
    setHoldProgress(0);
    setTriggered(false);
  }, []);

  const startHold = useCallback(() => {
    if (holdTimer.current) return; // already holding
    holdStartedAt.current = Date.now();
    setTriggered(true);
    haptics.medium();

    const tick = () => {
      const elapsed = Date.now() - holdStartedAt.current;
      setHoldProgress(Math.min(elapsed / holdMs, 1));
      if (elapsed < holdMs) holdRaf.current = requestAnimationFrame(tick);
    };
    holdRaf.current = requestAnimationFrame(tick);

    holdTimer.current = setTimeout(async () => {
      holdTimer.current = null;
      firing.current = true;
      pulling.current = false;
      decided.current = false;
      haptics.success();
      setRefreshing(true);
      setPullY(threshold * 0.6);
      await onRefresh();
      setRefreshing(false);
      setPullY(0);
      setTriggered(false);
      setHoldProgress(0);
      firing.current = false;
    }, holdMs);
  }, [holdMs, onRefresh, threshold]);

  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (refreshing || firing.current) return;
    const el = getScrollEl();
    if (!el || el.scrollTop > 0) return;     // only trigger at top
    startY.current = e.touches[0].clientY;
    startX.current = e.touches[0].clientX;
    pulling.current = true;
    decided.current = false;
  }, [refreshing, getScrollEl]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!pulling.current || refreshing || firing.current) return;
    const el = getScrollEl();
    if (el && el.scrollTop > 0) { pulling.current = false; clearHold(); setPullY(0); return; }
    const dy = e.touches[0].clientY - startY.current;
    const dx = e.touches[0].clientX - startX.current;

    if (!decided.current) {
      // Dead zone: wait for a clear, mostly-vertical downward drag before
      // committing to the pull gesture — avoids hijacking small taps,
      // horizontal card swipes, or momentum-scroll stop taps.
      if (Math.abs(dy) < 12 && Math.abs(dx) < 12) return;
      if (dy <= 0 || Math.abs(dx) > Math.abs(dy)) {
        pulling.current = false;
        setPullY(0);
        return;
      }
      decided.current = true;
    }

    if (dy <= 0) { clearHold(); setPullY(0); return; }
    e.preventDefault();
    // Rubber-band dampening
    const damped = dy > threshold
      ? threshold + (dy - threshold) * 0.25
      : dy;
    setPullY(damped);

    if (damped >= threshold) {
      startHold(); // no-op if already holding
    } else {
      clearHold();
    }
  }, [refreshing, threshold, getScrollEl, clearHold, startHold]);

  const handleTouchEnd = useCallback(() => {
    if (!pulling.current) return;
    pulling.current = false;
    decided.current = false;
    // Released before the hold completed — just a normal scroll bounce-back,
    // no refresh, no matter how far it was pulled.
    if (!firing.current) {
      clearHold();
      setPullY(0);
    }
  }, [clearHold]);

  useEffect(() => {
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchmove",  handleTouchMove,  { passive: false });
    window.addEventListener("touchend",   handleTouchEnd,   { passive: true });
    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchmove",  handleTouchMove);
      window.removeEventListener("touchend",   handleTouchEnd);
      clearHold();
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd, clearHold]);

  return (
    <div>
      {/* Pull indicator */}
      <div style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        display: "flex",
        justifyContent: "center",
        height: visible || refreshing ? `${Math.max(pullY, refreshing ? 48 : 0)}px` : "0px",
        overflow: "hidden",
        transition: refreshing || pullY === 0 ? "height 0.3s cubic-bezier(0.23,1,0.32,1)" : "none",
        alignItems: "flex-end",
        paddingBottom: visible || refreshing ? "8px" : "0",
      }}>
        {(visible || refreshing) && (
          <div style={{ position: "relative", width: 36, height: 36 }}>
            {/* Hold progress ring */}
            {triggered && !refreshing && (
              <svg width="36" height="36" viewBox="0 0 36 36"
                style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)" }}>
                <circle cx="18" cy="18" r="16" fill="none" stroke="var(--accent-20)" strokeWidth="2.5" />
                <circle cx="18" cy="18" r="16" fill="none" stroke="var(--accent)" strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeDasharray={2 * Math.PI * 16}
                  strokeDashoffset={2 * Math.PI * 16 * (1 - holdProgress)}
                  style={{ transition: "stroke-dashoffset 0.05s linear" }}
                />
              </svg>
            )}
            <div style={{
              position: "absolute", inset: 0,
              borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "rgba(9,22,32,0.90)",
              backdropFilter: "blur(12px)",
              border: `1px solid ${triggered || refreshing ? "var(--accent-30)" : "var(--border-2)"}`,
              boxShadow: triggered || refreshing
                ? "0 0 12px var(--accent-20)"
                : "0 4px 16px rgba(0,0,0,0.4)",
              transition: "border-color 0.2s ease, box-shadow 0.2s ease",
            }}>
              {refreshing ? (
                <svg className="spin" width="16" height="16" viewBox="0 0 24 24"
                  fill="none" stroke="var(--accent)" strokeWidth="2.5">
                  <path d="M12 4V2M12 22v-2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
                    strokeLinecap="round"/>
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                  stroke={triggered ? "var(--accent)" : "var(--text-3)"}
                  strokeWidth="2.5"
                  style={{
                    transform: `rotate(${triggered ? 180 : progress * 180}deg)`,
                    transition: "transform 0.15s ease, stroke 0.2s ease",
                  }}>
                  <path d="M12 5v14M5 12l7 7 7-7" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </div>
          </div>
        )}
      </div>

      <div style={{
        transform: pullY > 0 ? `translateY(${pullY}px)` : undefined,
        transition: pullY === 0 ? "transform 0.3s cubic-bezier(0.23,1,0.32,1)" : "none",
      }}>
        {children}
      </div>
    </div>
  );
}
