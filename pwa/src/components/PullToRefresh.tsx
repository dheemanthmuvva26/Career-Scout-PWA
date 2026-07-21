"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { haptics } from "@/lib/haptics";

interface PullToRefreshProps {
  onRefresh: () => Promise<void>;
  children: React.ReactNode;
  threshold?: number;
  /** id of the actual scrolling ancestor (defaults to the app shell's <main>) */
  scrollContainerId?: string;
}

export default function PullToRefresh({
  onRefresh,
  children,
  threshold = 72,
  scrollContainerId = "app-scroll",
}: PullToRefreshProps) {
  const [pullY, setPullY]           = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [triggered, setTriggered]   = useState(false);
  const startY   = useRef(0);
  const startX   = useRef(0);
  const pulling  = useRef(false);
  const decided  = useRef(false); // has the gesture been classified as vertical-pull yet?

  const progress = Math.min(pullY / threshold, 1);
  const visible  = pullY > 8;

  const getScrollEl = useCallback(
    () => document.getElementById(scrollContainerId),
    [scrollContainerId]
  );

  const handleTouchStart = useCallback((e: TouchEvent) => {
    if (refreshing) return;
    const el = getScrollEl();
    if (!el || el.scrollTop > 0) return;     // only trigger at top
    startY.current = e.touches[0].clientY;
    startX.current = e.touches[0].clientX;
    pulling.current = true;
    decided.current = false;
  }, [refreshing, getScrollEl]);

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!pulling.current || refreshing) return;
    const el = getScrollEl();
    if (el && el.scrollTop > 0) { pulling.current = false; setPullY(0); return; }
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

    if (dy <= 0) { setPullY(0); return; }
    e.preventDefault();
    // Rubber-band dampening
    const damped = dy > threshold
      ? threshold + (dy - threshold) * 0.25
      : dy;
    setPullY(damped);
    if (damped >= threshold && !triggered) {
      setTriggered(true);
      haptics.medium();
    } else if (damped < threshold && triggered) {
      setTriggered(false);
    }
  }, [refreshing, threshold, triggered, getScrollEl]);

  const handleTouchEnd = useCallback(async () => {
    if (!pulling.current) return;
    pulling.current = false;
    decided.current = false;
    if (pullY >= threshold) {
      setRefreshing(true);
      setPullY(threshold * 0.6);
      haptics.success();
      await onRefresh();
      setRefreshing(false);
    }
    setPullY(0);
    setTriggered(false);
  }, [pullY, threshold, onRefresh]);

  useEffect(() => {
    window.addEventListener("touchstart", handleTouchStart, { passive: true });
    window.addEventListener("touchmove",  handleTouchMove,  { passive: false });
    window.addEventListener("touchend",   handleTouchEnd,   { passive: true });
    return () => {
      window.removeEventListener("touchstart", handleTouchStart);
      window.removeEventListener("touchmove",  handleTouchMove);
      window.removeEventListener("touchend",   handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd]);

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
          <div style={{
            width: 36, height: 36,
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
