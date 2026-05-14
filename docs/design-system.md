# SWARM — Design System

> **Canonical source.** `docs/design-system/v1.html` — the SWARM Brand
> Aesthetic v1.0 reference document. The HTML is authored as a 30-spread
> A4 print-ready brand book; we keep it in the repo so the design system
> is versioned alongside the code that consumes it.

## How the design system is wired into the frontend

```
docs/design-system/v1.html        — canonical reference (30 spreads)
        │
        ▼
frontend/lib/tokens.ts            — token extraction (palette, fonts,
                                    type scale, spacing, radii, motion)
        │
        ├──▶ frontend/tailwind.config.ts   — Tailwind theme bindings
        │
        ├──▶ frontend/styles/globals.css   — base styles, focus ring,
        │                                    .swarm-wordmark, .eyebrow,
        │                                    .card, .dot, .pill, .mono-num
        │
        └──▶ frontend/components/*         — every UI component
```

## Token summary

| Token group | Source spread | Notes |
|---|---|---|
| Palette · monochrome | 08 (Color · Mono) | 14 grays from `absolute-black` to `platinum` + dual ink ramps |
| Palette · activation | 09 (Color · Activation) | `orbital-blue` lime, `signal-green` purple, `launch-amber` magenta — names are brand poetry, hex is the truth |
| Type families | 13 (Body & UI) | Cormorant Garamond (editorial), Satoshi/Inter (display/body), IBM Plex Mono (telemetry), Space Grotesk (eyebrow) |
| Type scale | 13 | Hero 144 / H1 64 / H2 40 / H3 28 / Lede 17 / Body 15 / UI 13 / Eyebrow 11 |
| Spacing | 17 (Layout) | 4 / 8 px scale up to 128 px |
| Radius | 18 (Cards) | 6 px cards · 4 px inputs · 2 px chips · 999 px pills |
| Motion | 16 (Motion) | `cubic-bezier(0.2, 0.7, 0.1, 1)` · 900ms loader · 4000ms breath · brightness on hover |
| Iconography | 15 | 24×24 grid · stroke-only 1.5px · round caps · platinum at rest |
| Voice | 20 / 21 / 22 | Sentence case · periods are weapons · use orbit/node/unit · avoid drone/AI/platform |

## State mapping (SWARM-OS ↔ brand)

The `AgentState` enum in `core/swarm_core/messages.py` maps to brand state
colors via `agentStateToSwarm()` in `frontend/lib/tokens.ts`:

| AgentState | SwarmState | Color | Use |
|---|---|---|---|
| DOCKED | `rest` | platinum (no halo) | Unit at the dock, charging |
| TAKEOFF | `connected` | orbital-blue lime | Just activated, ring lit |
| EN_ROUTE / ON_STATION / RTL / LANDING / DOCKING | `operational` | signal-green purple | Carrying out a mission |
| OFFLINE | `rest` | muted | Comms lost, not actionable |
| ERROR | `attention` | launch-amber magenta | Needs operator |

This matches the Control UI mockup in spread 24 verbatim:
RING-A · OP · RING-B · ATT · RING-D · LNK.

## Operator surface — beyond the static mockup

The design system's spread 24 is a brand-book frame, not a literal app
spec. The Control surface in `frontend/app/page.tsx` honors the design
language but adds operator-grade functionality the static frame does
not show:

- **Selection state** — clicking a unit row swaps the right panel from
  Fleet list to `UnitDetail` (live mission phase + progress, GPS, link
  health, action buttons).
- **Link badge** in the head bar — green = WS frames streaming, lime =
  reconnecting, magenta = lost.
- **Aggregate stats overlay** on the map — docked / airborne split.
- **Anomalies block** in the right panel — pending anomalies are
  pulled out as their own row with the attention dot.
- **Bilingual canon footer** — *"Many units. One intention." / "Molte
  unità. Una sola intenzione."* — per spread 22 voice rules.

## Voice rules (`docs/design-system/v1.html` spread 21)

- Sentence case. **Periods are weapons.** Never an exclamation.
- Third person · imperative. Rarely "we". Almost never "you".
- UPPERCASE only in the wordmark.
- Numerals: always digits. Telemetry is mono. Pad with leading zeros for
  sequence (`001 · 007 · 042`).
- Em-dash for pivots. The Italian counterpart matches the English rhythm.

### Use

`autonomy · intention · command · orbit · node · unit · signal · ring · silent · precise · inevitable · arrived · written · brought here · under command`

### Avoid

`drone · AI · neural · smart · next-gen · revolutionize · disrupt · unlock · empower · powerful · scalable · robust · cutting-edge · platform · solution`

## When the design system updates

1. Replace `docs/design-system/v1.html` (or add `v2.html` next to it).
2. Regenerate `frontend/lib/tokens.ts` from the new CSS variables.
3. `make lint` should catch token drift if a component uses a hex
   that no longer matches a token.
