import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Career Scout",
  description: "Your personal AI career assistant",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Career Scout",
  },
};

export const viewport: Viewport = {
  themeColor: "#09090b",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="apple-touch-icon" href="/icon-192.png" />
        {/* Register service worker — required for Web Share Target to appear in Android share sheet */}
        <script dangerouslySetInnerHTML={{ __html:
          `if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').then(function(r){console.log('[SW] registered',r.scope)}).catch(function(e){console.warn('[SW] registration failed',e)})})}`
        }}/>
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
