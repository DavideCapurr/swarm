# SWARM — YC interview prep

> If the application gets you an interview, **this is where acceptance is
> actually decided** — ~10 minutes, fast, partners interrupt, they probe the
> weakest point. Polish doesn't win it; crisp, honest, fast answers do. Built
> 2026-06-23 from the real project state. Practice these out loud until each
> answer is ≤20 seconds. Companion to [`readiness-and-gaps.md`](readiness-and-gaps.md).

## The format (so it doesn't surprise you)

- ~10 min video call, 1–4 partners, rapid-fire, they will cut you off.
- They're testing: do you *know your business cold*, are you *honest*, are you
  *fast and clear*, are you *formidable*. They are not testing your slides.
- Golden rules: **answer the question asked, in one sentence, then stop.** Lead
  with the number or the fact. Never bluff — "I don't know yet, here's how I'd
  find out" beats a confident guess. Don't argue; absorb and respond.

## The questions they *will* ask (SWARM-specific) + crisp answers

### On the product / what it is
- **"What does SWARM do, in one sentence?"**
  → "Autonomous drones that patrol private high-value land and verify threats —
  fire, intrusion — in minutes, with no fixed cameras or sensors installed."
- **"What have you actually built?"**
  → "An end-to-end autonomous coordination system, SwarmOS — it runs the full
  patrol-verify-evidence-escalate loop in simulation across three scenarios,
  with real computer-vision detection and a safety gate that checks every
  decision against a human baseline. ~1000 tests pass. I built it largely solo."
- **"Show me."** → Have the demo ready to screen-share in 5 seconds. Narrate in
  buyer voice ([`demo-recording-runbook.md`](demo-recording-runbook.md)), not phase numbers.

### On users / traction (your weakest area — rehearse hardest)
- **"How many users do you have?"**
  → "Zero paying today — I deliberately built the working system first. I've now
  done [N] conversations with estate managers and land-risk people in my region;
  here's the sharpest thing I heard: [real quote]." *(This answer is empty until
  you run the interviews. Do them.)*
- **"Why hasn't anyone paid you yet?"**
  → Honest: "I haven't asked for money yet — I'm validating the wedge and the
  price anchor first. The buyers I've talked to say [X]." Don't pretend demand
  you haven't tested.
- **"How do you know people want this?"** → Cite the conversations, not a hunch.

### On the market / why now
- **"Why now?"**
  → "Mediterranean wildfire risk is rising fast — it's already 86% of the EU's
  burned area — and drones + cheap autonomy just made mobile patrol economic for
  land that could never justify fixed towers."
- **"How big can this get?"** → Bottoms-up wedge first (estates × seasonal
  price), then the platform ladder. Don't lead with a $X billion TAM slide.

### On competition / defensibility (they'll push hard)
- **"Why won't Pano AI / Skydio / DJI just do this?"**
  → "They're all anchored to fixed infrastructure — towers, ground sensors,
  fixed docks — and to selling hardware. That locks them out of private mid-size
  land and gives them no reason to chase it. My product is the coordination OS,
  not the drone, and it starts capex-free."
- **"What's your unfair advantage?"**
  → "I can build the hard autonomy/coordination layer alone, fast, and I'm from
  the exact territory that needs it — I have buyer access others don't."
- **"What stops a funded competitor copying you?"** → The moat is the
  coordination OS + owned field-evidence data over time, not the demo.

### On the team / you (they'll probe the solo + school angle)
- **"Are you solo? Why?"**
  → Honest + framed: "[State reality — solo, or cofounder/recruiting.] I built
  the technical core to prove I can; I'm [closing / actively recruiting] the gap
  in [field-ops / commercial / hardware]." Never apologize; show you know the gap.
- **"You're starting university — is this a side project?"**
  → "No. I applied through Early Decision precisely so I can go all-in after the
  school year — or sooner if you take me. The system you saw is what I build when
  it's 'just' a side project; full-time is a different gear." Project total commitment.
- **"Would you drop out?"** → Have a real, honest answer ready *before* the call.
  Don't improvise this one — decide it with yourself first.

### On the hard-tech / flight reality
- **"Has this ever flown?"**
  → "Not yet — and I won't claim it has. The flight layer is a vendor-agnostic
  adapter with a CI-ready MAVLink/PX4 path; the next milestone is a logged SITL
  run, then a supervised bench. The hard, novel part — coordination you can
  trust — is the part that's done."
- **"Can you even legally fly drones for this?"**
  → "The MVP is human-supervised, inside the EASA Open/Specific category with a
  licensed operator — not unattended BVLOS. We patrol private land for its owner,
  so the consent and data story is clean. The harder envelope comes later, tied
  to evidence."

### The curveballs
- **"What's the biggest risk that kills this company?"** → Be honest and
  specific (e.g. "that buyers want it during a fire scare but won't pay for it
  weekly" — and how you're testing that). Honesty here scores points.
- **"What would you do with the money?"** → Concrete: first supervised
  flight evidence + first paid pilot. Not "hire a team."
- **"Why you?"** → 1 sentence, conviction, no hedging.

## Traps to avoid

- Don't overclaim — they catch it instantly and it's fatal. Your typed-claim
  discipline is an *asset*; use it.
- Don't ramble or give two answers. One sentence, stop, let them drive.
- Don't bad-mouth competitors; explain the structural difference calmly.
- Don't pretend to have users/revenue you don't.
- Don't get defensive when interrupted — it's the format, not hostility.

## The 60-second pre-call checklist

- Demo loaded, shareable in 5s, audio tested.
- Your single sharpest user quote memorized.
- Your "would you drop out / commitment" answer decided.
- Your one-liner so smooth you can say it half-asleep.
- A glass of water. Energy up. You built something real — act like it.
