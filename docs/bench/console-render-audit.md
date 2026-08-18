# Console render audit

What the operational console actually paints, measured on the rendered page
rather than judged by eye.

The console is delivered as a two-minute video and one screenshot inside the YC
application. That filter decides what counts as a defect here: things a viewer
cannot scroll or hover away from. Text painted over text, live readouts
truncated to an ellipsis, and the decision rationale sitting below the fold.

## How to run it

```bash
cd frontend && pnpm dev            # in one terminal
python scripts/console_render_audit.py
python scripts/console_render_audit.py --json docs/bench/artifacts/console-render.json
```

Chromium is taken from `SWARM_CHROMIUM_PATH`, else from
`PLAYWRIGHT_BROWSERS_PATH`, else from Playwright's own download.

## What it measures, and why it measures it that way

- **Glyph collisions** come from `Range.getClientRects()` over text nodes, not
  from element rects. An empty `div` as wide as its column produces false
  positives; the glyph boxes do not.
- **The measurement is clip-aware.** A rect is intersected with every ancestor
  that clips it before it counts, so a row scrolled out of a panel is not
  reported as overprinting the panel below it.
- **SVG elements report a lowercase `tagName`.** A case-sensitive filter
  silently skips the entire map — the surface carrying the most collisions.
- **Boxes from the same text node are never compared.** On an ellipsized
  element Chromium returns *two* rects for one run of text, the full width and
  the visible width, stacked on the same origin. Comparing them counts every
  truncated readout a second time under the wrong heading.

### The two surfaces

`/demo/intrusion` and `/dev/replay` render the same `OperationalConsole`.
They differ in two ways that affect horizontal pressure: the recorded surface
carries the longer session label `SIMULATED OPERATING SCENARIO` and no REPLAY
badge. Since reproducing it needs the PX4 bench, `app/dev/replay` accepts
`?label=` and `?replay=0` to reproduce that width without a backend — on a route
that is already 404 in a production build and never linked from the Console.

Measured: **the two variants produce identical numbers.** The command bar has
enough slack to absorb the longer label. Worth having checked rather than
assumed.

### The sample points

Take A is 62.7 s. Four frames carry the argument:

| sample | at | why |
|---|---|---|
| `calm` | T+12s | the quiet frame |
| `second-event` | T+30s | both missions active — steps 6–7 of the target sequence |
| `evidence-lands` | T+44s | verified arrival lands and the control loop starts truncating |
| `final-frame` | T+62s | worst case, and the frame that becomes the screenshot |

T+44s is not decorative. Sampled at eleven instants, the control-loop strip is
clean at T+12, 20, 26, 30, 35 and 41, and truncates from T+44 to the end. The
trigger is not the second event — which the strip carries fine — but the arrival
of verified evidence lengthening the last link. Sampling only T+12/30/62 would
have found the defect without ever seeing where it starts.

## Baseline — `387e689`, before any layout work

1920 × 1080, self-hosted faces.

| frame | collisions | truncated readouts | decision rail in frame |
|---|---|---|---|
| T+12s calm | 6 | 0 | 01–03 |
| T+30s second event | 11 | 0 | 01–03 |
| T+44s evidence lands | 12 | 5 | 01–03 |
| T+62s final frame | 12 | 5 | 01–03 |

### Fonts change the numbers, so they came first

The first baseline was taken while the brand faces still arrived from Google
Fonts, which the sandbox could not reach: every family collapsed onto one
proportional fallback and the run measured 4 collisions at T+12s and 6 at T+30s.
With the self-hosted faces in place the same frames measure 6 and 11.

JetBrains Mono is wider than the fallback, so the map captions overlap more, not
less. Measuring layout before the typography is settled understates the problem
and produces numbers that describe a rendering nobody will record.

### What the baseline says

- **The control loop loses the decision rationale.** Five readouts truncate from
  T+44s onward — `SELECT mav-001`, `mav-002 EXCLUDED · BUSY`,
  `e768f142 → mav-001` among them — and stay truncated for the last third of the
  take, including the screenshot frame. The deficits are 2–8 px.
- **The decision rail never reaches step 04.** `01–03` in frame at every sample,
  with 44–50% of the rail hidden. `04 MISSION OWNERSHIP` is below the fold from
  the first second to the last, which is the step the YC spec calls *"the
  Console exposes the decision rationale"*.
- **Map collisions are intra-caption, not cross-family.** Every one is an
  entity's own id line overlapping its own state line: agent captions separate
  two lines by 16 px for an 18 px face, objective captions by 21 px for a 20 px
  face. No agent label collides with an objective label in any sample.
- **The panel body and the page ground are the same colour**, `rgb(3, 4, 6)`, at
  every frame. Only a 1 px hairline separates a panel from the ground, which is
  the first thing a video encoder destroys.


## After the layout work

Same script, same viewport, same four frames, both surfaces.

| frame | collisions | truncated readouts | decision rail in frame |
|---|---|---|---|
| T+12s calm | 0 | 0 | 01–05 |
| T+30s second event | 0 | 0 | 01–04 |
| T+44s evidence lands | 0 | 0 | 01–04 |
| T+62s final frame | 0 | 0 | 01–04 |

Step 04 clears the fold with 14 px to spare at the three late frames and 47 px
at the calm one. `ground / panel body` reads `rgb(11, 14, 17) / rgb(19, 25, 32)`
instead of `rgb(3, 4, 6) / rgb(3, 4, 6)`.

### A correction to the detector

The first pass counted overlap area alone and reported 62 px² between two
timeline labels stacked 13 px apart. Nothing was painted over anything: the
labels are uppercase 11 px mono, whose ink is about 8 px tall inside a 13.2 px
line box, so the boxes grazed by a fifth of a pixel and a long label turned that
into area. A collision now has to be deep on **both** axes — 20% of the shorter
box — because grazing one axis is not ink over ink however long the run.

Checked against the defect it exists to find rather than assumed: with the old
caption leading restored, the stricter detector still reports 269, 245 and
111 px². It also agrees with the earlier `387e689` judgement, catching the 17 px
objective separation it fixed and clearing the 21 px result.

### A correction to the compression claim

The surface ramp was argued on the grounds that values under code value 16 are
crushed to black. That is wrong: Rec.709 limited range *rescales* full-range
0–255 into 16–235, it does not clip. The real defect was simpler and worse — the
page ground and the panel body were the **same colour**, so their separation was
zero code values and no encoder could preserve a distinction that did not exist.
Everything that marked a panel edge was a 1 px hairline, which is the
high-frequency detail a block transform smears first.

In limited-range code values the ramp now reads ground 28, panel body 37, raised
chrome 43.

### What is not verified here

**The compressed-file check has not been run.** The ffmpeg bundled with
Playwright in this environment is a screencast build with no H.264 encoder and
no PNG decoder, so a delivered-bitrate encode could not be produced. The numbers
above are page measurements and colourimetry, both deterministic; how the ramp
survives a real encode remains a founder-machine step, like
`scripts/m1_capture_screenshots.py`. Record a take, encode it at the delivery
bitrate, and confirm the panel edges still read.

The ramp's top step is capped by accessibility, not taste: `ash` measures 4.69:1
on `surface2`, and the next step up the ramp drops it to 4.37 and breaks the AA
floor `fbb26bd` established.
