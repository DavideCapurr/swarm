import { ReactNode } from "react";

import { Footer } from "@/components/Footer";
import { HeadBar } from "@/components/HeadBar";
import { SwarmStateProvider } from "@/lib/state";

export const metadata = {
  title: "SWARM · Console",
  description: "SwarmOS console — one map, one intention.",
};

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  return (
    <SwarmStateProvider>
      <div className="min-h-screen flex flex-col">
        <HeadBar />
        <div className="flex-1 flex flex-col min-h-0">{children}</div>
        <Footer />
      </div>
    </SwarmStateProvider>
  );
}
