# ADR 0004 — Design system as a canonical source

**Status**: Accepted
**Date**: 2026-05-14
**Supersedes**: the "design system placeholder" path in ADR-0001.

## Context

The SWARM Brand Aesthetic v1.0 was delivered as an HTML brand book
(`SWARMdesignsystemv1.html`, 30 print-ready spreads). Until now the
frontend shipped with placeholder tokens. Two questions:

1. Where does the design system live in the repo?
2. How does the frontend consume it without drift?

## Decision

1. **The HTML is the canonical source**, stored at
   `docs/design-system/v1.html` and versioned with the code.
2. The frontend extracts tokens from it once, into
   `frontend/lib/tokens.ts`. That is the only place hex codes, fonts,
   type scale, spacing, radii, and motion live in the codebase.
3. All other layers (Tailwind theme, base CSS, components) read from
   `tokens.ts`. No component declares its own hex.
4. **Brand-language identifiers are preserved.** The accent triple is
   named `orbital-blue` / `signal-green` / `launch-amber` in code even
   though the actual hex values are lime / purple / magenta. The names
   are intentional brand poetry; the hex is the truth. Renaming them
   would erase the brand voice.
5. **Voice and state semantics are first-class.** The mapping from
   SWARM-OS `AgentState` to brand states (`rest` / `connected` /
   `operational` / `attention`) lives in `tokens.ts:agentStateToSwarm()`.
   Components never branch on `AgentState` directly — they branch on
   the brand state.

## Consequences

- One source of truth, one update path. Bumping the design system to
  v2 is: replace the HTML, regenerate the tokens, audit components.
- The Control surface respects the brand book without being a literal
  reproduction of spread 24 — the brand book is a frame, the product
  is the artifact.
- Future operator capabilities (alerts, multi-territory, mission
  editor) inherit the design language for free as long as they
  consume `tokens.ts`.

## Alternatives considered

- **External design system package** (npm) — rejected: introduces a
  second repo to update for a single-product codebase.
- **CSS-only token import** (importing the HTML's `<style>` block
  directly) — rejected: HTML is a brand reference, not a CSS module;
  it carries 30 layout-specific styles that don't apply to the app.
- **Figma as canonical** — rejected: Figma is the design tool, not the
  versioned artifact. The HTML brand book travels with the repo.
