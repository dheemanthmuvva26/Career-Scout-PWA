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
  themeColor: "#020b0f",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
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
        {/* SW registration — required for Web Share Target + offline */}
        <script dangerouslySetInnerHTML={{ __html:
          `if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').then(function(r){console.log('[SW]',r.scope)}).catch(function(e){console.warn('[SW] failed',e)})})}`
        }}/>
        {/* View Transitions API polyfill hint — enable smooth page animations */}
        <script dangerouslySetInnerHTML={{ __html:
          `document.documentElement.classList.add('js')`
        }}/>
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
