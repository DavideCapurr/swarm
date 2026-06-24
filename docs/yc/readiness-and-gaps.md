# SWARM — YC readiness & gap plan

> Companion to [`application-draft.md`](application-draft.md). Brutally honest:
> what would get this rejected, and a dated plan to fix it before the deadline.
> Written 2026-06-23.

## The honest read

The **product/engineering** bar is already above most YC applicants:
end-to-end autonomous coordination in sim, real CV, a shadow-mode safety gate
with teeth, serious security, ~1000 passing tests, one-command demo. For a
founder who hasn't started university, this is a genuinely strong signal —
**this is the asset to lead with.**

But YC funds *companies*, and on the company axes SWARM is thin. The
application will live or die on closing these gaps, in priority order.

## Gaps that get this rejected (ranked)

| # | Gap | Why YC cares | Severity |
|---|---|---|---|
| 1 | **No user evidence.** "How do you know people need this" is a founder hunch, not quotes from buyers. | YC's single most-weighted thing after founders is *talking to users*. Zero is a red flag even for hard tech. | 🔴 Critical |
| 2 | **No live link / demo video doesn't exist yet.** `docs/yc/videos/` is empty; there's no public URL. | A reviewer spends ~1 min. No watchable proof = the strongest asset is invisible. | 🔴 Critical |
| 3 | **Founder commitment ambiguity.** Starting BIEF in Sept reads as "side project." | YC funds people who will go all-in. The school plan must be answered as a *strategy*, not a hedge. | 🟠 High |
| 4 | **Cofounder unresolved.** Solo (or recruiting) hard-tech. | YC prefers 2+ founders; solo is a known disadvantage. | 🟠 High |
| 5 | **No field/hardware proof.** Everything is sim. | Expected at this stage, but the "why should we believe this flies" answer must be crisp. | 🟡 Medium |
| 6 | **Regulatory reality unaddressed.** EU/EASA drone ops, BVLOS, privacy. | A reviewer will think "can they even fly this?" Needs a one-paragraph credible answer. | 🟡 Medium |
| 7 | **Market size not quantified.** No bottoms-up TAM. | "How much could you make" is unanswered. | 🟡 Medium |

**The reframe on #3/#4:** don't apologize for them — turn them into the
strategy. Early Decision *exists* for exactly this founder. A young technical
founder who shipped this much solo, applying via the program built for
students, with a clear "go all-in after the school year (or sooner if we get
in)" plan, is a coherent story. Hedging is the failure mode, not the calendar.

## What closes each gap (and who does it)

| # | Action | Owner | I can do now? |
|---|---|---|---|
| 1 | 10–15 real conversations with estate/vineyard managers, land-risk experts, drone operators in Piedmont; capture quotes on problem frequency, current alternative, budget owner, false-alarm cost. | Founder | I produce the **interview kit + target profile + one-pager** → [`customer-discovery-kit.md`](customer-discovery-kit.md) |
| 2 | Record the <2-min demo video; stand up a one-page public link. | Founder + me | ✅ **Live link built**: `frontend/public/landing/index.html` (self-contained, on-brand, no-red verified, hostable anywhere — deploy to Vercel/Netlify/GH-Pages, set the contact email). ⏳ Demo video still needs your machine (sim+backend+WebGL) via the [runbook](demo-recording-runbook.md). |
| 3 | Write the commitment answer as a strategy (Early Decision framing). | Founder | Drafted in `application-draft.md`; you finalize. |
| 4 | Decide: name the cofounder, or apply solo and address it head-on. | Founder | Application text handles both; the decision is yours. |
| 5 | One-paragraph "path to real flight": MAVLink/PX4 adapter already CI-ready → SITL → supervised bench. | Founder + me | I can draft from the real adapter state. |
| 6 | One-paragraph EU/EASA answer: supervised operator, Open/Specific category, privacy posture (back-view CV only, no faces stored). | Founder + me | I can draft from the threat-model + CV privacy posture. |
| 7 | Bottoms-up TAM: # private estates/territory × seasonal price. | Founder + me | I can draft a skeleton; you supply real price/volume. |

## Dated plan — two tracks, decide which to commit

Today: **2026-06-23**. Maturità finishing; summer code window open.

### Track A — Early Decision, aggressive (deadline 2026-07-27, ~5 weeks)

This applies *now*, locks a YES + funding, defers the batch past the BIEF
year. Highest urgency; lowest school disruption. Confirm deadline on
[ycombinator.com/apply](https://www.ycombinator.com/apply).

| Week | Dates | Goal | Concrete output |
|---|---|---|---|
| 1 | Jun 23–29 | Kill gap #2 (proof visible) | Record demo video; ship one-page live link; finalize one-liner. |
| 2 | Jun 30–Jul 6 | Attack gap #1 | 8+ buyer/expert conversations done; quotes logged in discovery kit. |
| 3 | Jul 7–13 | Finish gap #1 + #5/#6/#7 | Reach 12–15 conversations; draft regulatory + flight-path + TAM answers. |
| 4 | Jul 14–20 | Decide #3/#4; full draft | Cofounder decision made; every application field filled with real content. |
| 5 | Jul 21–27 | Polish + submit | Founder video re-takes; tighten copy; **submit before Jul 27 20:00 PT.** |

### Track B — Winter 2027 batch (deadline ~Nov 2026, implies BIEF leave)

Same work, more runway, but commits to relocating/leaving school for Jan–Mar
2027. Use the extra months to add **real evidence** (first supervised SITL
run; a written pilot-interest note from one buyer) that materially upgrades
the application above Track A.

| Milestone | By | Output |
|---|---|---|
| Demo + live link + discovery (gaps 1,2) | Aug 2026 | Same as Track A weeks 1–3. |
| SITL evidence (gap 5 → real) | Sep 2026 | One reproducible PX4/SITL run logged; truth table upgrades a row. |
| Pilot-interest signal (gap 1 → strong) | Oct 2026 | One honest written "would pilot" note from a real buyer (no fake LOIs). |
| Submit | ~Nov 2026 | Application with evidence Track A can't show. |

## Recommendation

Run **Track A work immediately regardless of which you submit** — the demo
video, live link, and customer conversations are mandatory for both and are
the highest-leverage things that exist. Decide A-vs-B only once the demo +
first ~5 conversations exist (~mid-July): if the signal is strong and you're
willing to defer the batch, submit Early Decision before Jul 27; if you want
to bring real SITL/pilot evidence and take the batch literally, hold for
Track B. Don't let the *decision* block the *work*.

## What I'll do next (in-repo, no founder machine needed)

1. ✅ Application draft + this gap plan.
2. ✅ Customer-discovery kit (interview script, target profile, one-pager copy).
3. ✅ Supporting answers (flight-path, regulatory/privacy, TAM) + researched competitive-and-market.
4. ✅ Demo recording runbook (YC-grade buyer-voice narration).
5. ✅ **Live one-page site** built + verified: `frontend/public/landing/index.html`.
   Deploy: drop the `landing/` folder on any static host (Vercel/Netlify/GH-Pages),
   or `python3 -m http.server --directory frontend/public` to preview locally
   (`/landing/`). **Set the contact email before publishing.**
6. On request: demo-capture harness; cofounder JD; fill personal application fields.
