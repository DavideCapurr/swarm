import { ReactNode } from "react";

import { SwarmStateProvider } from "@/lib/state";

export const metadata = {
  title: "SWARM · Mobile",
  description: "Mobile heads-up. Console confirms.",
  viewport: "width=device-width, initial-scale=1, viewport-fit=cover",
};

export default function MobileLayout({ children }: { children: ReactNode }) {
  return <SwarmStateProvider>{children}</SwarmStateProvider>;
}
