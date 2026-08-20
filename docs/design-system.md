# SWARM — Design System

> **Canonical source.** `docs/design-system/v1.html` — the SWARM Brand
> Aesthetic v1.0 reference document. The HTML is authored as a 30-spread
> A4 print-ready brand book; we keep it in the repo so the design system
> is versioned alongside the code that consumes it.
>
> **Superseded in one respect.** v1 specifies flat surfaces — no shadow beyond
> a 1 px inset highlight, no translucency. The v2 direction recorded in
> [`CLAUDE.md`](../CLAUDE.md) replaces that: depth, elevation and measured
> translucency are permitted and are expected to carry hierarchy. Everything
> else in v1 — the palette, the type scale, the accent budget, the contrast
> ramp below — still stands. Until v1.html is reauthored, treat CLAUDE.md as
> the authority on depth and v1.html as the authority on everything else.

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
| Type families | 13 (Body & UI) | Cormorant Garamond (editorial), Inter (display/body), JetBrains Mono (telemetry), Space Grotesk (eyebrow) |
| Type scale | 13 | Hero 144 / H1 64 / H2 40 / H3 28 / Lede 17 / Body 15 / UI 13 / Eyebrow 11 |
| Spacing | 17 (Layout) | 4 / 8 px scale up to 128 px |
| Radius | 18 (Cards) | 6 px cards · 4 px inputs · 2 px chips · 999 px pills |
| Motion | 16 (Motion) | `cubic-bezier(0.2, 0.7, 0.1, 1)` · 900ms loader · 4000ms breath · brightness on hover |
| Iconography | 15 | 24×24 grid · stroke-only 1.5px · round caps · platinum at rest |
| Voice | 20 / 21 / 22 | Sentence case · periods are weapons · use orbit/node/unit · avoid drone/AI/platform |

### Why Inter for display/body

Spread 13 declares `--font-display:'Satoshi','Inter',system-ui,sans-serif`.
Google Fonts does not serve Satoshi (`css2?family=Satoshi` → HTTP 400), so
**Inter is the face the brand book actually renders**, and the Console now
matches it rather than substituting Geist.

Inter is also the right call on legibility grounds. The Console is built almost
entirely from 11–13px labels, and at that size the deciding metric is x-height
as a fraction of the em (measured from the latin subsets Google serves):

| Face | x-height / em | `opsz` axis |
|---|---|---|
| **Inter** | **0.546** | **yes (14–32)** |
| Geist | 0.530 | no |
| Public Sans | 0.517 | no |
| IBM Plex Sans | 0.516 | no |
| Roboto Flex | 0.514 | yes (8–144) |
| Atkinson Hyperlegible | 0.496 | no |

Inter has the largest x-height of the candidates *and* an optical-sizing axis.
`app/layout.tsx` requests the variable `Inter:opsz,wght@14..32,300..700` and
`styles/globals.css` sets `font-optical-sizing: auto`, so the face widens its
spacing and opens its apertures on its own as type gets smaller. Note that the
Google-hosted Inter does not expose the `cv**`/`ss**` character variants — only
`calt`, `tnum`, `pnum`, `frac` — so do not write `font-feature-settings` rules
against those; they are no-ops here.

### Why JetBrains Mono for telemetry

The mono face carries every operational number, at 9–13px. Same metric, same
reasoning:

| Face | x-height / em | zero | ligatures |
|---|---|---|---|
| **JetBrains Mono** | **0.550** | dotted | `calt` — must be suppressed |
| IBM Plex Mono | 0.516 | dotted | none |
| Roboto Mono | 0.528 | plain oval | none |

JetBrains Mono gives 6.6% more apparent size than IBM Plex Mono at the same px.
Both already disambiguate zero with an interior dot, so that is a wash — the
x-height is the whole reason. IBM Plex Mono also draws `0` and `O` at identical
ink widths (0.488 em each), leaving the dot as the only cue; JetBrains Mono
separates them (0.440 / 0.424 em) as well as dotting the zero.

JetBrains Mono does ship `calt` code ligatures (`->`, `!=`, `==`). Telemetry is
not code, and a fused glyph inside a coordinate, unit ID or timestamp would
misreport operational state, so `styles/globals.css` sets
`font-variant-ligatures: none` on every selector that reaches the mono face.

### Console mono: Roboto Mono, not JetBrains Mono

`components/console/` (the `/demo/intrusion` surface) uses a second mono face,
`consoleMono` in `lib/tokens.ts`, exposed as the `font-console-mono` Tailwind
utility. The legacy `/` dashboard keeps `font-mono` → JetBrains Mono exactly as
above; the two now diverge on purpose rather than by omission.

