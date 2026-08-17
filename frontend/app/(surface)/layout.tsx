import { ReactNode } from "react";

import { AuthGate } from "@/components/AuthGate";
import { SwarmStateProvider } from "@/lib/state";

/**
 * Full-viewport operational surface.
 *
 * Same authentication and same state provider as the Console layout, without
 * its editorial head bar and foot bar: this surface fills the screen, because
 * every pixel of it is operational state.
 */
export const metadata = {
  title: "SWARM · SwarmOS operational console",
  description: "Objective, fleet decision, mission ownership and verified execution evidence.",
};

export default function SurfaceLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate>
      <SwarmStateProvider>{children}</SwarmStateProvider>
    </AuthGate>
  );
}
