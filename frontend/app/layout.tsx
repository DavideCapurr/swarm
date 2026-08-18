import "../styles/fonts.css";
import "../styles/globals.css";
import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "SWARM · Control",
  description: "Many units. One intention.",
};

// SWARM brand fonts — self-hosted under public/fonts, declared in
// styles/fonts.css.
// Editorial · Cormorant Garamond · for headings + the wordmark
// Display/body · Inter · UI
// Mono · JetBrains Mono · for telemetry, coordinates, numerals
// Grotesk · Space Grotesk · for eyebrows + structural labels
//
// Inter carries both its `opsz` (14-32) and `wght` (300-700) axes in one
// variable file. `font-optical-sizing: auto` in styles/globals.css activates
// opsz, so the console's dense 11-13px labels get the face's wider spacing and
// more open apertures automatically.
//
// These used to arrive from fonts.googleapis.com through a <link>. That put a
// network request in the middle of a recording: when it fails, all four
// families collapse onto one proportional fallback and every column of
// telemetry loses its alignment. See styles/fonts.css.

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-absolute-black text-platinum min-h-screen">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
