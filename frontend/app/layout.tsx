import "../styles/globals.css";
import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "SWARM · Control",
  description: "Many units. One intention.",
};

// SWARM brand fonts — loaded from Google Fonts.
// Editorial · Cormorant Garamond · for headings + the wordmark
// Display/body · Geist (fallback Inter) · UI
// Mono · IBM Plex Mono · for telemetry, coordinates, numerals
// Grotesk · Space Grotesk · for eyebrows + structural labels
const FONTS_HREF =
  "https://fonts.googleapis.com/css2" +
  "?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500" +
  "&family=Geist:wght@300;400;500;600;700" +
  "&family=Inter:wght@300;400;500;600;700" +
  "&family=IBM+Plex+Mono:wght@300;400;500;600" +
  "&family=Space+Grotesk:wght@400;500;600" +
  "&display=swap";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href={FONTS_HREF} />
      </head>
      <body className="bg-absolute-black text-platinum min-h-screen">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
