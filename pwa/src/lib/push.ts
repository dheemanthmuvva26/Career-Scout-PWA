// Web Push subscription management — replaces the old Telegram bot for
// proactive notifications. The actual push/notificationclick handling lives
// in src/worker/index.ts (compiled into the service worker by next-pwa).

import { api } from "@/lib/api";

function urlBase64ToUint8Array(base64Url: string): Uint8Array {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from(Array.from(raw).map((c) => c.charCodeAt(0)));
}

export function pushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window;
}

export async function getPushSubscriptionStatus(): Promise<"subscribed" | "unsubscribed" | "unsupported"> {
  if (!pushSupported()) return "unsupported";
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  return sub ? "subscribed" : "unsubscribed";
}

export async function subscribeToPush(): Promise<void> {
  if (!pushSupported()) throw new Error("Push notifications aren't supported on this browser/device.");

  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notification permission was not granted.");

  const { publicKey } = await api.pushVapidPublicKey();
  if (!publicKey) throw new Error("Server has no VAPID public key configured.");

  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    // Cast needed: lib.dom.d.ts's BufferSource/ArrayBufferView typing is
    // stricter than the Push API spec actually requires here (a plain
    // Uint8Array is valid per spec; TS just can't prove it structurally).
    applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
  });

  const json = sub.toJSON();
  await api.pushSubscribe(json.endpoint!, json.keys!.p256dh, json.keys!.auth);
}

export async function unsubscribeFromPush(): Promise<void> {
  if (!pushSupported()) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return;
  await api.pushUnsubscribe(sub.endpoint);
  await sub.unsubscribe();
}
