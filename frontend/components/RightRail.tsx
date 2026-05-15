"use client";

/**
 * RightRail — the operator's secondary surface.
 *
 * Rail order is mode-driven (PDF §5.10):
 *   rest         → patrol · risk · weather · link
 *   patrol       → risk · patrol · link · weather
 *   verification → anomaly · risk · link · weather · patrol
 *   escalation   → anomaly · risk · link · patrol · weather
 *   maintenance  → link · risk · patrol · weather
 */

import type { ReactNode } from "react";

import { useSwarm } from "@/lib/state";
import { AnomalySummary } from "./AnomalySummary";
import { LinkHealth } from "./LinkHealth";
import { NextPatrol } from "./NextPatrol";
import { RiskState } from "./RiskState";
import { WeatherLock } from "./WeatherLock";

type CardId = "anomaly" | "risk" | "patrol" | "weather" | "link";

const ORDER: Record<
  "rest" | "patrol" | "verification" | "escalation" | "maintenance",
  CardId[]
> = {
  rest: ["patrol", "risk", "weather", "link"],
  patrol: ["risk", "patrol", "link", "weather"],
  verification: ["anomaly", "risk", "link", "weather", "patrol"],
  escalation: ["anomaly", "risk", "link", "patrol", "weather"],
  maintenance: ["link", "risk", "patrol", "weather"],
};

const CARD: Record<CardId, () => ReactNode> = {
  anomaly: () => <AnomalySummary />,
  risk: () => <RiskState />,
  patrol: () => <NextPatrol />,
  weather: () => <WeatherLock />,
  link: () => <LinkHealth />,
};

export function RightRail() {
  const { mode } = useSwarm();
  const order = ORDER[mode.value];
  return (
    <div className="flex flex-col gap-3">
      {order.map((id) => (
        <div key={id}>{CARD[id]()}</div>
      ))}
    </div>
  );
}
