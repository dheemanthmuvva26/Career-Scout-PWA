import withPWAInit from "@ducanh2912/next-pwa";

const withPWA = withPWAInit({
  dest: "public",
  cacheOnFrontEndNav: true,
  aggressiveFrontEndNavCaching: true,
  reloadOnOnline: true,
  workboxOptions: { disableDevLogs: true },
  // Explicit path (not the "worker" default) — this project uses a src/ dir
  // and the default resolution is ambiguous about root vs. src. Adds Web
  // Push (push + notificationclick) on top of the generated service worker.
  customWorkerSrc: "src/worker",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
};

export default withPWA(nextConfig);
