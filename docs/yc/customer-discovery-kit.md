# SWARM — customer discovery kit

> Updated 2026-08-15.
>
> Purpose: discover the first commercial wedge from real workflows instead of forcing SWARM into wildfire, vineyards, industrial security, or another favorite vertical before evidence exists.
>
> Canonical thesis: [`../../swarm-thesis.md`](../../swarm-thesis.md).

## Core rule

Do not start by pitching SWARM.

Start by understanding where physical verification is slow, repetitive, expensive, dangerous, or poorly covered today.

The most useful opening question is:

> **What situations on your site currently require a person to physically go and check what is happening?**

The first market should emerge from repeated answers to that question.

---

## Target: 15–25 serious conversations

Aim for variety first, then depth once a pattern appears.

### Initial vertical pool

1. **Industrial sites / factories**
   - operations managers;
   - security managers;
   - maintenance managers;
   - EHS / safety roles.

2. **Logistics yards / warehouses / depots**
   - site managers;
   - fleet/yard operations;
   - security;
   - facilities.

3. **Mines / quarries**
   - site manager;
   - operations;
   - surveying / inspection;
   - safety.

4. **Energy infrastructure**
   - solar farm operators;
   - substations / generation sites;
   - O&M contractors;
   - inspection teams.

5. **Ports / large compounds**
   - operations;
   - safety;
   - security;
   - infrastructure inspection.

6. **Infrastructure inspection operators**
   - utilities;
   - rail / roads / pipelines where appropriate;
   - drone-service companies that already perform manual missions.

7. **Large private or semi-private sites**
   - campuses;
   - resorts;
   - estates;
   - agricultural operations;
   - other bounded environments.

### Expert pool

Also speak with:

- professional drone operators;
- PX4/ArduPilot practitioners;
- aviation/regulatory experts;
- robotics integrators;
- insurance/risk professionals where relevant;
- people who buy or operate drone-in-a-box systems.

These are not substitutes for buyers, but they can expose operational and regulatory failure modes early.

---

## What to learn

For every conversation, capture:

- **specific workflow**: what exactly triggers someone to go and look?
- **frequency**: times per day/week/month/year;
- **response time**: how long from alert/request to useful verification;
- **current operator**: who physically goes today?;
- **current tools**: camera, vehicle, guard, technician, handheld drone, etc.;
- **cost**: labor, interruption, callout, downtime, contractor cost;
- **cost of delay**: what gets worse while nobody has verified the event?;
- **false alarms**: how often does someone travel for nothing?;
- **coverage**: how large is the site / route / area?;
- **simultaneity**: do multiple tasks occur at once?;
- **availability constraints**: battery, people, shift coverage, weather, access;
- **sensor need**: RGB, thermal, zoom, other payload;
- **drone use today**: yes/no, manual/autonomous, vendor;
- **regulatory constraints**: what already blocks them?;
- **budget owner**: who can approve spend?;
- **existing budget line**: security, inspection, maintenance, O&M, drone services, etc.;
- **success metric**: what would make a pilot obviously useful?;
- **pilot willingness**: what conditions would have to be true?;
- **multi-agent advantage**: why would several coordinated units matter vs one manually operated drone?

---

## Interview script — buyer/operator

Keep the first 15 minutes almost entirely about their current process.

### 1. Map the site and responsibilities

> “What are you personally responsible for on this site?”

> “What parts of the site are hardest to keep visibility on?”

### 2. Find physical-check workflows

> “What situations require someone to physically go and check what is happening?”

If they give several, ask:

> “Which of those happens most often?”

> “Which one creates the most disruption or risk?”

### 3. Ask for the last real example

> “Can you walk me through the last time that happened, step by step?”

Do not accept abstractions if a concrete story is available.

### 4. Quantify frequency

> “How often does this happen?”

> “Is that predictable or random?”

### 5. Quantify time

> “From the moment you know there may be a problem, how long until someone actually sees what is happening?”

### 6. Quantify current cost

> “Who goes?”

> “How long does it take?”

> “Does it stop other work?”

> “Do you ever call an external contractor?”

### 7. Explore false alarms

> “How often does someone go out and discover there was nothing important?”

### 8. Explore delay cost

> “What happens if nobody verifies it for 10 minutes? An hour? Until the next shift?”

### 9. Existing drone usage

> “Do you use drones anywhere in this workflow today?”

If yes:

> “Who flies them?”

> “What makes the drone workflow annoying or expensive?”

> “What prevents it from being used more often?”

### 10. Multi-agent relevance

