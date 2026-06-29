/**
 * Haptic feedback utility — wraps navigator.vibrate() for native-feeling interactions.
 * Silently no-ops on devices that don't support it.
 */

const supports = typeof navigator !== "undefined" && "vibrate" in navigator;

export const haptics = {
  /** Very light tap — button press, toggle */
  light: () => supports && navigator.vibrate(8),

  /** Medium — selection change, card tap */
  medium: () => supports && navigator.vibrate(16),

  /** Heavier — confirm action, success */
  heavy: () => supports && navigator.vibrate(28),

  /** Success pattern */
  success: () => supports && navigator.vibrate([12, 60, 20]),

  /** Error / warning pattern */
  error: () => supports && navigator.vibrate([30, 40, 30, 40, 30]),

  /** Soft double-tap — notification, refresh complete */
  doubleTap: () => supports && navigator.vibrate([10, 80, 10]),

  /** Long press confirmation */
  longPress: () => supports && navigator.vibrate([0, 0, 40]),
};
