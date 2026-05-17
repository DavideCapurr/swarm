"use client";

import { use } from "react";

import { MobileAnomalyScreen } from "@/components/MobileAnomalyScreen";

export default function MobileAnomalyPage({
  params,
}: {
  params: Promise<{ anomaly: string }>;
}) {
  const { anomaly } = use(params);
  return <MobileAnomalyScreen anomalyId={anomaly} />;
}
