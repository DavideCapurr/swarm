"use client";

/**
 * SceneHeader — bilingual editorial claim above the viewport.
 *
 * NOT DS-canon Spread 24. This is the **YC pitch surface**: a one-line
 * answer (en + it) that names the wedge (autonomous wildfire patrol on
 * private land) plus a sim-vs-real boundary chip. Justified by playbook
 * §5.4 (one-line answer), §12.1 (open-on-territory demo), §15 (claim
 * discipline). Reads sub-context from `useSwarm()`.
 */

import { useSwarm } from "@/lib/state";
import { SCENE_HEADER } from "@/lib/copy";

export function SceneHeader() {
  const { session, units, awareness } = useSwarm();
  const siteLabel = session?.site_id ?? "vineyard-01";
  const dockedCount = units.filter((u) => u.fsm_state === "DOCKED").length;
  const totalCount = units.length;
  const coveragePct = Math.round(awareness.score);

  return (
    <header className="bg-absolute-black border-b border-gunmetal px-6 py-4 flex items-start justify-between gap-6">
      <div className="flex flex-col gap-1">
        <h1
          className="font-editorial text-platinum"
          style={{ fontSize: 22, lineHeight: 1.15, letterSpacing: "-0.005em" }}
        >
          {SCENE_HEADER.en.title}{" "}
          <em className="text-ash" style={{ fontStyle: "italic" }}>
            {SCENE_HEADER.en.italic}
          </em>
        </h1>
        <p
          className="font-editorial text-ash"
          style={{ fontSize: 13, lineHeight: 1.3, fontStyle: "italic" }}
        >
          {SCENE_HEADER.it.title}{" "}
          <em>{SCENE_HEADER.it.italic}</em>
        </p>
        <p className="eyebrow-mono mt-2 text-ash">
          sector · {siteLabel} · langhe ·{" "}
          <span className="mono-num text-platinum">
            {String(dockedCount).padStart(3, "0")} / {String(totalCount).padStart(3, "0")}
          </span>{" "}
          docked · coverage{" "}
          <span className="mono-num text-platinum">
            {String(coveragePct).padStart(3, "0")} %
          </span>
        </p>
      </div>
      {/*
        Sim badge stays hardcoded `simulation · wildfire scenario` until
        Phase 8 introduces a `Session.environment` field on the backend.
        Adding runtime-gating now would require a model change + Alembic
        migration that is out of scope for Phase 7. The badge must remain
        always-visible while the only running surface is the sim (playbook
        §15 claim-discipline rule). Tracked in docs/STATUS.md · Phase 7.F.
      */}
      <span
        className="eyebrow-mono text-ash border border-gunmetal rounded-chip px-3 py-1 whitespace-nowrap"
        data-testid="sim-badge"
      >
        {SCENE_HEADER.sim_badge}
      </span>
    </header>
  );
}
