"use client";

/**
 * /system — system page: docks + unit readiness.
 *
 * One DockDetail per dock; UnitReadiness card per unit. No invented numerals
 * — fields render "—" until the server emits them.
 */

import { useSwarm } from "@/lib/state";
import { DockDetail } from "@/components/DockDetail";
import { Eyebrow } from "@/components/Eyebrow";
import { UnitReadiness } from "@/components/UnitReadiness";

export default function SystemPage() {
  const { docks, units, awareness, session } = useSwarm();
  return (
    <main className="flex-1 px-6 py-6 flex flex-col gap-6 overflow-y-auto">
      <header className="flex items-baseline justify-between">
        <h1 className="font-editorial text-h3 text-platinum">System</h1>
        <span className="eyebrow-mono">
          {session?.site_id ?? "—"} · coverage {String(Math.round(awareness.score)).padStart(3, "0")} %
        </span>
      </header>

      <section className="flex flex-col gap-3">
        <Eyebrow mono>Docks</Eyebrow>
        {docks.length === 0 ? (
          <span className="eyebrow-mono text-ash">no docks reported</span>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {docks.map((d) => (
              <DockDetail key={d.dock_id} dock={d} />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <Eyebrow mono>units · {String(units.length).padStart(3, "0")}</Eyebrow>
        {units.length === 0 ? (
          <span className="eyebrow-mono text-ash">no units online</span>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {units.map((u) => (
              <UnitReadiness key={u.agent_id} unit={u} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
