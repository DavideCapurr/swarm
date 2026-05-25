# Phase 7.E — `make demo-*` per i tre scenari MVP

> Branch: `claude/loving-feynman-yxQqU`. Phase 7.A → 7.D mergeati (PR #55,
> #56, #57, #59, #60). Roadmap reference:
> [`docs/plan/swarmos-roadmap.md`](swarmos-roadmap.md) §Phase 7,
> linee 877-882.

## Context

Phase 7 ("Software MVP base in simulazione") porta lo stack a essere
**girabile end-to-end in sim sui tre scenari MVP**. 7.A-7.D hanno
shippato il materiale strutturale:

- `sim/scenarios/{wildfire,intrusion,search}_owner_land.yaml` — tre
  scenari replicabili sul terreno del founder (Phase 19).
- `swarm_os/autonomy.py` — kernel deterministico R1/R2/R3 (Phase 7.B).
  Ogni decisione autonoma passa dal command bus, finisce nella audit-log
  con `source="autonomy"` + `rule=…` (Phase 7.C / Phase 4).
- Console con eyebrow `AUTO · {rule}` su HeadBar, CommandTimeline,
  EventFeed, AnomalySummary, MobileAnomalyScreen (Phase 7.C).
- `sim/swarm_sim/cv/` — YOLOv8 pretrained opt-in per scenario, manifest
  HTTPS+sha256, fixture CC0, integrity gate (Phase 7.D).

Quello che manca per **chiudere Phase 7** è citato esattamente nel piano
(riga 877):

> **7.E** "Make demo" target: `make demo-wildfire-sim`,
> `make demo-intrusion-sim`, `make demo-search-sim`. Replicabili in
> 1 comando.

E il gate alla riga 881:

> i 3 scenari girano end-to-end in sim, ogni decisione autonoma è
> loggata, metriche baseline raccolte.

PR #62 (`codex/yc-bief-roadmap`, draft) richiama esplicitamente che
7.E è la prossima cosa da chiudere prima di Phase 8.

## Decisioni chiave

1. **Un unico script parametrico**, non tre copie. `scripts/demo_scenario.sh`
   prende il path della YAML + flag opzionali e delega tutto il boot
   (infra, sim, backend, frontend) a `scripts/dev_up.sh` che già
   esisteva. `scripts/demo_wildfire.sh` resta come thin wrapper di
   back-compat per `make demo` e per la riga del README §Quickstart
   "Run the wildfire scenario manually".
2. **Tre target Make** (`demo-wildfire-sim`, `demo-intrusion-sim`,
   `demo-search-sim`) che chiamano lo script con la YAML corretta e
   `--metrics`. Nessuna logica nel Makefile oltre al dispatch.
3. **Decisioni autonome loggate**: nessun codice nuovo. Phase 7.B + 7.C
   già scrivono `OperatorCommand{source="autonomy", rule="R1"|"R2"|"R3"}`
   e `Event{source="autonomy"}` nell'audit log (Alembic 0003 + 0004).
   Il gate è soddisfatto dal lavoro precedente.
4. **Metriche baseline raccolte**: `scripts/scenario_metrics.py`, opt-in
   via flag `--metrics`. Si autentica come **viewer** (read-only) — usa
   gli account che `make bootstrap-auth-dev` provisiona di default
   (`op-viewer01` / `swarm-dev`) — poi attende `--duration` secondi
   (default 60), interroga `/commands` + `/events`, e scrive un JSON in
   `docs/bench/artifacts/phase-7e-<scenario>-<utcts>.json` con:
   - conteggio decisioni autonome per regola (R1/R2/R3),
   - conteggio decisioni autonome per stato (completed / rejected /
     timed_out),
   - conteggio eventi per kind + sotto-conteggio degli eventi con
     `source="autonomy"`,
   - **latencies_ms** (richiesta YC playbook §12.2):
     `anomaly_to_autonomy_decision` (p50/p95/n) calcolata correlando
     `Event{kind=anomaly, anomaly_id=X, ts}` col primo
     `OperatorCommand{source=autonomy, target="anomaly:X", submitted_at}`;
     `autonomy_decision_to_mission_dispatch` (p50/p95/n) calcolata da
     `in_flight_at - submitted_at` sulle decisioni che hanno spawned
     una missione (DISMISS R3 lascia `in_flight_at=null` → escluso),
   - finestra di osservazione.
   Niente `/metrics` Prometheus: è commander+MFA gated (Phase 6.D) — il
   collector resta in scope viewer. La audit-log è la source-of-truth
   richiesta dal gate.
5. **Niente nuove dipendenze**. `httpx` è già core dep. `yaml` per i
   test è già dev dep (lo usano i test Phase 6.E e 7.D). Nessun nuovo
   endpoint backend.

## File creati / modificati

### Nuovi

- `scripts/demo_scenario.sh` — script parametrico
  `./scripts/demo_scenario.sh <yaml> [--metrics] [--duration SECONDS]`.
  `set -euo pipefail`, no `|| true` (CLAUDE.md §readiness check #3).
  Esporta `SIM_SCENARIO` poi `exec ./scripts/dev_up.sh`. Quando
  `--metrics` è passato, lancia il collector in background prima del
  boot.
- `scripts/scenario_metrics.py` — collector read-only.
  Usa `httpx`, autentica via `/auth/login`, dorme `--duration` secondi,
  snapshot di `/commands` + `/events`, dump JSON. Idempotente per
  timestamp, mai sovrascrive un artifact esistente.
- `tests/test_phase7e_demo.py` — 18 test (pattern di
  `tests/test_phase6e_deploy.py`): Makefile, executable bit, fail-fast
  shell, YAML opt-in autonomy, `--help` smoke del collector,
  artifact-path isolation.
- `docs/plan/phase-7e.md` — questo file.

### Modificati

- `scripts/demo_wildfire.sh` — ridotto a thin wrapper su
  `demo_scenario.sh sim/scenarios/wildfire_owner_land.yaml "$@"`.
- `Makefile` — tre target nuovi + `.PHONY` aggiornato.
- `docs/STATUS.md` — flip riga 18 a `done` + sezione completed-checklist.
- `README.md` — un bullet nei Quickstart sui tre `make demo-*`.

### Non modificati (volutamente)

- `swarm_os/autonomy.py`, `swarm_os/command_bus.py`,
  `sim/swarm_sim/runner.py`, `backend/app/*` — il gate logging è già
  soddisfatto.
- Le tre YAML degli scenari — già con `autonomy_baseline: true` e
  `perception.cv_enabled: true`.
- `scripts/dev_up.sh` — riusato così com'è.

## Verifica end-to-end

Prima di marcare 7.E `done` in STATUS.md.

### Gate automatici

1. `make lint` verde (ruff + mypy + tsc).
2. `make test` verde, incluso `tests/test_phase7e_demo.py` (18 nuovi).
3. `make audit` verde (pip-audit, pnpm audit, Bandit, pymavlink
   integrity, cv integrity).

### Hands-on gate (citare l'evidenza nel completed-checklist di STATUS.md)

Per ciascuno dei tre scenari:

1. `make bootstrap-auth-dev` (se mai eseguito).
2. `make demo-<scenario>-sim` — un solo comando.
3. Aprire http://localhost:3000 dopo 5-10 s, login `op-viewer01` /
   `swarm-dev`.
4. Osservare nell'EventFeed almeno una riga `auto` (Orbital Blue) e nel
   CommandTimeline almeno un chip `AUTO · R1`.
5. Dopo `--duration` secondi (default 60), il collector scrive
   `docs/bench/artifacts/phase-7e-<scenario>-<utcts>.json` con
   `auto_decisions.by_rule.R1 >= 1`.

Atteso per ogni scenario:

| Scenario  | Anomalia                          | Regole attese          |
|-----------|-----------------------------------|------------------------|
| wildfire  | SMOKE 0.62 @ t=10s; FIRE 0.88 @ t=25s | R1 VERIFY, poi R2 ESCALATE |
| intrusion | INTRUSION 0.71 @ t=15s            | R1 VERIFY              |
| search    | HEAT_SPOT 0.55 @ t=20s            | R1 VERIFY              |

(R2 ESCALATE è gated a conf ≥ 0.80: solo il follow-up FIRE wildfire la
trigghera. Intrusion + search stanno deliberatamente sotto la soglia R2
per lasciare l'escalation all'operatore — vedi commenti nelle YAML.)

### Anti-overreach (CLAUDE.md §10)

- No nuove dipendenze Python o JS.
- No nuovi endpoint backend o rotte Console.
- No modifiche all'autonomy kernel, agli scenari YAML, al CV runtime.
- No metriche Prometheus nuove (uso `/commands` + `/events` esistenti).
- No PDF, no chart libs, no nuovi componenti UI, no feature flag.
- Scope = tre target Make + uno script parametrico + un collector
  read-only + test + docs. Stop.
