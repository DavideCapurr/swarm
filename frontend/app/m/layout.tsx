import { ReactNode } from "react";

import { SwarmStateProvider } from "@/lib/state";

export const metadata = {
  title: "SWARM · Mobile",
  description: "Mobile heads-up. Console confirms.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function MobileLayout({ children }: { children: ReactNode }) {
  return <SwarmStateProvider>{children}</SwarmStateProvider>;
}
