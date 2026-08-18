import type { UnitState } from "./api";

/**
 * What the fleet telemetry on screen actually came from.
 *
 * The surface used to state `PX4 SITL TELEMETRY` as a literal in three places.
 * That is true of the recorded bench and false of every other configuration the
 * same Console serves — `make demo-*-sim` runs the simulated adapter and the
 * caption still claimed PX4. A provenance claim has to be read off the frames
 * that carry it, like every other value here: `UnitState` already ships
 * `vendor` and `model`.
 *
 * Nothing is inferred beyond what the units report. A MAVLink fleet whose model
 * does not say SITL is described as MAVLink plus its model, never upgraded to a
 * SITL or physical-flight claim.
 */
export function telemetrySourceLabel(units: Pick<UnitState, "vendor" | "model">[]): string {
  if (units.length === 0) return "AWAITING TELEMETRY";

  const vendors = new Set(units.map((unit) => unit.vendor));
  if (vendors.size > 1) return "MIXED TELEMETRY SOURCES";

  const [vendor] = [...vendors];
  const models = new Set(units.map((unit) => unit.model));
  const model = models.size === 1 ? [...models][0] : null;

  if (vendor !== "mavlink") {
    return `${vendor.replaceAll("_", " ").toUpperCase()} TELEMETRY`;
  }
  if (model && /sitl/i.test(model)) return "PX4 SITL TELEMETRY";
  return model ? `MAVLINK TELEMETRY · ${model.toUpperCase()}` : "MAVLINK TELEMETRY";
}