Only after understanding the workflow:

> “Do you ever need to inspect multiple areas at once, maintain coverage while another unit is busy, or choose between several available assets?”

This tests whether SWARM's coordination primitive matters or whether one manual drone is enough.

### 11. Budget

> “Which team would normally pay to solve this?”

> “Is there already a budget for inspections, security, maintenance, drone services, or callouts?”

Avoid asking “how much would you pay for SWARM?” too early.

### 12. Pilot conditions

At the end, if the problem is real:

> “If a system could reduce that verification time from [their number] to [credible target], what would you need to see before testing it on-site?”

Then:

> “Who else would have to approve a test?”

---

## Italian version — concise outreach interview

### Opening

> “Sto studiando come grandi siti gestiscono i controlli fisici quando succede qualcosa e qualcuno deve andare sul posto a verificare. Non sto cercando di venderle un drone: mi interessa capire il processo reale. Posso farle qualche domanda per 15 minuti?”

### Core question

> “Quali sono le situazioni in cui oggi qualcuno deve fisicamente andare a controllare cosa sta succedendo?”

### Concrete example

> “Mi racconta l'ultima volta che è successo, passo per passo?”

### Frequency

> “Quanto spesso succede?”

### Response time

> “Da quando ricevete il segnale a quando qualcuno vede davvero cosa sta succedendo, quanto passa?”

### Cost / people

> “Chi deve andare? Quanto tempo porta via? Blocca altre attività?”

### Existing drones

> “Usate già droni per qualche controllo o ispezione? Se sì, cosa rende il processo scomodo o costoso?”

### Pilot close

> “Se riuscissimo a ridurre molto quel tempo di verifica con un sistema autonomo e supervisionato, cosa dovrebbe dimostrare per valere un test sul vostro sito?”

---

## What NOT to ask

Avoid leading questions such as:

- “Would autonomous drones be useful?”
- “Would you buy SWARM?”
- “Would you like a drone to patrol your site?”
- “Do you think AI could improve this?”
- “Would faster response be valuable?”

Almost everyone can say yes to those without revealing a real problem.

Ask about what already happened, what they already pay for, and what they already do.

---

## Discovery log template

For each interview record:

```text
Date:
Company / site:
Role:
Vertical:
Site type / approximate scale:

Top physical-verification workflow:
Last concrete example:
Frequency:
Current response time:
People involved:
Current tools:
Current drone use:
Current cost / budget line:
Cost of delay:
False alarm frequency:
Multi-event / coverage problem:
Regulatory / safety constraint:
Budget owner:
Pilot decision-maker:
Pilot success metric:
Pilot willingness / conditions:

Exact useful quotes:

Signals FOR this wedge:
Signals AGAINST this wedge:

Follow-up:
```

---

## Wedge scorecard

After enough interviews, score each recurring workflow from 1–5.

| Dimension | What 5 means |
|---|---|
| Frequency | Happens constantly / weekly+ |
| Urgency | Delay materially matters |
| Cost | Current process is visibly expensive |
| Budget clarity | Clear buyer and existing spend |
| Drone fit | Mobile aerial verification clearly helps |
| Multi-agent fit | Coordination materially improves the workflow |
| Deployment feasibility | Bounded/supervised early deployment is credible |
| Repeatability | Same workflow exists across many sites |
| Sales cycle | Early buyer can move relatively quickly |
| Pilot willingness | Real operator will test under clear conditions |

Do not choose the winner only from the total score. A fatal regulatory, safety, procurement, or technical blocker can override an otherwise attractive score.

---

## Evidence ladder

Treat signals differently:

### Weak

- “cool idea”;
- “I can see this being useful”;
- LinkedIn interest;
- generic enthusiasm.

### Useful

- concrete repeated workflow;
- quantified frequency and response time;
- clear budget owner;
- existing spend on the workaround.

### Strong

- buyer shares internal process/data;
- buyer introduces the decision-maker;
- buyer offers site access;
- buyer defines success criteria;
- buyer says they would test if those criteria are met.

### Very strong

- written pilot commitment;
- paid pilot;
- recurring contract.

Never upgrade one category into another when describing traction.

---

## What success looks like

Customer discovery is successful when SWARM can replace:

> “We think [vertical] needs this.”

with:

> “Across [N] interviews, [specific role] repeatedly described [specific workflow]. It happens [frequency], takes [current response time/cost], and [buyer] already pays through [budget line]. [N] operators said they would evaluate a pilot if we hit [metric].”

Only then should that workflow become the canonical first wedge.
