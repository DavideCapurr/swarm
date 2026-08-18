# Console render audit

What the operational console actually paints, measured on the rendered page
rather than judged by eye.

The console is delivered as a two-minute video and one screenshot inside the YC
application. That filter decides what counts as a defect: things a viewer cannot
scroll or hover away from. Text painted over text, live readouts truncated to an
ellipsis, and the decision rationale sitting below the fold.

## The viewport is not a choice

[`docs/design/operational-console-ia.md`](../design/operational-console-ia.md) §3
specifies **2560 × 1440 at device pixel ratio 1, no page scroll**, and notes that
smaller viewports degrade rather than break. That is the size the surface is
designed to and recorded at, so it is this script's default.

It is a flag rather than a constant because measuring at a self-chosen size is
how this has already gone wrong twice. Commit `62a09d2` reverted a rail change
made on the strength of a 1760 × 1000 measurement nobody had specified. The first
version of *this* document repeated the mistake at 1920 × 1080 and reported
truncation and a folded decision rail as defects; neither exists at the specified
size. Use `--viewport` to check how the surface degrades, never to establish a
criterion.

## How to run it

```bash
cd frontend && pnpm dev            # in one terminal
uv run python scripts/console_render_audit.py
uv run python scripts/console_render_audit.py --viewport 1920x1080   # degradation check only
```

Playwright is pinned in the `dev` extra, so `make setup` installs the library.
The wheel carries no browser; on a machine that has never run this audit,
download Chromium once:

```bash
uv run python -m playwright install chromium
```

One time per machine, not per session. Chromium comes from
`SWARM_CHROMIUM_PATH`, else `PLAYWRIGHT_BROWSERS_PATH`, else that download.

## What it measures, and why it measures it that way

- **Glyph collisions** come from `Range.getClientRects()` over text nodes, not
  element rects. An empty `div` as wide as its column produces false positives;
  glyph boxes do not.
- **The measurement is clip-aware.** A rect is intersected with every ancestor
  that clips it, so a row scrolled out of a panel is not reported as
  overprinting the panel below.
- **A collision must be deep on both axes** — 20% of the shorter box. Area alone
  over-reports: `getClientRects()` returns the font's line box, which is taller
  than the ink in it, so two timeline labels 13 px apart graze by a fifth of a
  pixel and a long label turns that into 62 px² of nothing.
- **Boxes from the same text node are never compared.** On an ellipsized element
  Chromium returns two rects for one run of text — full width and visible width,
  same origin — which would count every truncated readout again under the wrong
  heading.
- **SVG elements report a lowercase `tagName`.** A case-sensitive filter
  silently skips the entire map.

### The two surfaces

`/demo/intrusion` and `/dev/replay` render the same `OperationalConsole`. The
recorded surface carries the longer session label `SIMULATED OPERATING SCENARIO`
and no REPLAY badge, so `app/dev/replay` accepts `?label=` and `?replay=0` to
reproduce that width without the PX4 bench — on a route already 404 in a
production build. Measured: both variants give identical numbers.

### The sample points

Take A is 62.7 s.

| sample | at | why |
|---|---|---|
| `calm` | T+12s | the quiet frame |
| `second-event` | T+30s | both missions active — steps 6–7 of the target sequence |
| `evidence-lands` | T+44s | verified arrival lands and lengthens the last causal link |
| `final-frame` | T+62s | worst case, and the frame that becomes the screenshot |

## What was actually wrong, at 2560 × 1440

Measured on `main` (`0ec686e`) with the brand faces self-hosted:

| | before | after |
|---|---|---|
| glyph collisions | 3 / 4 / 4 / 4 | 0 / 0 / 0 / 0 |
| truncated readouts | 0 | 0 |
| decision rail in frame | 01–06 | 01–06 |
| ground / panel body | `rgb(3,4,6)` / `rgb(3,4,6)` | `rgb(11,14,17)` / `rgb(19,25,32)` |

Two defects, not five:

- **Map captions overlap their own second line.** Every collision is an entity's
  id line over its own state line — never one entity's label over another's. The
  agent caption put 16 px between an 18 px face and its state line, the objective
  caption 21 px for a 20 px face. Both now derive the gap from the font size at
  1.3, the ratio a normal line box uses. The objective gap had already been
  raised once, 17 px to 21 px, and was still short; deriving it is what stops a
  third round.
- **The page ground and the panel bodies were the same colour.** Everything
  marking a panel edge was a 1 px hairline, which is the high-frequency detail a
  block transform smears first. Three greyscale steps now — ground 28, panel body
  37, raised chrome 43 in limited-range code values.

The ramp's top step is capped by accessibility, not taste: `ash` measures 4.69:1
on `surface2`, and the next step up drops it to 4.37 and breaks the AA floor
`fbb26bd` established.

### The detector was checked against the defect it exists to find

With the old caption leading restored it still reports 268, 244 and 110 px²;
with the fix, zero. It also agrees with the earlier `387e689` judgement, catching
the 17 px objective separation that commit fixed and clearing the 21 px result.

### A correction to the compression argument

The surface ramp was first argued on the grounds that values under code value 16
are crushed to black. That is wrong: Rec.709 limited range *rescales* 0–255 into
16–235, it does not clip. The real defect was simpler — the separation between
ground and panel was exactly zero code values, and no encoder preserves a
distinction that does not exist.

### What is not verified here

**The compressed-file check has not been run.** The ffmpeg bundled with
Playwright in this environment is a screencast build with no H.264 encoder and no
PNG decoder, so no delivered-bitrate encode could be produced. The numbers above
are page measurements and colourimetry, both deterministic; how the ramp survives
a real encode remains a founder-machine step, like
`scripts/m1_capture_screenshots.py`. Record a take, encode at the delivery
bitrate, and confirm the panel edges still read.

## Degradation at 1920 × 1080

Not a criterion — recorded so the cliff is known. At that size, with the fixes
above in place, the control-loop strip truncates five readouts from T+44s to the
end of the take, including `SELECT mav-001`, and the decision rail shows only
steps 01–03, leaving `04 MISSION OWNERSHIP` below the fold. Both are the spec's
"degrade rather than break", and both are invisible in a recording: nobody
scrolls, and an ellipsis does not announce itself.

If the recording size ever has to drop, these are the two things to fix first.
