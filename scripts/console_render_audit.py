"""Measure what the operational console actually paints, at the recording viewport.

The console is judged by a two-minute video and one screenshot inside the YC
application, so the defects that matter are the ones a viewer cannot scroll or
hover away from: text painted over text, live readouts truncated to an ellipsis,
and the decision rationale sitting below the fold.

This measures all three against the rendered page. Three details are load-bearing:

  * Collisions are computed from ``Range.getClientRects()`` over text nodes, not
    from element rects. An empty ``div`` as wide as its column produces false
    positives; the glyph boxes do not.
  * The measurement is clip-aware. A rect is intersected with every ancestor that
    clips it before it counts, so content scrolled out of a panel is not reported
    as overprinting the panel below.
  * SVG elements report a lowercase ``tagName``. A case-sensitive filter silently
    skips the entire map — the surface with the most collisions.

Run against a dev server (``pnpm dev``). ``/dev/replay?at=<ms>`` replays Take A
from recorded frames with no backend, so a measurement is reproducible frame for
frame; ``&label=`` and ``&replay=0`` reproduce the width pressure of the recorded
surface, whose session label is longer and which carries no REPLAY badge.

    python scripts/console_render_audit.py
    python scripts/console_render_audit.py --json docs/bench/artifacts/audit.json

Chromium comes from ``SWARM_CHROMIUM_PATH``, else from ``PLAYWRIGHT_BROWSERS_PATH``,
else from Playwright's own download. Nothing here writes to the repo unless asked.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = os.environ.get("SWARM_CONSOLE_URL", "http://localhost:3000")

# The recording viewport. Pinned in docs/bench/final-demo-rehearsal.md — every
# exit criterion in the layout work is stated at this size, so a measurement at
# any other size proves nothing about the take.
VIEWPORT = {"width": 1920, "height": 1080}

# The recorded surface's session label. `/demo/intrusion` sets this from
# IntrusionResponseDemo; it is materially wider than the replay harness's own
# "take a · recorded", and the command bar's spare width is what absorbs it.
RECORDED_LABEL = "SIMULATED OPERATING SCENARIO"

# Two frames carry the whole argument. T+12s is the calm frame. The second-event
# frame is where the control loop grows an exclusion link and the decision rail
# grows a step — the moment steps 6-8 of the target sequence are on screen. The
# final frame is the worst case: both agents have returned and every map glyph
# collapses onto the origin, and it is the frame that becomes the screenshot.
# T+44s is not decorative: measured across the take, the control loop is clean
# through the whole two-mission overlap and starts truncating only when verified
# arrival evidence lands, then stays truncated to the end. Sampling T+12/30/62
# alone would miss the instant the defect appears.
DEFAULT_SAMPLES = [
    ("calm", 12_000),
    ("second-event", 30_000),
    ("evidence-lands", 44_000),
    ("final-frame", 62_000),
]

# An overlap smaller than this is two adjacent line boxes touching, not text
# painted over text.
MIN_OVERLAP_PX2 = 4.0

# Area alone over-reports. `Range.getClientRects()` returns the font's line box,
# which is taller than the ink inside it: JetBrains Mono at 11px occupies about
# 13.2px of em box for roughly 8px of uppercase ink. Two rows 13px apart graze
# by a fifth of a pixel and, over a long label, that graze clears any area
# threshold while nothing is painted over anything.
#
# So a collision also has to be *deep on both axes*: the overlap must cover this
# fraction of the shorter box horizontally *and* vertically. Grazing one axis is
# not ink over ink, however long the run — two stacked timeline labels overlap
# 79% horizontally and 1.5% vertically, and nothing is painted over anything.
# The real defects measured on this surface — an agent's id line over its own
# state line — are deep on both.
MIN_OVERLAP_DEPTH = 0.2


def chromium_executable() -> str | None:
    """Resolve a Chromium the sandbox already has, rather than downloading one."""
    pinned = os.environ.get("SWARM_CHROMIUM_PATH")
    if pinned:
        return pinned
    browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not browsers:
        return None
    found = sorted(glob.glob(os.path.join(browsers, "chromium-*", "chrome-linux", "chrome")))
    return found[-1] if found else None


# The measurement itself. Kept in one expression so the page is walked once per
# sample and every number in a row describes the same paint.
MEASURE_JS = r"""
() => {
  const MIN_OVERLAP = %(min_overlap)s;
  const MIN_DEPTH = %(min_depth)s;

  // A rect is only real where its clipping ancestors let it show. Without this
  // an item scrolled out of a panel reads as overprinting whatever is below.
  const clipOf = (node) => {
    let el = node.parentElement;
    let clip = { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
    while (el) {
      const cs = getComputedStyle(el);
      const clips =
        cs.overflow !== 'visible' || cs.overflowX !== 'visible' || cs.overflowY !== 'visible';
      if (clips) {
        const r = el.getBoundingClientRect();
        clip = {
          left: Math.max(clip.left, r.left),
          top: Math.max(clip.top, r.top),
          right: Math.min(clip.right, r.right),
          bottom: Math.min(clip.bottom, r.bottom),
        };
      }
      el = el.parentElement;
    }
    return clip;
  };

  const intersect = (r, c) => {
    const left = Math.max(r.left, c.left);
    const top = Math.max(r.top, c.top);
    const right = Math.min(r.right, c.right);
    const bottom = Math.min(r.bottom, c.bottom);
    if (right - left <= 0.5 || bottom - top <= 0.5) return null;
    return { left, top, right, bottom };
  };

  const hidden = (node) => {
    let el = node.parentElement;
    while (el) {
      if (el.getAttribute && el.getAttribute('aria-hidden') === 'true') return true;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || cs.opacity === '0') return true;
      el = el.parentElement;
    }
    return false;
  };

  // Where a text box sits, for a human reading the report. `tagName` is
  // lowercase on SVG nodes, so compare case-insensitively or lose the map.
  const label = (node) => {
    const parts = [];
    let el = node.parentElement;
    while (el && parts.length < 4) {
      const testid = el.getAttribute && el.getAttribute('data-testid');
      if (testid) { parts.unshift(testid); break; }
      parts.unshift((el.tagName || '').toLowerCase());
      el = el.parentElement;
    }
    return parts.join('>');
  };

  // ── Text boxes ────────────────────────────────────────────────────────────
  // Each box remembers which text node it came from. Boxes from the same node
  // are never compared: on an ellipsized element Chromium returns two rects for
  // one run of text — the full width and the visible width — stacked on the same
  // origin. That is truncation, which is counted on its own below, not text
  // painted over text, and comparing them would report every truncated readout
  // twice under the wrong heading.
  const boxes = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let nodeIndex = 0;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = (node.textContent || '').trim();
    if (!text || hidden(node)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const clip = clipOf(node);
    const owner = nodeIndex++;
    for (const raw of Array.from(range.getClientRects())) {
      if (raw.width <= 0.5 || raw.height <= 0.5) continue;
      const r = intersect(raw, clip);
      if (!r) continue;
      boxes.push({ owner, text, where: label(node), rect: r });
    }
  }

  // ── Collisions ────────────────────────────────────────────────────────────
  const collisions = [];
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      if (boxes[i].owner === boxes[j].owner) continue;
      const a = boxes[i].rect;
      const b = boxes[j].rect;
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w <= 0 || h <= 0) continue;
      const area = w * h;
      if (area < MIN_OVERLAP) continue;
      // Deep enough to be ink over ink, not two line boxes grazing.
      const depthY = h / Math.min(a.bottom - a.top, b.bottom - b.top);
      const depthX = w / Math.min(a.right - a.left, b.right - b.left);
      if (Math.min(depthX, depthY) < MIN_DEPTH) continue;
      collisions.push({
        area: Math.round(area),
        a: boxes[i].text.slice(0, 70),
        b: boxes[j].text.slice(0, 70),
        aWhere: boxes[i].where,
        bWhere: boxes[j].where,
      });
    }
  }
  collisions.sort((x, y) => y.area - x.area);

  // ── Truncation ────────────────────────────────────────────────────────────
  // Only ellipsis counts. Plain `overflow: hidden` on a layout box is not a
  // readout losing its tail.
  const truncated = [];
  for (const el of Array.from(document.querySelectorAll('*'))) {
    const cs = getComputedStyle(el);
    if (!cs.textOverflow.startsWith('ellipsis')) continue;
    if (el.scrollWidth <= el.clientWidth + 1) continue;
    const text = (el.textContent || '').trim();
    if (!text) continue;
    truncated.push({
      text: text.slice(0, 90),
      lostPx: Math.round(el.scrollWidth - el.clientWidth),
      where: el.getAttribute('data-testid') || label(el.firstChild || el),
    });
  }
  truncated.sort((x, y) => y.lostPx - x.lostPx);

  // ── Content below the fold ────────────────────────────────────────────────
  const panelTitle = (el) => {
    const section = el.closest('section');
    const header = section && section.querySelector('header');
    return ((header && header.textContent) || '').trim().slice(0, 40) || '(unnamed)';
  };
  const clipped = [];
  for (const el of Array.from(document.querySelectorAll('*'))) {
    const cs = getComputedStyle(el);
    if (!['auto', 'scroll'].includes(cs.overflowY)) continue;
    if (el.scrollHeight <= el.clientHeight + 1) continue;
    clipped.push({
      panel: panelTitle(el),
      hiddenPct: Math.round((1 - el.clientHeight / el.scrollHeight) * 100),
      visiblePx: Math.round(el.clientHeight),
      totalPx: Math.round(el.scrollHeight),
    });
  }
  clipped.sort((x, y) => y.hiddenPct - x.hiddenPct);

  // The decision rail's causal chain is only "exposed" as far as it is on
  // screen. Steps 1-4 close the argument: objective, evaluation, selection,
  // ownership. Report the last step whose number is fully inside the rail.
  let lastVisibleStep = null;
  const rail = document.querySelector('[data-testid="decision-rail"]');
  if (rail) {
    const body = rail.querySelector(':scope > div:last-child');
    const view = (body || rail).getBoundingClientRect();
    const walk = document.createTreeWalker(rail, NodeFilter.SHOW_TEXT);
    for (let node = walk.nextNode(); node; node = walk.nextNode()) {
      const text = (node.textContent || '').trim();
      if (!/^0[1-9]$/.test(text)) continue;
      const r = node.parentElement.getBoundingClientRect();
      if (r.top >= view.top - 0.5 && r.bottom <= view.bottom + 0.5) {
        const n = Number(text);
        if (lastVisibleStep === null || n > lastVisibleStep) lastVisibleStep = n;
      }
    }
  }

  // Ground vs panel body, the pair that has to survive the encoder.
  const swatch = (sel) => {
    const el = document.querySelector(sel);
    return el ? getComputedStyle(el).backgroundColor : null;
  };

  return {
    textBoxes: boxes.length,
    collisions,
    truncated,
    clipped,
    lastVisibleStep,
    ground: swatch('main'),
    panelBody: swatch('[data-testid="decision-rail"]'),
  };
}
""" % {"min_overlap": MIN_OVERLAP_PX2, "min_depth": MIN_OVERLAP_DEPTH}


@dataclass
class Sample:
    name: str
    url: str
    result: dict = field(default_factory=dict)


async def measure(page, url: str) -> dict:
    await page.goto(url, wait_until="networkidle")
    # The console composes from frames; the control loop is the last thing to
    # settle. Wait for the surface, not for a timer.
    await page.wait_for_selector('[data-testid="control-loop-strip"]', timeout=20_000)
    await page.wait_for_timeout(400)
    return await page.evaluate(MEASURE_JS)


def render(samples: list[Sample]) -> str:
    out: list[str] = []
    for s in samples:
        r = s.result
        out.append(f"\n── {s.name} ─────────────────────────────────────────")
        out.append(f"   {s.url}")
        out.append(f"   text boxes measured : {r['textBoxes']}")
        out.append(f"   glyph collisions    : {len(r['collisions'])}")
        for c in r["collisions"][:6]:
            out.append(f"       {c['area']:>6} px²  {c['a']!r}")
            out.append(f"                     over {c['b']!r}")
        out.append(f"   truncated readouts  : {len(r['truncated'])}")
        for t in r["truncated"][:8]:
            out.append(f"       −{t['lostPx']:>4} px  {t['text']!r}")
        out.append("   below the fold      :")
        for c in r["clipped"]:
            out.append(
                f"       {c['hiddenPct']:>3}% hidden  {c['panel']!r}"
                f"  ({c['visiblePx']} of {c['totalPx']} px)"
            )
        step = r["lastVisibleStep"]
        out.append(f"   decision rail       : steps 01–{step:02d} in frame" if step else
                   "   decision rail       : no step numbers found")
        out.append(f"   ground / panel body : {r['ground']} / {r['panelBody']}")
    return "\n".join(out)


async def run(args: argparse.Namespace) -> int:
    urls: list[Sample] = []
    for name, at in DEFAULT_SAMPLES:
        base = f"{FRONTEND}/dev/replay?at={at}"
        urls.append(Sample(f"{name} · replay harness", base))
        urls.append(
            Sample(
                f"{name} · recorded surface",
                f"{base}&replay=0&label={RECORDED_LABEL.replace(' ', '%20')}",
            )
        )

    executable = chromium_executable()
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=executable)
        page = await browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        for sample in urls:
            sample.result = await measure(page, sample.url)
        await browser.close()

    print(render(urls))

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "viewport": VIEWPORT,
                    "samples": [{"name": s.name, "url": s.url, **s.result} for s in urls],
                },
                indent=2,
            )
        )
        print(f"\nwrote {path}")

    worst = max(len(s.result["collisions"]) for s in urls)
    worst_trunc = max(len(s.result["truncated"]) for s in urls)
    if args.fail_on_regression and (worst or worst_trunc):
        print(
            f"\nFAIL: {worst} collisions and {worst_trunc} truncated readouts remain",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="write the full measurement to this path")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit non-zero if any collision or truncated readout remains",
    )
    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