JetBrains Mono is a code-editor brand face, and at the density this console
sets it — every operational number, tracked and often uppercase — it read as a
terminal rather than an operator console. Retested every mono candidate from
this doc plus three more against the same metric used above (canvas-rendered
lowercase `x` at 400px, pixel bounds of the glyph / em):

| Face | x-height / em | vs JetBrains Mono | zero |
|---|---|---|---|
| **JetBrains Mono** | **0.547** | — | dotted |
| **Roboto Mono** | **0.527** | **−3.7%** | slashed |
| DM Mono | 0.493 | −9.9% | slashed |
| Space Mono | 0.493 | −9.9% | slashed |
| IBM Plex Mono | 0.516 | −5.7% | dotted, ties `O` ink width |
| Red Hat Mono | 0.487 | −11.0% | slashed |

Roboto Mono is the only candidate that loses less than the 6.6% gap that ruled
out IBM Plex Mono in the first place, so it is the only one that does not
trade away this console's own legibility floor to get a calmer face. It reads
as Android/Material system UI rather than an IDE, which is the actual
complaint being answered, and its zero is slashed — Google Fonts' current
build, contra the "plain oval" this doc originally logged against it; type
foundries revise metrics, so that line was stale rather than wrong at the
time. Self-hosted the same way as the rest of this stack: `latin` +
`latin-ext` from the `css2` variable-weight request, `300 700`, under
`public/fonts/roboto-mono-*`.

### Label contrast

`ash` is the label tier and the second most used text colour in the Console (97
`text-ash` call sites), all of it at 9–13px — never "large text" under WCAG. The
brand-book value `#6B7480` did not clear the 4.5:1 AA floor on any surface it
renders on, so it was lightened along its own hue to `#7F8A98`:

| Surface | `#6B7480` (was) | `#7F8A98` (now) |
|---|---|---|
| absolute-black `#030406` | 4.33:1 | 5.85:1 |
| obsidian `#0B0E11` | 4.09:1 | 5.52:1 |
| graphite/30 hover `#14181D` | 3.76:1 | 5.09:1 |
| graphite/40 hover `#171C21` | 3.62:1 | 4.89:1 |
| graphite/60 selected `#1E2328` | 3.34:1 | 4.52:1 |

The hovered row, not the card, was the binding constraint. `ash` stays clearly
recessive after the change — relative luminance 0.250 against muted-silver's
0.425 and platinum's 0.870 — so the three text tiers still read as three tiers.

Anything below `ash` on the ramp (`graphite` at 1.47:1, `mist-lo`/`ink-2` at
1.94:1) is a border, fill or divider colour. Do not set text in them.

### The accent budget, and how to stay inside it

"85% monochrome" is measurable, so measure it. Counting characters of visible
text on `/dev/replay?at=30000`, the operational console read:

| | before | after |
|---|---|---|
| monochrome | 69.6% | **85.9%** |
| launch-amber | 14.8% | 6.2% |
| orbital-blue | 9.4% | 3.3% |
| signal-green | 6.2% | 4.5% |
| **accent total** | **30.4%** | **14.1%** |

Amber alone had been consuming almost the entire 15% budget. The cause was not
volume but category error — accent was being spent on things that are not
states:

- **identifiers** — `OBJ 01`, `thermal-array-02`, `perimeter-cam-04`, owner and
  mission ids, timeline lane labels
- **standing statements** — `DECIDES WHAT THE FLEET SHOULD DO`,
  `SWARMOS DECIDES · PHYSICAL AGENTS EXECUTE`
- **panel headers and counts** — `FOCUS OBJ 02`,
  `CONCURRENT MISSION OWNERSHIP · 2 EXECUTING`
- **explanations** — the sentence describing *why* an agent was excluded

The test to apply before colouring anything: **would this text change colour if
the fleet's state changed?** If not, it is monochrome. When a state needs
calling out but its explanation does not, colour the verdict and leave the
sentence monochrome — `EXCLUDED` in amber, `FROM OBJ 02 · BUSY` in silver — or
mark the line with a small amber square and keep the words neutral.

What legitimately keeps an accent: link state, the agent SwarmOS selected,
execution phase, verified PX4 evidence, exclusion verdicts, and the
simulated-imagery and replay claim boundaries.

The audit that produces the table above is worth re-running after any change to
this surface, alongside a clip-aware check for text painted over text — note
that SVG elements report a lowercase `tagName`, so a case-sensitive filter
silently skips the entire map.

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
