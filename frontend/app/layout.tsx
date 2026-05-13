import "../styles/globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SWARM OS — Operator Dashboard",
  description: "Many units. One intention.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg text-ink min-h-screen">{children}</body>
    </html>
  );
}
