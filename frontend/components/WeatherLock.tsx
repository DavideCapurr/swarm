"use client";

/**
 * WeatherLock — dock weather hold state.
 *
 * SwarmOS sets `DockState.weather_lock` as the truth signal. Wind / visibility
 * are emitted when known; the rail renders "—" otherwise — never invented
 * numerals. No red — escalation stays amber.
 */

import { useSwarm } from "@/lib/state";
import { IconWeather } from "@/icons";
import { Eyebrow } from "./Eyebrow";

export function WeatherLock() {
  const { primaryDock } = useSwarm();
  const dock = primaryDock;
  const locked = !!dock?.weather_lock;
  const state = locked ? "text-launch-amber" : "text-signal-green";
  const label = locked ? "weather hold" : "clear";

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Weather lock</Eyebrow>
        <span className={`eyebrow-mono ${state}`}>{label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className={state}>
          <IconWeather size={28} />
        </span>
        <div className="flex flex-col">
          <span className="mono-num text-platinum text-lede">
            {dock?.wind_mps != null ? `${dock.wind_mps.toFixed(1)} m/s` : "—"}
          </span>
          <span className="eyebrow-mono">wind · surface</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">visibility</span>
        <span className="text-right mono-num text-platinum">
          {dock?.visibility_km != null ? `${dock.visibility_km.toFixed(1)} km` : "—"}
        </span>
        <span className="eyebrow-mono">temp</span>
        <span className="text-right mono-num text-platinum">
          {dock?.temp_c != null ? `${dock.temp_c.toFixed(0)} °C` : "—"}
        </span>
      </div>
      {locked && (
        <span className="eyebrow-mono text-launch-amber">
          weather hold · dispatch deferred
        </span>
      )}
    </div>
  );
}
