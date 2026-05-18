# SwarmOS — Piano completo Phase 0 → Phase 26

Phase 0–6 = PDF roadmap originale (fondazione tecnica, in larga parte
fatta).
Phase 7–10 = **pre-seed sprint** (founder solo + Claude Code + Codex
fino a primo capitale).
Phase 11–26 = **post-seed execution** (visione finale dopo team +
capitale + giurisdizione target attiva).

Giurisdizioni target iniziali (decisione utente 2026-05-18):
**Rwanda + Dubai (UAE)**, non UE. Casi MVP: incendio + protezione case
+ bene pubblico (defibrillatore, ricerca dispersi, supporto Protezione
Civile).

## Context

L'utente ha consegnato un PDF (`06b2766e-SWARMOS_piano_sviluppo_e_prompt_code_AGGIORNATO.pdf`,
estratto a `/tmp/swarm_plan.txt`) che descrive il piano completo di sviluppo
di **SwarmOS**, l'operating layer autonomo, e della **Console** (la
superficie operativa per gli operator). Il principio cardine del prodotto:
**SwarmOS decides. Console supervises.** Nessuna UI inventa verità
operativa. Ogni numero arriva da SwarmOS o dal simulator onesto. Ogni campo
temporaneamente derivato dal client deve essere marcato `DERIVED`.

Vincolo trasversale aggiunto dall'utente: SwarmOS e il repo SWARM devono
essere **safe il più possibile sul piano cybersecurity**, con attenzione
esplicita al pattern di attacco descritto nella risposta di OpenAI
all'attacco supply-chain TanStack nel frontend JavaScript. Per questo lo Phase 0 include una
*security baseline* obbligatoria, e ogni fase successiva ha una sezione
"Security additions" che chiude i gap nuovi che essa stessa apre.

Il PDF organizza il prodotto in 7 fasi (0-6). La richiesta dell'utente:
**il piano copra tutte le fasi fino a Phase 6, poi le implementiamo una
alla volta** (questa sessione = Phase 0, le successive in sessioni
dedicate). Quanto segue è la mappa completa per Phase 0 → Phase 6,
ancorata allo stato attuale del repo come trovato dall'esplorazione.

### Terminologia (PDF §0 + uso corrente nel repo)

- **SWARM** — brand/progetto. In maiuscolo per il wordmark e nei testi UI
  ("SWARM / control / session 014"). Riferimento al repo: `swarm/`.
- **SwarmOS** — il prodotto: l'operating layer autonomo che decide,
  pianifica, coordina la flotta. Sorgente di verità.
  **Ambito SwarmOS = TUTTO il backend del repo**, ovvero le cartelle
  `core/`, `swarm_os/`, `orchestrator/`, `adapters/`, `sim/`, `backend/`,
  `infra/`, `scripts/`. Il package `swarm_os/` (kernel decisionale) è
  *parte* di SwarmOS, non l'intero SwarmOS — è il cervello che coordina
  gli altri pezzi.
- **Console** — la **sola** superficie operatore: tutto e solo ciò che
  vive in `frontend/`. Renders state, sends intent. Non decide.
  Quando dici "Console" ti riferisci esclusivamente al codice React/
  Next.js dentro `frontend/`.
- **operator** — la persona che usa la Console. Manda intent
  (`/actions/verify`, `/actions/hold-patrol`), non comandi manuali al drone.
- **adapter** — modulo che traduce un vendor reale (DJI, MAVLink, Skydio,
  Parrot, Autel) o il simulator in contratti SwarmOS.
- **fleet** — l'insieme delle unit (droni) sotto un dock. **unit** è
  l'entità singola (agent_id). Il PDF usa "Unit 003", "003 / 004 online".
- **sector** — un poligono del territorio sotto awareness. La Console rende
  una grid di sector centrata su VINEYARD_CENTER nel demo Langhe.
- **mission** — un task atomico (patrol, verify, return, etc.).
- **anomaly** — un evento candidato. Ha stato `pending → verifying →
  verified/dismissed → escalated/marked_known`.
- **event** — entry della timeline operativa che la Console mostra in
  EventFeed (typed `kind`: patrol, anomaly, verify, operator, dock, link,
  sector, mission).
- **awareness** — il punteggio aggregato che dice "quanto SwarmOS si fida
  della sua mappa del territorio in questo istante". Vive server-side
  (Phase 3); fino ad allora i client ne possono derivare una versione
  marcata DERIVED.
- **OperatorCommand** — l'oggetto che incapsula l'intent dell'operator dopo
  la validazione policy (battery/link/geofence/weather/priority).

### Stato attuale del repo (post-Phase 0, verificato 2026-05-15)

Backend (Python, FastAPI):
- `core/swarm_core/messages.py` ha già `Telemetry`, `FleetState`, `Anomaly`,
  `MissionTask`, `MissionProgress`, `Bid`, `Award`, `CaptureResult` +
  primitives (`Geo`, `Waypoint`, `Attitude`) ed enum (`AgentState`,
  `AnomalyKind`, `SensorKind`) + i contratti Console (`UnitState`,
  `DockState`, `Sector`, `AwarenessBreakdown`, `MissionView`,
  `AnomalyView`, `Event`, `OperatorCommand`, `Session`).
- `core/swarm_core/geometry.py` (`haversine_m`, `point_in_polygon`,
  `tile_polygon`, `bbox`, `midpoint`, `sector_grid`, `closest_sector`) —
  base solida per `sectors`.
- `core/swarm_core/missions.py` con `MissionKind` enum e DSL
  `PATROL()/VERIFY()/COVER()/RELAY()/RTL_DOCK()`.
- `core/swarm_core/allocator.py` + `fsm.py` (drone-level FSM) +
  `core/swarm_core/tests/`.
- `adapters/` con `base.py` (AdapterRegistry) e stub per `simulated`,
  `dji_cloud`, `dji_psdk`, `mavlink`, `parrot`, `skydio`, `autel`.
- `orchestrator/swarm_orchestrator/` con `bus.py` (InMemoryBus +
  RedisBus), `service.py` (anomaly loop + 500 ms auction + dispatch).
- `sim/swarm_sim/` con `world.py` (Vineyard world, drones, perception),
  `runner.py` che boota world + adapter + orchestrator + bus.
- `backend/app/main.py` (FastAPI + WS hub + bus_consumer);
  `backend/app/api/routes.py` con `/health`, `/fleet`, `/anomalies`,
  `/telemetry/latest`, `/events`; `backend/app/ws/telemetry.py`.

Frontend (Next.js 16, React 19, MapLibre):
- Single page `app/page.tsx` (`ControlSurface`, 314 righe) già
  design-compliant: HEAD BAR + viewport + EventFeed + canon footer +
  awareness/anomaly/dock cards. NO route group.
- `lib/api.ts`, `lib/ws.ts`, `lib/tokens.ts`. URL derivation LAN-aware già
  presente.
- Componenti: `Map.tsx` (MapLibre Langhe basemap), `FleetGrid`,
  `UnitDetail`, `EventFeed`, `AnomalyCard`, `AwarenessScore`, `DockCard`,
  `StatusPill`, `Eyebrow`.

Infra / supply chain:
- `docker-compose.yml`: Timescale + Redis digest-pinned con hardening
  container e resource limits.
- `.github/workflows/{lint,test}.yml`: GitHub Actions SHA-pinned, Python
  install via `uv sync --frozen`, frontend via Corepack + pnpm.
- `pnpm-lock.yaml` e `uv.lock` committati; `frontend/.pnpmrc` disabilita
  lifecycle scripts e forza peer strict.
- `SECURITY.md`, threat model, incident response, Dependabot, dependency
  review, CodeQL, Bandit, Semgrep, Trivy, gitleaks presenti.
- CORS allowlist env-driven; WS evil Origin rifiutato pre-accept HTTP 403
  o close 1008.

## Strategia generale

**Principio additivo, non distruttivo.** Il codice esistente (simulator,
adapter, orchestrator, bus, FastAPI corrente, componenti frontend) è già
fonte di verità operativa funzionante. Il piano lo **proietta** in nuovi
contratti view-oriented per la Console, senza riscriverlo.

**Reconciliazione dei due modelli dati**: additivo.
- `FleetState`/`Telemetry`/`Anomaly` restano i contratti adapter→bus (alta
  frequenza, raw vendor).
- `UnitState`/`AnomalyView`/`MissionView`/etc. sono *view aggregates*
  prodotti da `swarm_os/state.py` partendo dai messaggi del bus.
- Questo permette di non rompere simulator/adapter/orchestrator. Il piano
  della Phase 5 (Real Adapter) richiede esattamente questa stabilità.

**Frontend "copy-then-redirect"**. L'attuale `ControlSurface` viene liftato
in `frontend/components/TerritoryControl.tsx`, montato sia in `/` che in
`/(console)/` come stesso componente. Solo dopo la verifica di parità il
file `app/page.tsx` flippa a `redirect("/(console)")`. Demo mai down.

**Security in ogni fase**, con un payload massimo concentrato in Phase 0.
Phase 4 (Persistence) e Phase 6 (Production OS) hanno security additions
ulteriori (mTLS bus, secrets-scanning, SBOM, JWT/OIDC, sigstore
provenance, geofence enforcement). Riferimento concettuale: attacco
TanStack (lifecycle scripts + tag floating + token con scope ampio) — il
piano chiude queste classi di rischio nella supply chain.

## Architettura finale (post Phase 6)

```
swarm/
  core/swarm_core/
    messages.py          # contratti condivisi (raw + view)
    geometry.py          # WGS84, grid, point-in-polygon, closest sector
    voice.py             # confidence-bound copy + FORBIDDEN_WORDS
    awareness.py         # score factors, risk state, sector confidence
    safety.py            # thresholds, geofence, weather lock rules

  swarm_os/
    state.py             # SwarmState live store (units, docks, sectors, …)
    fsm.py               # operating mode FSM (rest/patrol/verification/escalation/maintenance)
    sectors.py           # grid generation + scoring
    scheduler.py         # patrol cadence, coverage targets
    event_detector.py    # state transitions → typed Event
    command_bus.py       # OperatorCommand validate→apply→audit
    coordinator.py       # wrap orchestrator/swarm_orchestrator/, no replace
    policy.py            # safety policy engine (Phase 6)

  orchestrator/swarm_orchestrator/   # resta com'è: dispatcher + auction
  adapters/
    base.py
    simulator/           # adapter Phase 1 (truth source per v0)
    mavlink/             # Phase 5 (PX4/ArduPilot)
    dji/, dji_cloud/, dji_psdk/  # Phase 5 (alternativa)
    skydio/, parrot/, autel/     # Phase 5+
  sim/swarm_sim/         # world/perception, alimenta SimulatedAdapter

  backend/app/
    main.py              # FastAPI + lifespan + middleware sicurezza
    security.py          # origin allowlist, regex, rate-limit, headers
    api/routes.py        # GET endpoints
    api/actions.py       # POST endpoints (operator intent)
    ws/telemetry.py      # WS typed payloads per kind
    db/                  # Timescale (Phase 4)
    auth/                # JWT/OIDC (Phase 6)

  frontend/
    app/
      page.tsx           # → redirect /(console)
      (console)/         # Territory Control + Verification + System State
      m/                 # Mobile Alert
    lib/
      state.tsx          # SwarmStateProvider + useSwarm()
      derive.ts          # derived flags
      api.ts, ws.ts      # typed clients
      actions.ts         # dispatch()
    components/          # 17 component cards
    icons/               # named SVG 24px stroke 1.5 round

  infra/
    postgres/, redis/    # docker-compose
    timescale/           # Phase 4 schemas + migrations

  .github/
    workflows/           # lint/test/dependency-review (SHA-pinned)
    dependabot.yml
  SECURITY.md
  uv.lock                # Python lockfile
  frontend/.pnpmrc       # ignore-scripts=true, audit-level=high
```

## Phase 0 — Repo discipline + security baseline

**Obiettivo** (PDF §2): mettere ordine prima di costruire. Cartelle, make
commands, lint/test baseline, shared types. **Nessuna feature nuova**.
**Espansione per cybersecurity**: l'utente ha chiesto safety
infrastrutturale, quindi Phase 0 estende §2 con tutti i guard-rail della
supply chain.

### Cosa fa
1. **Security baseline** (S1-S14, lista nella sezione successiva).
2. **Shared types Console** (`UnitState`, `DockState`, `Sector`,
   `AwarenessBreakdown`, `MissionView`, `AnomalyView`, `Event`,
   `OperatorCommand`, `Session` in `core/swarm_core/messages.py`) — solo i
   modelli Pydantic, ancora non instanziati.
3. **voice.py** server-side con `band(confidence)`, `describe_anomaly()`,
   `describe_sector()`, `describe_mode()`, lista `FORBIDDEN_WORDS`.
4. **geometry.py extensions**: `sector_grid(center, half_extent_m, n)`,
   `closest_sector(p, sectors)`.
5. **Makefile**: target `make audit` (= `pip-audit` + `pnpm audit
   --audit-level=high`). Target `make demo` resta intatto.
6. **README**: sezione Security che linka `SECURITY.md` e descrive
   lockfile + `make audit`.

### File toccati in Phase 0
- `frontend/.pnpmrc` (NEW) — S1: `ignore-scripts=true`,
  `engine-strict=true`, `audit-level=high`, `fund=false`,
  `strict-peer-dependencies=true`
- `.nvmrc`, `frontend/.nvmrc` (NEW) — S2: Node 24 LTS line
- `frontend/package.json` (EDIT) — `"packageManager": "pnpm@11.1.2"` and
  `"engines": {"node": ">=24 <25"}`
- `.github/workflows/lint.yml` + `test.yml` (EDIT) — S3 drop `--no-audit`,
  S4 SHA-pin (full 40-char) di `actions/checkout`, `actions/setup-python`,
  `actions/setup-node`, S5 `permissions: contents: read`
- `.github/dependabot.yml` (NEW) — S6: weekly per frontend JavaScript,
  `pip`, `docker`, `github-actions`, raggruppato minor+patch
- `.github/workflows/dependency-review.yml` (NEW) — S12: blocca PR con
  CVE high
- `docker-compose.yml` (EDIT) — S7: digest-pin via `@sha256:…` (l'utente
  ha autorizzato `docker pull` per estrarli)
- `SECURITY.md` (NEW) — S11: disclosure policy + scope + contatto +
  Private Vulnerability Reporting GitHub
- `uv.lock` (NEW da `uv lock`) + workflow `uv sync --frozen` — S10
- `pyproject.toml` (EDIT) — pin minimi più stringenti (no rimozioni)
- `Makefile` (EDIT) — target `audit`
- `README.md` (EDIT) — sezione Security + link a `CLAUDE.md` e
  `docs/plan/swarmos-roadmap.md`
- `CLAUDE.md` (NEW, root del repo) — quick context loader per ogni
  nuova sessione: terminologia, regole hard, stato corrente, link al
  piano
- `docs/plan/swarmos-roadmap.md` (NEW) — copia versionata di questo
  piano (single source of truth)
- `docs/STATUS.md` (NEW) — file vivo: fase corrente, prossima fase,
  decisioni aperte. Aggiornato a fine di ogni fase
- `docs/CONVENTIONS.md` (NEW) — convenzioni codice/commit/branch
- `backend/app/security.py` (NEW) — utility scaffold: origin allowlist
  reader, header constants, regex `^op-[a-z0-9]{4,32}$`, token-bucket
  rate-limiter 30 req/min/IP (non ancora wired sulle action perché non
  esistono in Phase 0)
- `backend/app/main.py` (EDIT) — CORS env-driven allowlist
  (`SWARM_ALLOWED_ORIGINS`, default `http://localhost:3000`),
  `allow_methods=["GET","POST","OPTIONS"]`, `allow_credentials=False`;
  security headers middleware (CSP minimale, X-Content-Type-Options,
  X-Frame-Options DENY, Referrer-Policy, Permissions-Policy); WS origin
  check con close 1008
- `frontend/next.config.mjs` (EDIT) — `headers()` con CSP / nosniff /
  Referrer-Policy / Permissions-Policy
- `core/swarm_core/messages.py` (EDIT) — sezione "Console-facing
  aggregates" con i 9 nuovi modelli (campi come PDF §6)
- `core/swarm_core/geometry.py` (EDIT) — `sector_grid` + `closest_sector`
- `core/swarm_core/voice.py` (NEW)
- `core/swarm_core/tests/test_messages_v1.py` (NEW), `test_voice.py` (NEW),
  `test_geometry_sectors.py` (NEW)

### Anti-overreach Phase 0
- Non scrivere logica di `swarm_os/` ancora.
- Non modificare `app/page.tsx`.
- Non toccare adapter reali.
- Non aggiungere JWT/auth.
- Non aggiungere Timescale.

### Verifica Phase 0
- `make demo` boota identico (sim + backend + frontend).
- `make lint`, `make test`, `make audit` verdi.
- `curl -H "Origin: https://evil.example" -I http://localhost:8765/health`
  → nessun `Access-Control-Allow-Origin: https://evil`.
- `websocat -H "Origin: https://evil.example" ws://localhost:8765/ws/telemetry`
  → rifiuto pre-accept HTTP 403 oppure chiusura 1008.
- `curl -I http://localhost:8765/health` mostra Content-Security-Policy,
  X-Content-Type-Options, Referrer-Policy.
- `grep -E "@sha256:" docker-compose.yml` ritorna due match.
- `grep -E 'uses: actions/.+@[0-9a-f]{40}' .github/workflows/*.yml` per
  ogni action.
- `test -f frontend/.pnpmrc && grep ignore-scripts frontend/.pnpmrc`.

## Phase 1 — SwarmOS Sim Kernel

**Obiettivo** (PDF §2/§3/§7): creare il cervello simulato. SwarmOS deve
*sapere* lo stato della flotta, del territorio, decidere il mode operativo,
gestire missioni/anomalie, pubblicare eventi.

### Cosa fa
1. Nuovo package `swarm_os/`:
   - `state.py`: `SwarmState` con dict `units`, `docks`, `sectors`,
     `missions`, `anomalies`, `tracks`, deque `events`, awareness, mode,
     verifier_id, session; asyncio.Lock per mutazioni.
   - `fsm.py`: `compute_mode(state)` puro: la regola del piano
     (attention→maintenance, verified→escalation, pending→verification,
     airborne→patrol, else rest).
   - `sectors.py`: generazione grid + scoring per `Sector.confidence` e
     `last_visited_at` (decadimento lineare).
   - `awareness.py`: `AwarenessBreakdown` calculator (score + factors +
     blind_spot_sectors + stale_sectors + risk_state).
   - `scheduler.py`: `next_patrol_at` per dock, `tick(state, now)`.
   - `event_detector.py`: bus topics → `Event(kind=...)`, idempotente.
   - `command_bus.py`: `submit(OperatorCommand)`, valida target,
     applica state mutation, appende Event, ritorna 202.
   - `coordinator.py`: il coordinator che fa girare projection
     (FleetState+Telemetry → UnitState), scheduler.tick,
     fsm.compute_mode, awareness re-compute ~2 Hz, push WS frames via
     `WSHub`. **Delega l'esecuzione** all'esistente
     `orchestrator/swarm_orchestrator/`.
2. `adapters/simulator/runner.py` (NEW): adapter integration che si
   abbona ai topic `swarm:*` esistenti e alimenta `SwarmState`. Emette
   anomaly trigger programmato, route waypoints, verifier assignment
   (logica già implementata client-side, ora server-side).
3. REST endpoints (estendere `backend/app/api/routes.py`):
   - `GET /session` — info Session
   - `GET /awareness` — `AwarenessBreakdown` corrente
   - `GET /docks` — list `DockState`
   - `GET /sectors` — list `Sector`
   - `GET /units` — list `UnitState`
   - `GET /missions` — list `MissionView`
   - `GET /anomalies` — list `AnomalyView`
   - `GET /events?limit=&kind=&sector=&agent=` — filtered events
   - Le endpoint vecchie (`/fleet`, `/anomalies` raw, `/telemetry/latest`)
     **restano** durante Phase 1-2.
4. WS dual-emit (`backend/app/ws/telemetry.py`): continua a emettere i
   payload attuali `fleet|anomaly|telemetry|progress` e aggiunge i nuovi
   `unit|dock|sector|awareness|mission|anomaly_view|event|operator`. La
   transizione completa avviene in Phase 2.
5. Action endpoints (`backend/app/api/actions.py` NEW):
   - `POST /actions/verify`, `/hold-patrol`, `/dismiss`, `/return`
   - Header `X-Operator-Id` obbligatorio (regex Phase 0)
   - `target` validato contro `SwarmState`
   - `rejected_reason` solo da enum chiuso (no echo input)
   - Rate-limit 30 req/min/IP (middleware Phase 0 wired qui)
   - Ritorna 202 `{command_id, status}`

### Anti-overreach Phase 1
- Niente Timescale: tutto in memoria.
- Niente auth (X-Operator-Id non è JWT, è solo handle validato).
- Niente video reale.
- Niente adapter reali.
- Niente weather/NOTAM esterni.

### Verifica Phase 1
- `curl localhost:8765/session` → snapshot sim.
- `curl localhost:8765/awareness` → breakdown con factors valorizzati.
- `curl localhost:8765/units` → 3 UnitState.
- `curl localhost:8765/sectors` → grid generata.
- WS streama sia il payload vecchio che nuovo (verificabile con `wscat`).
- `curl -X POST -H "X-Operator-Id: op-davide" -H "content-type:
  application/json" -d '{"target":"sector:north-a"}'
  localhost:8765/actions/verify` → 202.
- 31a chiamata di fila → 429.
- `make test` verde, copertura swarm_os/ ≥ 70%.

## Phase 2 — Console Operating Shell

**Obiettivo** (PDF §5): rendere visibile SwarmOS via Console. Territory
Control + Verification + System State + Mobile Alert + ActionRail +
SectorLayer + RouteLayer. Design system vincolante (PDF §5.2).

### Cosa fa
1. **Lift**: `ControlSurface` (314 righe di `app/page.tsx`) → nuovo
   componente `frontend/components/TerritoryControl.tsx`. Stesso
   comportamento, solo file diverso.
2. **State provider**: `frontend/lib/state.tsx` con
   `SwarmStateProvider` + `useSwarm()`. Riusa `SwarmSocket` esteso con
   i nuovi `kind`. Espone `fleet`, `units`, `dock`, `sectors`,
   `missions`, `anomalies`, `events`, `awareness`, `mode`, `verifier`,
   `link`, `clock`, `dispatch`, `derived`.
3. **derive.ts**: helper temporanei marcati `derived: true` per i
   campi non ancora prodotti server-side.
4. **api.ts/ws.ts**: union typed payloads `WSMessage = { kind:
   "unit"|"dock"|"sector"|... ; data: ... }`. URL derivation LAN-aware
   preservata.
5. **Routing**:
   - `frontend/app/(console)/layout.tsx` — monta `<SwarmStateProvider>`
     + `<HeadBar/>` + `<Footer/>`.
   - `frontend/app/(console)/page.tsx` — renderizza
     `<TerritoryControl/>` (lifted).
   - `verify/page.tsx`, `verify/[id]/page.tsx`, `system/page.tsx`,
     `m/layout.tsx`, `m/page.tsx`, `m/[anomaly]/page.tsx` (stub honest
     da `useSwarm()`).
   - **Solo dopo verifica parità** `/` e `/(console)/`:
     `frontend/app/page.tsx` flippa a `redirect("/(console)")`.
6. **17 nuovi componenti** (PDF §5.10):
   - Layout: `HeadBar.tsx`, `Footer.tsx`, `RightRail.tsx`,
     `ActionRail.tsx`.
   - Rail cards: `RiskState`, `NextPatrol`, `WeatherLock`,
     `LinkHealth`, `AnomalySummary`.
   - Map overlays: `SectorLayer`, `RouteLayer`.
   - Verification: `LiveFeedFrame` (placeholder onesto, **mai video
     stock**).
   - System: `DockDetail`, `UnitReadiness`.
   - Mobile: `MobileAlertScreen`, `MobileAnomalyScreen`.
   - Icons: `frontend/icons/index.tsx` — named SVG 24px stroke 1.5
     round caps.
7. **WS cleanup**: rimuovere il dual-emit Phase 1 dei payload vecchi una
   volta che la Console legge solo i nuovi.
8. **Voice + Brand audit pass** (PDF §9):
   ```
   grep -rE "Intruder|Manual|fly drone|alarm|red[- ]?(alert|state)" \
     frontend/components frontend/app  # zero match
   grep -rE "box-shadow|drop-shadow|backdrop-blur|linear-gradient" \
     frontend/components frontend/styles  # zero fuori allowlist
   ```

### Anti-overreach Phase 2
- Niente librerie chart/modal/toast/snackbar.
- Niente icon kit esterno (Lucide solo fallback).
- Niente video stock.
- Niente rosso. Mai.
- Niente glassmorphism / linear-gradient / backdrop-blur fuori
  allowlist esplicita.

### Verifica Phase 2 (Definition of Done Step 1 §8)
- `make demo` boota tutto.
- `/` redirige a `/(console)/`; `/(console)/verify`,
  `/(console)/system`, `/m`, `/m/<anomaly>` renderizzano.
- Mappa mostra `SectorLayer` + `RouteLayer` + anomaly ring.
- RightRail cambia ordine in base a mode.
- `verify/[id]` mostra LiveFeedFrame placeholder "UNIT 003 VIEWPORT
  PENDING".
- ActionRail wire `verify/hold/dismiss/return` → 202 dal backend;
  azioni future mostrano advisory copy.
- `/m` no horizontal overflow a 360×640; awareness identica a desktop.
- Voice + Brand audit grep tutti zero.
- `make lint`, `make test`, `make audit` verdi.

## Phase 3 — Truth Layer

**Obiettivo** (PDF §2): togliere derive dal client. Awareness server-side
(già in Phase 1), event detector completo, mission scheduler, command
lifecycle full.

### Cosa fa
1. **Eliminare DERIVED flags**: tutti i campi che il client deriva
   (operating mode, verifier, awareness, link aggregate) devono arrivare
   già calcolati da SwarmOS. `derive.ts` può sopravvivere solo per UI
   helpers (es. formatting), non per fonti di verità.
2. **Event detector completo**: tutte le state transitions producono
   `Event` tipizzati. Coverage minima: patrol_started, patrol_completed,
   sector_visited, anomaly_detected, anomaly_verifying,
   anomaly_verified, anomaly_dismissed, anomaly_escalated,
   operator_command_submitted, operator_command_completed,
   operator_command_rejected, dock_weather_lock, link_degraded,
   unit_battery_low, mission_failed.
3. **Mission scheduler**: patrol cadence per sector con coverage targets
   (`Sector.last_visited_at` decay → automatic re-patrol mission
   creation). Niente missioni manuali.
4. **Command lifecycle full**: `OperatorCommand.status` progresso reale
   `submitted → accepted → in_flight → completed | rejected | timed_out`.
   La Console mostra lo stato di ogni comando con timeline.
5. **Sector confidence**: scoring server-side, non più client.

### File principali
- `swarm_os/awareness.py` esteso
- `swarm_os/event_detector.py` esteso
- `swarm_os/scheduler.py` esteso
- `swarm_os/command_bus.py` esteso con state machine OperatorCommand
- `frontend/lib/derive.ts` ridotto a UI formatting helpers
- `frontend/components/TerritoryControl.tsx` semplificato (legge da
  `useSwarm()` senza derive)

### Anti-overreach Phase 3
- Niente integrazioni esterne (weather/NOTAM resta Phase 6).
- Niente persistence (resta Phase 4).

### Verifica Phase 3
- Test che dimostra: con backend acceso e simulator running, ogni
  campo della Console arriva da SwarmOS (assert via WS inspection).
- Nessun "DERIVED" eyebrow visibile nella Console.

## Phase 4 — Persistence

**Obiettivo** (PDF §2/§4): rendere storico e auditabile.

### Cosa fa
1. **Schema Timescale**:
   - `events` (hypertable per `ts`)
   - `telemetry` (hypertable, retention 7-30 giorni)
   - `missions` (relazionale)
   - `anomalies` (relazionale)
   - `operator_commands` (audit log, retention permanente)
   - `sector_visits` (per coverage history)
   - `sessions` (sessione operativa)
2. **Alembic migrations** in `backend/app/db/migrations/`.
3. **SQLAlchemy Async** per scrivere/leggere; il `BusConsumer` persiste
   ogni evento appena lo proietta in `SwarmState`.
4. **API estese**: `/events?from=&to=&kind=&sector=` storica;
   `/missions/<id>/history`; `/operator-commands?operator_id=`.
5. **Auditing**: ogni `OperatorCommand` registra `operator_id`,
   `submitted_at`, `accepted_at`, `completed_at`, `outcome`,
   `rejected_reason` (enum chiuso).

### Security additions Phase 4
- DB credentials da env, non in `docker-compose.yml`.
- Connection encryption (`sslmode=require` quando non in dev).
- Backup encryption se aggiungiamo Postgres backup target.
- `secrets-scanning` workflow (`.github/workflows/secret-scanning.yml`)
  per intercettare token nel repo.

### Anti-overreach Phase 4
- Niente analytics avanzate (dashboards/grafici complessi resta out).
- Niente data export PDF/CSV ancora.

### Verifica Phase 4
- `make demo` con `POSTGRES_*` env riempito boota e persiste.
- Riavvio backend → la Console mostra eventi dallo storico.
- Query `select count(*) from events where kind='anomaly'` cresce con
  il sim.
- `make audit` continua a passare; aggiunto controllo SQL injection
  via test che invia `'; DROP TABLE events;--` come filtro.

## Phase 5 — Real Adapter

**Obiettivo** (PDF §2): collegare hardware reale. **Un solo vendor alla
volta** (MAVLink o DJI). Decisione del vendor presa con l'utente in una
mini-fase di analisi (test bench disponibile, costi licenza, vincoli
regolatori).

### Cosa fa
1. Decisione vendor (out-of-band) → da preferenza utente.
2. Implementare adapter completo `adapters/<vendor>/adapter.py`:
   - `connect()` / `disconnect()`
   - `stream_telemetry()` async iterator
   - `execute_mission(MissionTask)` → emette `MissionProgress`
   - `request_capture(sensor)` → `CaptureResult` con uri reale (RTMP/
     RTSP/HLS stream descriptor onesto, **mai placeholder mascherato**)
   - `vendor` / `model` properties
3. Compatibilità contract: l'adapter deve produrre gli **stessi**
   `FleetState/Telemetry/Anomaly` del simulator. Il test di
   conformità in `adapters/tests/test_conformance.py` deve passare per
   il nuovo adapter.
4. Frontend: `LiveFeedFrame` accetta lo stream descriptor reale quando
   `available=true`; quando `false` mantiene "VIEWPORT PENDING".
5. Side-by-side col simulator: env flag `SWARM_VENDORS=simulator,mavlink`
   permette di avere fleet mista durante test.

### Security additions Phase 5
- Sigstore / package provenance check per dipendenze vendor (es. mavsdk).
- Validazione stream URL contro allowlist scheme (solo `rtsps://`,
  `https://`).
- mTLS tra adapter e bus (se vendor adapter gira out-of-process).
- Rate-limit telemetry inbound (sanity check: drop se Hz > 50).

### Anti-overreach Phase 5
- Non supportare tutti i vendor in una sola PR.
- Non aggiungere autopilot manual override (mantiene il principio
  "operator sends intent, SwarmOS decides").

### Verifica Phase 5
- Test bench: drone reale in volo (o SITL) → Console mostra `UnitState`
  con vendor corretto, Map mostra geo reale.
- Conformance test verde per il nuovo adapter.
- Console UI non distingue cosmeticamente sim vs reale (perché il
  contratto è lo stesso); badge `vendor` chiaro per audit.

## Phase 6 — Production OS (end-state: pronto a gestire sciami di droni reali)

**Obiettivo finale del piano** (PDF §2/§4 + richiesta utente): SwarmOS
e la Console pronti, completi, distribuibili e utilizzabili per gestire
**sciami di droni in condizioni reali**. Non solo "codice completo": un
sistema che un operatore può davvero usare in campo, su un sito reale,
sotto SLA, con audit, monitoring, supporto, runbook, conformità.

A fine Phase 6 il sistema soddisfa **tutti** i requisiti di:
operatività, sicurezza, osservabilità, supporto, deployment, conformità,
performance, resilienza, documentazione.

### Cosa fa (raggruppato per blocchi)

#### 6.A Safety policy engine
File: `swarm_os/policy.py`, `swarm_os/safety.py`,
`infra/config/sites/<site_id>.yaml`.
- Geofence enforcement: ogni `MissionTask` validato contro polygon del
  sito; reject se waypoint esce o se la traiettoria interseca; rejection
  loggata e mostrata in Console.
- Weather lock: integrazione provider reale (OpenWeather o Aviationweather
  o equivalente) con timeout + cache + fallback safe-default; soglie wind
  mps, visibility km, temp_c, precipitation; `DockState.weather_lock`
  server-side; lock automatico se provider giù.
- Battery threshold per mission kind (es. PATROL 30%, VERIFY 40%, RTL
  forzato sotto 20%).
- Link quality threshold per RTL automatico (sotto 0.3 → RTL).
- Mission priority resolution + preemption: missioni di emergenza
  preemptano patrol.
- No-fly zone: integrazione opzionale NOTAM / EASA NFZ.

#### 6.B Multi-site + runtime config
- `Session.site_id` propagato ovunque.
- Runtime config caricata da `infra/config/sites/<site_id>.yaml`
  (geofence, thresholds, patrol cadence, allowed mission kinds,
  operator allowlist, weather provider creds).
- Hot reload via signal SIGHUP o endpoint `/admin/reload-config`
  (gated da role `commander`).
- Audit log per ogni config change.

#### 6.C Operator auth + RBAC
- JWT (default) o OIDC bridge (`oidc-provider` env).
- Token scaduti corti (15 min access, 8 h refresh).
- Revocation list (Redis-backed).
- Ruoli: `viewer` (sola GET), `operator` (verify/hold/dismiss/return),
  `commander` (escalate, mark-known, config reload, return-all,
  emergency-stop).
- MFA obbligatorio per `commander`.
- Login UI in `frontend/app/login/page.tsx` (minimale, design system
  rispettato).
- Audit ogni login / refresh / revocation.

#### 6.D Observability stack
- Metrics: Prometheus client in backend (`prometheus_client`).
  Endpoint `/metrics` scope-locked al ruolo `commander` o a IP allowlist.
  Metriche minime: `swarm_units_online`, `swarm_anomalies_pending`,
  `swarm_actions_total{action,outcome}`, `swarm_ws_clients`,
  `swarm_mission_duration_seconds`, request histogram per route.
- Dashboards: Grafana `infra/grafana/dashboards/*.json` precaricati.
- Logs: structlog JSON → fluent-bit / Vector → Loki o ELK; correlation
  ID propagato via header `X-Request-ID`.
- Traces: OpenTelemetry SDK su backend (opzionale); export OTLP.
- Health endpoints: `/health` (liveness), `/ready` (readiness, controlla
  DB+Redis+Bus).
- Alerting rules base (`infra/grafana/alerts.yml`):
  - units offline > 1 per > 5 min
  - anomalies pending > N for > T
  - link health < 0.5 sul fleet
  - auth failure rate > soglia
  - dock weather lock attivo > 1 h
  - DB lag / unreachable

#### 6.E Deployment + infra-as-code
- Container images backend + frontend buildate in CI, signed con
  `cosign`, pubblicate su GHCR.
- `infra/k8s/` con manifest Kubernetes (Deployment + Service + Ingress
  + Secret + ConfigMap + HPA + NetworkPolicy + PodSecurityContext
  non-root + readOnlyRootFilesystem).
- `infra/helm/` Helm chart minimale che parametrizza per sito.
- Compose-prod `docker-compose.prod.yml` per deployment small-scale
  (single-node) con TLS terminator + Postgres + Redis.
- Cert manager (cert-manager o Let's Encrypt script).
- Strategia release: blue/green o canary documentata
  (`docs/ops/deploy.md`).
- Backup automation: pg_dump cron in CronJob k8s o systemd timer,
  encryption GPG, retention 30 giorni minimum, restore test mensile.
- Migration playbook (`docs/ops/migrations.md`).

#### 6.F Performance + scale targets
Definire e validare con load test:
- Target per sito: 50 unit attive concorrenti, 5 dock, telemetry 10 Hz
  per unit (= 500 msg/s sul bus), p95 latency WS frame < 200 ms,
  REST p95 < 100 ms.
- Target multi-site: 10 site concorrenti per istanza SwarmOS.
- Capacità burst: 200 unit con degradazione graceful (rate-limit, not
  crash).
- Load test in CI weekly: `tests/load/` con `locust` o `k6` script;
  threshold fail in CI se p95 oltre.
- Chaos test: kill backend → frontend ri-connette in < 6 s e mostra
  link "lost"; kill Redis → orchestrator continua con InMemoryBus
  fallback, anomaly detection degradata ma sicura.

#### 6.G Resilience + disaster recovery
- RTO 1 h, RPO 5 min documentato.
- Failover Redis (Sentinel) + Postgres (replica + Patroni o
  managed RDS) — pattern documentato anche se non sempre deployato.
- Backup test mensile.
- Runbook DR (`docs/ops/disaster-recovery.md`).
- Emergency stop button in Console: comando `EMERGENCY_RTL_ALL` che
  ordina RTL a tutta la flotta (richiede ruolo `commander` + conferma
  doppia).

#### 6.H Documentazione completa
File in `docs/`:
- `docs/architecture/overview.md` — diagrammi C4 (context, container,
  component).
- `docs/architecture/adr/*.md` — Architectural Decision Records.
- `docs/security/threat-model.md` — STRIDE per service.
- `docs/security/incident-response.md` — runbook IR.
- `docs/security/disclosure.md` — public disclosure + bug bounty.
- `docs/api/openapi.yaml` — generato da FastAPI, committato.
- `docs/api/ws-contract.md` — payload WS tipizzati.
- `docs/operator/manual.md` — manuale operatore Console (con
  screenshot, flow di emergenza).
- `docs/operator/training.md` — checklist training nuovo operatore.
- `docs/ops/deploy.md` — guida deployment passo-passo.
- `docs/ops/runbook.md` — procedure operative (rolling restart,
  config reload, emergency stop).
- `docs/ops/disaster-recovery.md`.
- `docs/ops/migrations.md`.
- `docs/compliance/gdpr.md` — data flow, retention, DPA.
- `docs/compliance/drone-regulations.md` — riferimenti EASA / FAA /
  ENAC (Italia) — *informativo, non legal advice*.
- `docs/dev/onboarding.md` — setup dev locale.
- `docs/dev/release-process.md` — versioning + tag + sign + publish.

#### 6.I Compliance + data protection
- GDPR data flow mapping (PII inventory: operator id, possibly
  geolocation, camera frames).
- Retention policy per kind di dato (telemetry 30 gg, events 1 anno,
  audit 7 anni, video frames per policy del sito).
- Data export su richiesta (`/admin/export?operator_id=`).
- Data delete su richiesta (admin tool).
- DPA template (`docs/compliance/dpa-template.md`).
- Drone regulatory: NON è SwarmOS che decide la compliance del volo —
  documentare che l'operatore è responsabile delle autorizzazioni
  (CE class, U-space, etc.). SwarmOS può integrare NOTAM/NFZ feed e
  bloccare missioni in NFZ note, ma non sostituisce la responsabilità
  operativa.

#### 6.J Testing finale
- Test coverage minima: backend 80%, frontend critical path 70%.
- Integration tests end-to-end (`tests/e2e/`): boot sim, operator
  invia verify, anomaly verifying, anomaly verified, escalation,
  return, dock; tutti via API senza mock interni.
- Load test settimanale (Phase 6.F).
- Chaos test mensile (kill components, network partition).
- Security: dynamic test (ZAP baseline scan) in CI, pen-test esterno
  pre-go-live.
- Acceptance test con cliente / operatore reale su un sito di prova.

### Security additions Phase 6
Voci nella tabella S49–S68. Sintesi: JWT/OIDC + RBAC + MFA, mTLS bus,
SBOM + cosign signing, vault prod, IDOR, geofence runtime, weather
provider hardened, TLS public + HSTS, firewall egress, AppArmor/Seccomp,
pen-test, bug bounty, CSP nonce script-src.

### Anti-overreach Phase 6
- Niente autonomia non verificabile (ogni decisione tracciata).
- Niente operator-less mode finché policy engine non è formally-reviewed.
- Niente operazioni che la legge locale del sito non permette
  (responsabilità operatore).
- Non sostituire la due-diligence regolatoria.

### Verifica Phase 6 (deve passare per dichiarare il piano completo)
- Pen-test report esterno → zero critical, no high non-mitigated.
- Load test: target Phase 6.F rispettati a p95.
- Chaos test: nessun crash con component kill; RTL automatico su
  link loss verificato a banco.
- Geofence test: missione con waypoint fuori polygon → reject.
- Weather lock test: stub provider con wind > soglia → dock locked.
- Auth: JWT scaduto → 401; viewer su `/actions/*` → 403; commander
  con MFA → ok.
- IDOR: operator del site A che chiede `/units?site_id=B` → 403.
- Backup restore test riesce in < RTO.
- Audit trail: ogni decisione operatore + ogni mutazione policy
  → row in DB con hash chain integro.
- SBOM presente in release artifacts, immagine container firmata
  (cosign verify ok).
- Doc completa: tutti i file in §6.H committati e linkati da README.
- Manuale operatore: un nuovo operatore può eseguire una verify
  end-to-end seguendo solo `docs/operator/manual.md`.
- Compliance: DPA template + retention policy documentati;
  drone regulation reference presente.

## Phase 7 → Phase 10 — Pre-seed sprint (solo + Claude Code + Codex)

**Contesto reale (decisione utente 2026-05-18)**: il "team" oggi è
**founder solo + Claude Code + Codex**. Niente assunti, niente
hardware, niente investitori, niente partner. Ogni decisione di queste
4 fasi deve essere fattibile in queste condizioni.

**Obiettivo pre-seed**: arrivare a un **MVP demo-able + pacchetto
pitch + outreach attivo** in 3-4 mesi, e a un **seed round chiuso**
(o term sheet firmato) entro 6-9 mesi. Niente hardware reale, niente
deployment reale, niente partner sul campo fino al seed.

**Giurisdizioni target**: Rwanda + Dubai (UAE). Rwanda per il caso
"bene pubblico" (defibrillatore, ricerca dispersi, Protezione Civile —
Zipline ha già aperto la strada lì), Dubai per "premium / protezione
case + incendio sterpaglie / wildfire desertico". Entrambe hanno
autorità collaborative (RCAA + Dubai DCAA / GCAA), entrambe vogliono
attirare deep-tech.

**Principio guida nuovo** (sostituisce "SwarmOS decides. Console
supervises." una volta entrati in Fase 7): **"SwarmOS decide ed
esegue. L'umano può intervenire se necessario."** Human-on-the-loop,
non in-the-loop.

## Phase 7 — MVP demo-able (solo + AI, 6-10 settimane)

**Obiettivo**: video demo da 90 secondi che mostra il sistema reagire
autonomamente a 3 scenari MVP (incendio, SOS casa, defibrillatore) in
simulazione realistica. Il demo deve essere **girabile live in 5 minuti
su laptop**, niente magia di editing.

Tutto in simulazione — zero hardware. Slice tattiche delle Fasi 11-26
prese solo quanto basta per la demo. Profondità completa di ogni fase
arriva dopo il seed.

- **7.A** Tre scenari simulati in `sim/scenarios/`:
  - `wildfire_dubai.yaml`: incendio sterpaglie desertico, propagazione,
    detection CV + termocamera simulata, dispatch multi-drone
    autonomo, contenimento perimetrale, handoff Civil Defense Dubai.
  - `home_sos_dubai.yaml`: villa abbonata, sensore fumo + pulsante
    SOS app, dispatch drone perimetrale, ispezione, live feed
    proprietario.
  - `aed_rwanda.yaml`: chiamata 912 (numero emergenza Rwanda) → dispatch
    drone-AED → consegna a indirizzo cittadino in Kigali. Inspired da
    pattern Zipline ma per scenari emergency-on-demand.
- **7.B** `swarm_os/autonomy.py` deterministico funzionante sui 3
  scenari (slice della Phase 11 — solo soglie, no ML).
- **7.C** Console esistente come "osservatorio" con eyebrow `AUTO`
  per ogni decisione autonoma (no intent buttons per la demo — è
  uno spettacolo di autonomia).
- **7.D** Mobile mockup funzionante (Next.js mobile o Expo) con
  pulsante SOS one-tap che genera evento nella sim. No app store, no
  publishing — solo demo locale.
- **7.E** Computer vision su modelli pretrained + dataset pubblici:
  - Fuoco: **FLAME** + **D-Fire** dataset, YOLOv8 pretrained
    fine-tuned su 2-3 epoche.
  - Aerial detection: **VisDrone** pretrained.
  - Inference live nello scenario, non training pesante.
- **7.F** Federazione minima (slice della Phase 12): 2-3 celle che si
  passano un drone durante il wildfire scenario. Solo quanto basta a
  vedere il "sciame di sciami" in azione, niente meta-coordinatore
  completo.
- **7.G** Dispatch sim base (slice della Phase 18): 100 settori, 30
  droni, 10 docking station distribuite su mappa di Kigali o Dubai
  Marina. ETA calcolato realistico (3D path planning semplificato).
- **7.H** Demo recording pipeline: script Python che lancia scenario
  in headless + `ffmpeg` screen capture + voice-over scriptato (TTS
  inglese + italiano).
- **7.I** Metrics dashboard live durante demo: tempo risposta p50/p95,
  decisioni autonome corrette vs override, falsi positivi. Numeri reali
  della sim, quotabili nel pitch.
- **7.J** "Make demo" target: `make demo-wildfire`, `make demo-home`,
  `make demo-aed`. Replicabile dal computer di un investitore in 1 cmd.

**Gate**: video demo 90s girabile in 5 minuti, con metriche convincenti
(ETA p95 < 120s in sim, accuratezza decisioni > 90% su dataset noto).

## Phase 8 — Materiali pitch (solo + AI, 2-4 settimane)

**Obiettivo**: arrivare a una demo call con tutto pronto. Niente
slide brutte, niente whitepaper vago.

- **8.A** Pitch deck 12-15 slide:
  problema → mercato → soluzione → demo embed → traction (=metriche
  sim) → team (=founder + AI stack) → business model → giurisdizione
  + go-to-market Rwanda/Dubai → roadmap → ask + use-of-funds.
- **8.B** Demo video editato 90s, sottotitolato inglese, per
  email/LinkedIn/landing.
- **8.C** Technical whitepaper 15-25 pagine: architettura SwarmOS,
  shield deterministico vs ML, federazione, decision log firmato,
  perché Rwanda+Dubai. Pubblico target: CTO degli investitori
  + advisor tecnici.
- **8.D** One-pager PDF per cold email.
- **8.E** Financial model Google Sheets, 5 anni:
  - Costi: hardware (droni + dock), cloud, team, legal/insurance.
  - Ricavi: abbonamento individuale (Dubai $20-50/mese), municipal
    contract (Rwanda — paga il governo/donor), insurance partnerships.
  - Sensitivity: numero abbonati × penetrazione × ARPU.
  - Break-even per città.
- **8.F** Business plan 20 pagine: TAM/SAM/SOM, competitive analysis
  (Zipline, Skydio, Brinc, Hivemapper), unit economics, milestone
  timeline.
- **8.G** Landing page (Next.js, hostata su Vercel) con email capture,
  demo video embed, contatto founder.
- **8.H** Press kit minimal: logo SVG, screenshot, founder bio,
  one-pager.
- **8.I** Profili pubblici: LinkedIn aggiornato, Twitter/X attivo,
  AngelList/Crunchbase claim.

**Gate**: pacchetto inviabile a investitore Tier-1 senza vergogna —
verificato da almeno 1 advisor esterno (anche fractional/payback in
equity).

## Phase 9 — Outreach pre-seed (solo, 4-12 settimane)

**Obiettivo**: chiudere primo capitale (target 500K-2M EUR pre-seed o
seed bridge).

- **9.A** Lista 100 investitori target:
  - **VC deep-tech UE/USA** con tesi su autonomous systems
    (Lakestar, NGP Capital, Bessemer, In-Q-Tel, Lockheed Martin
    Ventures, ecc.).
  - **VC climate-tech** (per il pitch wildfire/Protezione Civile).
  - **VC Africa-focused** (Partech Africa, TLcom, Norrsken22 —
    perfetti per la narrativa Rwanda).
  - **VC GCC / Middle East** (MEVP, Wamda, Saudi PIF-linked,
    Mubadala — perfetti per Dubai).
  - **Angel italiani con exit** (deep-tech background).
  - **Family office** Gulf + Italian.
- **9.B** Lista 30 partner potenziali:
  - **Rwanda**: RCAA (autorità aviazione), MININFRA, Rwanda
    Development Board, Kigali City, Zipline (potenziale parnership
    o quanto meno benchmark), Civil Protection Rwanda.
  - **Dubai**: DCAA, RTA (Roads & Transport), Dubai Civil Defense
    (incendi), Dubai Police (per coordinamento, non subordinazione),
    DEWA, EmiratesNBD (insurance).
  - **Insurance/reinsurance**: SwissRe, Munich Re partnership
    Africa, Dubai Islamic Insurance.
- **9.C** Lista 20 advisor potenziali (pagamento equity-only o
  fractional):
  - Ex-Zipline operations Rwanda.
  - Ex-EASA / ex-FAA con esperienza autonomous certification.
  - Ex-founder con exit deep-tech (preferibile drone/AI).
  - Ex-VVF/Civil Defense ufficiale.
  - Legal counsel drone law UAE + UE.
- **9.D** Cold outreach: email + LinkedIn + intro warm. Target: 30-50
  demo call nei primi 3 mesi.
- **9.E** Letter of Intent da 3-5 partner potenziali (non vincolanti
  — servono solo come validazione narrativa per investitori).
- **9.F** Contatti preliminari regolatori: email/call esplorative con
  RCAA + Dubai DCAA / GCAA. **Solo esplorative**, niente applicazioni
  SORA o equivalenti finché non c'è capitale + counsel locale.
- **9.G** Iterazione pitch su feedback (deck v2, v3, v4 normale).
- **9.H** Convertire interesse in term sheet.

**Gate**: term sheet firmato, oppure 3+ investitori in due diligence
attiva con LOI verbali.

## Phase 10 — Seed close + team minimo (mesi 6-9)

**Obiettivo**: trasformarsi da founder solo + AI in azienda operativa
minima.

- **10.A** Setup legale: holding (probabilmente Delaware o Singapore
  per investitori internazionali) + opco locale Rwanda e/o Dubai. Counsel
  locale + counsel corporate USA/SG.
- **10.B** Closing seed round.
- **10.C** Prime 3-5 assunzioni in ordine di criticità:
  1. **CTO / tech-lead senior** (co-decide architettura, libera il
     founder dal codice quotidiano).
  2. **ML/CV engineer** (per portare Fase 13 da pretrained a custom).
  3. **Hardware/integrazione engineer** (per Fase 17).
  4. **Business development + legal locale** Rwanda o Dubai (per
     trattative regolatorie + partner).
  5. **(Opzionale) Operations** Rwanda+Dubai (fractional all'inizio).
- **10.D** Workspace fisico minimo (anche coworking + lab spazio
  separato per drone bench).
- **10.E** Hardware procurement iniziale: 5-10 droni PX4-compatible
  per test (Holybro X500, ModalAI VOXL2, o equivalente; budget
  100-200k EUR include payload swap + RTK base + spare parts) +
  1-2 docking station prototype (BRINC o costruzione custom, valutare
  partnership).
- **10.F** Primo pilota concordato con partner pubblico:
  - **Rwanda preferibile come primo pilota** per AED/ricerca
    dispersi (più facile da autorizzare, allineamento con Vision
    2050 Rwanda, Zipline ha già normalizzato il volo BVLOS).
  - **Dubai parallelo** per wildfire test in zone desertiche
    extra-urbane (low-risk, no popolazione).
- **10.G** Apertura cantieri Fasi 11+ in parallelo (con team, non più
  solo founder).

**Gate**: primo drone reale vola sotto controllo SwarmOS in spazio
aereo controllato (campo prove privato Dubai o area test Rwanda
autorizzata).

---

## Phase 11 → Phase 26 — Post-seed execution (con team + capitale)

> Queste 16 fasi sono la traduzione della "visione finale"
> (infrastruttura urbana autonoma) in esecuzione dopo il seed. Sono
> **scheletro di pianificazione** — ogni fase qui va espansa con la
> stessa granularità delle Fasi 0–6 prima dell'esecuzione, con il team
> in carne ed ossa che è stato hired in Fase 10.
>
> Pre-seed (Fasi 7-10) ha già usato slice tattiche di queste fasi per
> la demo MVP; qui si fa l'esecuzione a regime, con hardware reale,
> deployment reale, autorità reali.
>
> **Focus MVP** (decisione utente 2026-05-18, da Fase 7): incendio +
> protezione case + bene pubblico. Casi "law-enforcement-adjacent"
> (inseguimento, abbagliamento aggressori) restano fuori MVP — vengono
> valutati solo dopo trazione sui casi sopra. Conseguenza pratica:
> Fase 19 (intervento attivo) è ristrutturata per priorità; Fasi 21+23
> (compliance pesante, etica) sono trattate come requisito legale
> locale, non come driver di prodotto.
>
> **Giurisdizioni**: Rwanda + Dubai prima, eventuale espansione UE/USA
> dopo trazione (Fase 26).

## Phase 11 — Autonomia decisionale (no operator in the loop)

**Obiettivo**: il sistema decide e agisce da solo su anomalie e missioni.
L'operatore esiste solo come override. Pre-seed (Fase 7.B) ha già la
versione deterministica funzionante in sim — qui si porta a maturità in
produzione.

- **11.A** Inversione default in Console: diventa osservatorio. Le 4
  intent attuali (`verify / hold-patrol / dismiss / return`) restano
  come pulsanti di override, non sono più il flusso primario.
- **11.B** Motore `swarm_os/autonomy.py` produzione: dato un'anomalia +
  contesto + policy del sito, restituisce decisione `VERIFY | DISMISS
  | ESCALATE | WAIT`. Soglie deterministiche per partire, classificatore
  ML in Fase 13.C.
- **11.B-bis** Modalità ombra obbligatoria per ogni nuovo decisore prima
  del go-live: decide + logga + confronta con decisione umana per due
  settimane; flip del default solo quando convergono.
- **11.C** Hook intervento umano:
  - Override soft (annulla/modifica decisione autonoma in corso).
  - Policy nudge a scadenza (alza/abbassa soglie temporaneamente).
  - Kill switch (atterra tutti i droni; unica eccezione alla regola
    "no red" del design system; richiede commander + MFA).
- **11.D** Eyebrow `AUTO` / `OVERRIDE` ovunque nella Console + timeline.
- **11.E** Decision log firmato (hash chain immutabile su `events`).
- **11.F** Explainability obbligatoria per ogni decisione autonoma
  (SHAP / feature attribution salvata nel decision log).

**Gate**: una settimana in produzione su un sito Rwanda o Dubai senza
override umano critici; decisori in shadow mode con < 5% divergenza.

## Phase 12 — Federazione "sciame di sciami"

**Obiettivo**: scalare da un coordinatore singleton a una rete di sciami
autonomi che collaborano. Pre-seed (Fase 7.F) ha già 2-3 celle in sim;
qui si fa l'architettura completa.

- **12.A** Nuova entità `Swarm` in `core/swarm_core/messages.py` (id,
  goal corrente, droni assegnati, area di responsabilità, stato salute).
- **12.B** `SwarmCellCoordinator` per ogni sciame al posto del singleton
  `SwarmCoordinator`. Lock per `swarm_id`.
- **12.C** Bus Redis namespaced per cella: `swarm:cell:<id>:telemetry`,
  `swarm:cell:<id>:events`.
- **12.D** `swarm_os/meta_coordinator.py`: assegna obiettivi alle celle
  (non missioni atomiche ai droni). Bilanciamento carico, copertura,
  riserva strategica.
- **12.E** Protocollo mesh inter-sciame: topic `swarm:mesh:offer`,
  `swarm:mesh:request`, `swarm:mesh:commit`. Algoritmo contract-net per
  richiesta/offerta aiuto. Trasferimento temporaneo droni tra celle.
- **12.F** Fusione/scissione dinamica sciami in base alla situazione.
- **12.G** Backpressure: una cella può rifiutare assegnazioni se sta
  gestendo un'emergenza locale.
- **12.H** Multi-site simultaneo in una sola istanza (sostituisce il
  modello one-site-at-a-time di Phase 6.B). Critico per gestire Rwanda
  + Dubai in parallelo dalla stessa control plane.

**Gate**: chaos test (kill random di celle) → sistema converge senza
intervento; latenza inter-cell mesh p95 < 200ms.

## Phase 13 — Intelligenza (ML/AI)

**Obiettivo**: sostituire le regole deterministiche del livello
decisionale con modelli appresi. Shield deterministico (Fase 6.A) resta
intatto sotto. Pre-seed (Fase 7.E) ha già modelli pretrained su dataset
pubblici — qui si addestra su dati propri.

- **13.A** Computer vision on-edge sui droni: YOLOv8 / RT-DETR per
  detection persone/veicoli/fuoco/animali. Distillazione modello grosso
  → modello edge. Training su dati propri (incendi sterpaglie Dubai
  + scenari Rwanda).
- **13.B** Tracking soggetti (ByteTrack / BoT-SORT) per frame-su-frame.
- **13.C** Classificatore disposizione anomalie (gradient boosting,
  leggero, interpretabile, calibrato). Sostituisce le soglie di Fase 11.B.
- **13.D** Retraining settimanale sugli override umani come label di
  training oro.
- **13.E** Reinforcement learning per pattugliamento (PPO o bandit
  contestuali). Funzione di valore: copertura × novità × rischio − costo.
- **13.F** Multi-agent RL per allocazione tra sciami (dopo Phase 12).
- **13.G** Forecast: degrado batterie (importantissimo nel caldo Dubai
  50°+), meteo nowcasting locale, picchi anomalie (stagioni: harmattan
  Rwanda, shamal Dubai).
- **13.H** LLM per briefing turno + spiegazione decisioni +
  configurazione assistita. Multilingua (EN/AR/KIN). **MAI** safety
  runtime.
- **13.I** Pipeline MLOps: model registry, A/B shadow deployment, drift
  detection, GPU centrale per training.
- **13.J** Feature store leggero su TimescaleDB esistente.
- **13.K** Modulo `swarm_os/intelligence/` con classifier, scoring,
  calibration, explainability.

**Gate**: ogni modello ML ha passato shadow mode + audit di calibrazione
+ SHAP/attention salvate nel decision log.

## Phase 14 — Detection multimodale automatica

**Obiettivo**: il sistema rileva emergenze senza che nessuno prema un
pulsante.

- **14.A** Integrazione sensori IoT urbani: microfoni, qualità aria
  (importante per Dubai polvere/calima), fumo, vibrazioni.
- **14.B** Detection audio (esplosioni, vetri rotti — modelli tipo
  ShotSpotter ma per scenari MVP, non gunshot).
- **14.C** Detection da camere fisse convenzionate (centri commerciali,
  compound privati abbonati in Dubai; mercati e zone pubbliche in
  Kigali).
- **14.D** Fusione multi-sorgente (sensore + camera + segnalazione
  utente da app).
- **14.E** Trigger automatico dispatching senza intervento umano.
- **14.F** Filtro falsi positivi multimodale (rumore singolo ≠
  emergenza).

**Gate**: tasso falsi positivi < 1% su dataset città-scala di 30 giorni
in giurisdizione attiva.

## Phase 15 — App cittadino (consumer)

**Obiettivo**: l'utente abbonato (o cittadino in scenari pubblici) può
chiedere aiuto. Pre-seed (Fase 7.D) ha già un mockup funzionante per la
demo — qui si porta a livello prodotto.

- **15.A** App nativa iOS/Android (non solo web mobile). Localizzazioni:
  EN, AR (Dubai), KIN (Rwanda) come minimo.
- **15.B** Pulsante SOS one-tap con timer "annulla" + anti-misclick.
- **15.C** SOS silenzioso (movimento, password coercion, shake).
- **15.D** Geolocalizzazione opt-in.
- **15.E** Notifiche push: drone in arrivo, ETA, drone sul posto.
- **15.F** Video live dal drone all'utente (rassicurazione).
- **15.G** Comunicazione audio bidirezionale utente↔drone (TTS
  multilingua, voce calma scriptata).
- **15.H** Storico personale interventi.
- **15.I** Profilo medico/contatti d'emergenza (per dispatch informato).
- **15.J** Sharing localizzazione con persone fidate durante emergenza.
- **15.K** Modalità "viaggio sicuro casa" (drone scorta opt-in
  perimetrale, non per inseguimento).

**Gate**: tempo da tap-SOS a drone-arrivato p95 < 120s; UX accessibilità
WCAG AA; pubblicato su Apple App Store + Google Play in entrambe le
giurisdizioni.

## Phase 16 — Business / abbonamenti

**Obiettivo**: modello di ricavo sostenibile, multi-tenant per Rwanda +
Dubai con economie diverse.

- **16.A** Multi-tenant: provider per nazione/città/quartiere/compound.
- **16.B** Piani abbonamento:
  - Dubai: B2C premium $20-50/mese individuale; B2B compound/villa
    $200-500/mese; B2G assistenza Civil Defense.
  - Rwanda: B2G dominante (governo paga per accesso pubblico AED +
    Civil Protection); B2C low-cost per ceto medio Kigali ($2-5/mese).
- **16.C** Billing ricorrente: Stripe (Dubai globale), Flutterwave o
  MTN MoMo (Rwanda), bonifico bancario per B2B/B2G.
- **16.D** SLA per piano (tempo di risposta garantito; gradient da
  premium a community).
- **16.E** Dashboard amministrazione city/government partner.
- **16.F** Integrazione assicurazioni (sconti polizza per abbonati;
  Dubai Islamic Insurance, AAR Rwanda).
- **16.G** KPI pubblici (trasparenza: tempi risposta, interventi, falsi
  positivi).
- **16.H** White-label per partner (operatore telecom, banca, sviluppatore
  immobiliare).

**Gate**: revenue model dimostrabile su un pilota in entrambe le
giurisdizioni; unit economics positive a 12 mesi proiettati.

## Phase 17 — Infrastruttura fisica (docking stations urbane)

**Obiettivo**: rete di docking station strategicamente posizionate.
Profili ambientali molto diversi tra Rwanda (clima collinare, 1500m,
piogge) e Dubai (deserto, 50°+ estate, polvere, salinità costiera).

- **17.A** Hardware docking station weather-proof per due profili
  ambientali distinti: tropical highland (Rwanda) + desert/coastal
  (Dubai). Anti-vandalismo.
- **17.B** Algoritmo posizionamento ottimo (copertura città, ETA target,
  vincoli legali locali).
- **17.C** Permessi pubblici: Kigali City + Rwanda Development Board
  per suolo pubblico; Dubai Municipality + RTA per suolo pubblico;
  accordi con sviluppatori privati (Emaar/Damac Dubai, Vision City
  Rwanda) per palazzi privati.
- **17.D** Alimentazione (rete + solare backup obbligatorio — Rwanda
  rete instabile, Dubai sole abbondante; UPS sempre).
- **17.E** Connettività (4G/5G primaria + LoRaWAN backup; Rwanda ha MTN
  e Airtel, Dubai ha du e Etisalat).
- **17.F** Diagnostica remota docking station.
- **17.G** Manutenzione predittiva (drone + dock).
- **17.H** Inventory management droni (rotazione, riparazioni,
  sostituzioni; supply chain hardware da Cina via Dubai hub).
- **17.I** Carico drone su dock libero più vicino dopo intervento.

**Gate**: densità docking station sufficiente a garantire ETA < 120s
sul 95% del territorio coperto in zona pilota (quartiere Kigali e
quartiere Dubai distinti).

## Phase 18 — Dispatch intelligente città-scala

**Obiettivo**: scegliere il drone giusto e portarlo lì nel tempo target.
Pre-seed (Fase 7.G) ha già il dispatch in sim — qui si fa city-scale
reale.

- **18.A** Algoritmo "qual drone mandare" (distanza, batteria, tipo
  payload, meteo, traffico aereo, vento — Dubai shamal forte).
- **18.B** Path planning 3D urbano (Dubai grattacieli alti, Kigali
  topografia collinare, evita palazzi, alberi, linee elettriche, NFZ).
- **18.C** ETA garantito 1-2 minuti come SLO.
- **18.D** Backup drone automatico se primo fallisce.
- **18.E** Dispatch multi-drone con ruoli specializzati.
- **18.F** Coda priorità (emergenza vitale > incendio > protezione
  case > ronda).
- **18.G** Pre-posizionamento predittivo (sposta droni dove probabilmente
  serviranno, da forecast 13.G).
- **18.H** Coordinamento traffico aereo locale (altri droni, elisoccorso,
  Zipline Rwanda se opera ancora). Dubai ha già un quadro UTM nascente.

**Gate**: SLO ETA p95 < 120s su 1000+ dispatch reali per giurisdizione;
zero near-miss con traffico aereo terzo.

## Phase 19 — Intervento attivo (non solo osservare)

**Obiettivo**: il drone agisce sulla situazione, non solo la documenta.

> **Priorità di prodotto (MVP)**: incendio + protezione case + bene
> pubblico (defibrillatore, ricerca dispersi). I casi d'uso
> "law-enforcement-adjacent" (inseguimento sospetti, abbagliamento
> aggressori) restano **fuori MVP** — vengono valutati solo dopo trazione
> sui casi a bene pubblico evidente, e probabilmente mai in giurisdizioni
> dove il rapporto popolazione-polizia è teso.

### Incendio (priorità 1 — MVP)
- **19.A** Camera termica per detection precoce + targeting fonte calore.
  Use case prioritario Dubai: incendi sterpaglie/desert vegetation,
  incendi compound; Rwanda: incendi mercati, incendi mattoneria/cottage
  industries.
- **19.B** Sistema spegnimento mirato (capsule polvere/gel/aerosol
  pulito, non spray indiscriminato; payload sostenibile in clima caldo).
- **19.C** Coordinamento multi-drone per contenimento perimetrale (da
  Phase 12 federazione).
- **19.D** Evacuazione assistita (annunci vocali multilingua, indicazione
  vie fuga).
- **19.E** Stop intervento se aria contaminata o pericolo esplosione
  (deterministico, parte dello shield 6.A).
- **19.F** Handoff strutturato:
  - Dubai → Dubai Civil Defense (incendi).
  - Rwanda → Rwanda National Police / Rwanda Fire & Rescue Brigade.

### Protezione case (priorità 2 — MVP, soprattutto Dubai)
- **19.G** Risposta a chiamata SOS da app del proprietario (da Phase 15.B).
- **19.H** Risposta a sensori IoT casa abbonata (fumo, allarme intrusione
  domotica, vetro rotto — da Phase 14.A).
- **19.I** Ispezione perimetrale on-demand (proprietario chiede
  "controlla il giardino"). Use case dominante villa/compound Dubai.
- **19.J** Illuminazione perimetrale dissuasiva (faro LED ad alta
  intensità — uso passivo, non puntato su persone).
- **19.K** Live feed criptato proprietario + (su richiesta esplicita
  proprietario) handoff alle autorità tramite Phase 20.
- **19.L** Modalità "viaggio sicuro casa" (drone scorta opt-in
  perimetrale).
- **19.M** Audio bidirezionale per dialogo proprietario↔persona
  presente (es. corriere, vicino, addetto manutenzione).

### Bene pubblico (priorità 3 — MVP, soprattutto Rwanda)
- **19.N** Drone-defibrillatore per arresti cardiaci (modello già
  esistente Svezia/Olanda; Rwanda first-mover Africa).
- **19.O** Ricerca dispersi (bambini, anziani, escursionisti area
  laghi/vulcani Rwanda; turisti in deserto Dubai) con termocamera + CV.
- **19.P** Illuminazione zone pubbliche pericolose temporanee (lavori
  stradali, incidente notturno).
- **19.Q** Supporto Protezione Civile durante eventi climatici (frane
  Rwanda stagione piogge, tempeste sabbia Dubai).
- **19.R** Ricognizione post-evento (allagamenti, frane, incendi
  spenti) per prioritizzare soccorsi.

### Payload + hardware (trasversale a tutte le priorità)
- **19.S** Modulo payload swappabile (termocamera, spegnimento,
  defibrillatore, kit primo soccorso, faro).
- **19.T** Standardizzazione interfaccia drone↔payload (per terze parti).

### Fuori MVP — valutare solo dopo trazione e contesto locale
- **19.U** Sicurezza personale antiaggressione (faro/sirena/tracking
  soggetto in fuga). Richiede compliance Phase 21 completa + accettazione
  pubblica + valutazione caso per caso giurisdizione.

**Gate MVP**: ogni payload incendio/casa/bene-pubblico ha passato
sicurezza fisica + approvazione regolatoria locale + insurance coverage.
Use case 19.U **non parte** finché non c'è trazione + autorizzazione
specifica per giurisdizione (probabilmente mai in Rwanda; valutabile in
Dubai con framework chiaro).

## Phase 20 — Integrazione autorità locali

**Obiettivo**: il sistema lavora **prima** dei servizi tradizionali,
mai **al posto** loro. Posizionamento "infrastruttura primo strato",
non "polizia privata" — coerente con la sensibilità locale.

- **20.A** Chiamata automatica numero emergenza nazionale:
  - Rwanda: 912 (emergency), 113 (police), 911/912 (medical/fire).
  - Dubai: 999 (police), 998 (ambulance), 997 (fire).
- **20.B** Live feed alle autorità competenti con autenticazione (Dubai
  Civil Defense per incendi, Rwanda Fire & Rescue + RBC per emergenze
  mediche).
- **20.C** Handoff custodia evento (drone passa il "caso" all'umano
  appena arrivano).
- **20.D** Chain of custody video/audio per uso giudiziale (estende
  l'hash chain di 11.E).
- **20.E** API verso centrali operative locali.
- **20.F** Coordinamento con elisoccorso e altri servizi aerei
  (separazione altitudini).
- **20.G** Protocollo "stand-down" quando arriva pattuglia (drone si
  ritira o supporta in modo subordinato).

**Gate**: accordo operativo scritto con almeno una autorità per
giurisdizione (es. Dubai Civil Defense per incendi, Rwanda Civil
Protection per emergenze mediche); protocollo handoff testato in
esercitazione congiunta.

## Phase 21 — Compliance giurisdizione target

**Obiettivo**: il sistema è legale e auditabile **in Rwanda e Dubai**.
UE/USA non sono obiettivo prima della Phase 26.

- **21.A** Autorizzazione volo BVLOS / autonomo urbano:
  - **Rwanda**: RCAA — Rwanda Civil Aviation Authority. Quadro
    progressivo, hanno già autorizzato Zipline. Categoria
    "performance-based" applicabile.
  - **Dubai**: DCAA + GCAA federale + Dubai Sky Dome iniziativa.
    Sandbox attivi per droni autonomi.
- **21.B** Coordinamento traffico aereo: Rwanda RCAA UTM nascente;
  Dubai SkyHub UTM in pilota — partecipare al pilota se accessibile.
- **21.C** Privacy data protection:
  - **Rwanda**: Law N° 058/2021 (data protection); registrazione
    presso NCSA. Privacy mask volti/targhe/finestre automatica.
  - **Dubai**: PDPL (Personal Data Protection Law UAE 2021) + DIFC
    DP Law se holding DIFC. Stessa privacy mask.
- **21.D** Conservazione dati: retention policy esplicita per
  giurisdizione, cancellazione automatica, sovranità dati locale.
- **21.E** DPIA / equivalent risk assessment pubblicato per ogni città
  servita.
- **21.F** Consenso cittadini opt-in (per scenari attivi, non per zona
  pubblica con privacy mask).
- **21.G** Diritto all'oblio video (richieste cancellazione).
- **21.H** Audit indipendente algoritmico annuale (terza parte
  certificata).
- **21.I** Compliance uso dispositivi attivi (sirene/luci): valutazione
  legale locale caso per caso.
- **21.J** Polizza assicurativa civile multimilionaria (Lloyd's
  internazionale + reinsurance locale).
- **21.K** Accountability cascade chiara (provider → city partner →
  utente).
- **21.L** Public oversight committee per ogni città servita
  (composizione: cittadini + autorità + advisor).
- **21.M** Trasparenza pubblica: report quadrimestrale falsi positivi,
  interventi, danni.

**Gate**: autorizzazione regolatoria scritta da autorità competente per
ogni città servita. **Bloccante**: senza 21.A non si vola.

## Phase 22 — Sicurezza fisica e cyber dei droni

**Obiettivo**: il sistema resiste ad attacchi attivi. Rilevante
soprattutto Dubai (target alto-profilo, capacità adversariali
sofisticate disponibili nella regione).

- **22.A** Anti-spoofing GPS (multi-constellation: GPS + GLONASS +
  Galileo + BeiDou; RTK quando possibile).
- **22.B** Resistenza a jamming radio (frequency hopping).
- **22.C** Anti-hijacking comandi (firma crittografica end-to-end).
- **22.D** Backup comms multi-canale (4G + LoRa + satellite Iridium
  per fallback assoluto).
- **22.E** Protezione fisica drone (carrozzeria leggera, fail-safe
  atterraggio, ditching sicuro).
- **22.F** Decommissioning sicuro se catturato (wipe + brick remoto).
- **22.G** Difesa anti-drone offensivo (se qualcuno cerca di abbatterli).
- **22.H** Penetration testing annuale obbligatorio (red team esterno).
- **22.I** Bug bounty program.
- **22.J** SBOM completo + supply chain attestation per ogni componente
  (estende Phase 6.E cosign).

**Gate**: red team esterno (drone hijack + GPS spoof + radio jam) tutti
falliti, almeno una volta per giurisdizione.

## Phase 23 — Etica + accettazione locale

**Obiettivo**: il sistema è accettato culturalmente nelle giurisdizioni
target. Le metriche di "accettazione" cambiano profondamente tra Kigali
(comunità collettivista, post-genocidio, alta fiducia istituzioni) e
Dubai (multiculturale, transitoria, alta tolleranza tech).

- **23.A** Bias check algoritmico (più droni in zone povere? falsi
  positivi su gruppi specifici? — particolarmente delicato Dubai con
  manodopera espatriata).
- **23.B** Trasparenza modelli ML (cosa decidono e perché — estende 13.K).
- **23.C** Diritto a non essere ripreso (opt-out cittadini dove
  applicabile).
- **23.D** Community advisory board locale (composizione adatta alla
  cultura: per Rwanda — leader cellule amministrative + civil society;
  per Dubai — rappresentanti compound + camere di commercio).
- **23.E** Comunicazione pubblica chiara (cosa il sistema fa e NON fa);
  ufficio stampa locale.
- **23.F** Sondaggi accettazione periodici per quartiere/compound.
- **23.G** Modalità "drone visibile" (livrea distintiva, luci sempre
  accese, suono identificabile).
- **23.H** Trasparenza statistiche reali pubblicate, non marketing.

**Gate**: community advisory board attivo + accettazione pubblica >
soglia in sondaggi locali; revisione semestrale.

## Phase 24 — Resilienza e disastri

**Obiettivo**: il sistema funziona anche quando il mondo intorno crolla.
Profili disastro diversi: Rwanda (frane, terremoti minori, piogge);
Dubai (tempeste sabbia, alluvioni urbane occasionali, eventi tecnologici).

- **24.A** Failover regionale (region AWS Bahrain o Frankfurt per
  Dubai; region AWS Cape Town o GCP Johannesburg per Rwanda; cross-
  region replication).
- **24.B** Modalità degraded (rete cellulare giù → mesh radio drone-to-
  drone + LoRa backup).
- **24.C** Backup energia docking station (batteria 48h+, solare in
  entrambe le giurisdizioni).
- **24.D** Continuità durante eventi di massa (terremoto, alluvione,
  tempesta).
- **24.E** Disaster mode (sospende SLA normali, prioritizza vite umane).

**Gate**: DR drill annuale superato per giurisdizione; RTO/RPO
dichiarati e rispettati.

## Phase 25 — Operazioni & supporto

**Obiettivo**: il sistema autonomo ha comunque un'organizzazione umana
dietro, distribuita tra le giurisdizioni servite.

- **25.A** Operations center 24/7 per fuso orario coperto (Dubai GMT+4
  + Kigali GMT+2 sono solo 2h di delta — un team unico con shifting
  funziona).
- **25.B** Tier 1/2/3 support per cittadini abbonati (multilingua
  EN/AR/KIN/FR).
- **25.C** Onboarding city partner (installazione, calibrazione,
  training operatori locali).
- **25.D** Programma certificazione tecnici manutenzione locali
  (riduce dipendenza espatriati).
- **25.E** Centro ricerca + sviluppo continuo (HQ R&D Dubai o
  Lussemburgo per ragioni fiscali; team distribuiti).

**Gate**: SLO supporto p95 < target; turnover tecnici certificati sotto
soglia.

## Phase 26 — Espansione

**Obiettivo**: scalare oltre Rwanda + Dubai.

- **26.A** Seconda ondata: GCC (Riyadh / NEOM Arabia Saudita, Doha
  Qatar) + East Africa (Nairobi Kenya, Kampala Uganda); copia il
  template Dubai e Rwanda con minimi adattamenti.
- **26.B** Terza ondata (post-trazione): rientro UE/USA con caso di
  successo dimostrato, dati reali in mano, framework regolatori UE
  affrontabili (SORA Specific). A questo punto Phase 21 si estende
  per coprire EASA + GDPR + FAA.
- **26.C** Adapter vendor multipli (PX4, DJI Enterprise se serve, custom
  hardware proprietario).
- **26.D** Marketplace skill plugin (detector specializzati per use
  case nuovi: agricoltura precision, monitoraggio infrastrutture).
- **26.E** Open API per integratori terzi.
- **26.F** SDK Python/TypeScript.
- **26.G** Sandbox/demo cloud per prospect.

**Gate**: ogni nuova città servita con stesso codebase + adattamenti
regolatori locali + community advisory board attivo entro 6 mesi
dall'avvio.

## Dipendenze tra le fasi 11-26

```
11 (autonomia) ──┬──> 13 (ML)  ──┬──> 18 (dispatch città)
                 │                │
                 ├──> 14 (detection multimodale)
                 │                │
                 └──> 12 (federazione) ──> 18
                                  │
15 (app cittadino) ───────────────┼──> 16 (business)
                                  │
17 (docking station) ─────────────┼──> 18 ──> 19 (intervento attivo)
                                  │
21 (compliance giurisdizione) ── BLOCKER trasversale per 19, 20, 26
                                  │
20 (autorità locali) ────> 19 ────┘
22 (sicurezza) ── trasversale (richiesto da 19 in poi)
23 (etica/accettazione) ── trasversale (richiesto da 19 in poi)
24 (resilienza) ── richiesto prima di 26
25 (operazioni) ── richiesto per ogni pilot live
```

**Ordine consigliato di attacco post-seed** (sequenziale dove non
sganciabile, parallelo dove indipendente):

1. **Fase 11** prima di tutto (sblocca semantica autonoma; pre-seed
   ha già fondamenta deterministiche).
2. **Fase 13 (ML)** + **Fase 12 (federazione)** in parallelo (branch
   distinti) — entrambe appoggiate sulla Fase 11.
3. **Fase 14 (detection multimodale)** dopo 13.A/13.B (CV pronta).
4. **Fase 15 (app)** in parallelo a tutto (team frontend distinto).
5. **Fase 17 (docking)** + **Fase 21 (compliance giurisdizione)** in
   parallelo — 21 è bloccante per il volo reale, deve partire **subito
   dopo seed close**.
6. **Fase 18 (dispatch)** richiede 12 + 13.E + 17.
7. **Fase 19 (intervento attivo)** richiede 21 sbloccata + 22 in piedi.
8. **Fase 20 (autorità locali)** prima di 19 in produzione.
9. **Fase 22 (sicurezza)** + **Fase 23 (etica)** trasversali, sempre on.
10. **Fase 24 (resilienza)** prima di andare oltre la città pilota.
11. **Fase 25 (ops)** richiesta per pilota.
12. **Fase 26 (espansione)** ultimo blocco.

## Caveat sul piano 7-26

### Pre-seed (Fasi 7-10) — founder + AI

- **Effort realistico**: 4-6 mesi di lavoro intenso founder + Claude
  Code + Codex per arrivare a seed.
- **Bloccante reale**: capacità di chiudere capitale. Il software è
  veloce, l'outreach investitori no. Iniziare 9.A (lista investitori)
  in parallelo a 7 fin dal giorno 1.
- **Rischio principale**: founder burnout. Solo + AI è efficiente ma
  isolante. Trovare 1-2 advisor presto (Fase 9.C) anche solo per
  sanity check.

### Post-seed (Fasi 11-26) — team + capitale + regolatorio

- **Effort realistico**: 5-10 anni con team da 15-30 persone (ingegneria,
  ML, hardware, legale, ops) per coprire tutte le 16 fasi su 2
  giurisdizioni. Le Fasi 0-10 sono ~10% del lavoro totale.
- **Blocco più duro NON tecnico**: Fase 21 (regolatorio). Rwanda RCAA
  e Dubai DCAA sono **più rapide** di EASA, ma comunque mesi di
  procedure. Va affrontata in parallelo all'ingegneria, **non dopo**.
- **Blocco secondo più duro**: Fase 23 (accettazione locale). Errare
  un'esercitazione pubblica in Kigali o Dubai uccide il prodotto per
  anni. Investire seriamente in community engagement.
- **Capitale**: hardware (droni + docking) + R&D ML + legale +
  assicurazioni richiedono seed serio (1-3M EUR per la prima coppia
  di piloti); Series A 5-15M per scale su entrambe le giurisdizioni.
- **Hardware lead time**: 3-6 mesi tipici per quantità (droni custom
  + docking station prototype). Ordinare appena chiuso il seed.
- **Ordine di esecuzione potrebbe cambiare** in base a feedback
  regolatorio, capitale disponibile, primo pilota concreto. Le Fasi
  11-26 sono **scheletro decisionale**, non specifica implementativa.

Queste 20 fasi totali (4 pre-seed + 16 post-seed) sono **piano vivente**:
ogni fase, prima di partire, va espansa allo stesso livello di dettaglio
delle Fasi 0-6 (file specifici, contratti API, test, gate di accettazione).
Aspettarsi che la roadmap cambi dopo seed close (feedback investitori),
dopo primo pilota (feedback regolatorio Rwanda/Dubai), e dopo prima
trazione utenti (feedback prodotto).

## Definition of Done dell'intero piano

A **fine Phase 6**, lo stato consegnato all'utente è:

### Funzionale
- SwarmOS controlla autonomamente fleet di droni reali (almeno un
  vendor da Phase 5: MAVLink/PX4 oppure DJI) e simulati (sempre).
- Operatore via Console: vede territorio, anomalie, missioni in real
  time; invia 8 azioni; vede stato comando; non vede mai dati
  inventati.
- Multi-site: una istanza SwarmOS gestisce più siti simultaneamente.
- Mode FSM: rest/patrol/verification/escalation/maintenance funzionante
  end-to-end, deciso server-side.
- Persistence: ogni telemetry/event/mission/anomaly/command
  persistente; storico interrogabile.

### Sicurezza
- 360° threat coverage (S1–S68 implementati).
- Pen-test esterno passato.
- SAST (Bandit/Semgrep/CodeQL/ESLint-security) + DAST (ZAP) + SBOM +
  signing tutti attivi.
- Auth + RBAC + MFA per ruoli alti.
- Audit trail completo + integrity protection.
- Threat model + IR runbook documentati.

### Operatività
- Deployment riproducibile (Docker compose-prod o k8s/Helm).
- Monitoring + alerting attivi (Prometheus + Grafana + Loki).
- Backup automatico + restore test mensile.
- Runbook per: deploy, rolling restart, emergency stop, DR.
- SLO/SLI definiti e monitorati (latency p95, error rate, uptime).
- Performance: target Phase 6.F rispettati.

### Documentazione
- Architettura (C4 + ADR).
- API (OpenAPI + WS contract).
- Manuale operatore + training.
- Runbook ops + DR + migrations.
- Security (threat model + IR + disclosure).
- Compliance (GDPR + drone reg reference).

### Conformità & supporto
- Disclosure policy attiva + bug bounty / responsible disclosure.
- GDPR data flow documentato + export/delete tooling.
- Drone reg reference (responsabilità operativa esplicitata).
- Onboarding/offboarding operator documentato.

### Reliability
- Test coverage: backend ≥ 80%, frontend critical ≥ 70%.
- Integration e2e + load + chaos tests in CI.
- RTO 1 h, RPO 5 min documentati + testati.

**Quando tutto questo è verificato e committato, il piano è completo e
SwarmOS è pronto a gestire sciami di droni in condizioni reali.**

## 360° Security model

L'utente ha richiesto cybersecurity **a 360 gradi**: non solo difesa
contro supply-chain attacks (TanStack-class), ma copertura completa delle
classi di rischio note per un sistema che orchestra droni reali. Non vanno
aperte vulnerabilità.

Threat categories considerate, con strategia di copertura:

### A. Web/API application (OWASP Top 10 + API Security Top 10)
- **A01 Broken Access Control** → IDOR check per `site_id` + RBAC (Phase 6);
  endpoint mai serve dati di altri site
- **A02 Cryptographic Failures** → TLS ovunque, AES at rest per DB
  (Phase 4+6), no algoritmi deboli, RNG da `secrets` modulo Python
- **A03 Injection** → Pydantic strict + parametrized SQLAlchemy + no
  shell exec (Phase 0+1+4)
- **A04 Insecure Design** → threat model documentato in
  `docs/security/threat-model.md` (Phase 0), policy server-side (Phase 6)
- **A05 Security Misconfiguration** → CSP/headers/CORS strict (Phase 0),
  container hardening (Phase 0), no default credentials (Phase 4+6)
- **A06 Vulnerable Components** → Dependabot + audit + SBOM (Phase 0+6)
- **A07 Auth Failures** → JWT/OIDC + key rotation + revocation +
  password policy se mai user/pass (Phase 6)
- **A08 Software/Data Integrity** → sigstore/cosign signing + Subresource
  Integrity + audit log hash chain (Phase 0+4+6)
- **A09 Logging/Monitoring Failures** → structlog + correlation IDs +
  centralized + integrity (Phase 1+4)
- **A10 SSRF** → outbound allowlist scheme + host (Phase 5)
- **API-specific**: rate limit per IP + per operator, body size limit,
  request timeout, slow-client (Slowloris) protection (Phase 0+1)

### B. Supply chain (TanStack-class e oltre)
- pnpm `ignore-scripts=true` (Phase 0)
- GitHub Actions SHA-pinned, `permissions:` least-privilege (Phase 0)
- Docker digest-pinned (Phase 0)
- pnpm + pip audit attivi in CI (Phase 0)
- Lockfile committato (`pnpm-lock.yaml` e `uv.lock` in Phase 0)
- Dependabot weekly raggruppato (Phase 0)
- Dependency-review workflow su PR (Phase 0)
- SBOM CycloneDX in release (Phase 6)
- Sigstore/cosign signing artefatti rilasciati (Phase 6)
- Provenance check per pacchetti vendor (Phase 5)

### C. Identity / Auth / Session
- Operator handle validato regex in Phase 1 (transitional)
- JWT/OIDC + RBAC (`viewer`/`operator`/`commander`) in Phase 6
- Short-lived access tokens + refresh + revocation list (Phase 6)
- Cookie flags `HttpOnly` `Secure` `SameSite=Strict` (Phase 6)
- Idle timeout + absolute session timeout (Phase 6)
- MFA per ruoli `commander` (Phase 6)

### D. Secrets / credentials
- `.env` gitignored (già), `.env.example` template (già)
- Pre-commit hooks `detect-secrets` o `gitleaks` (Phase 0)
- CI `gitleaks` action (Phase 0)
- No hard-code, env-only fino a Phase 6
- Vault (HashiCorp / Doppler / 1Password) in prod (Phase 6)
- Key rotation procedure documentata (Phase 6)

### E. Network / Transport
- TLS ovunque in prod (Phase 6)
- HSTS + cert rotation (Phase 6)
- mTLS bus (Redis TLS o NATS mutual cert) (Phase 4+5)
- Firewall egress allowlist (Phase 6)
- WS origin check (Phase 0) + WS auth token (Phase 6)
- Backend non esposto direttamente a Internet, solo via reverse proxy
  con TLS termination (Phase 6 doc / infra)

### F. Container / OS / Infrastructure
- Non-root user nei container app (Phase 0)
- Read-only FS dove possibile (Phase 0)
- Capability drops (`cap_drop: ALL`) (Phase 0)
- AppArmor/Seccomp profile in prod (Phase 6)
- Image scanning in CI (trivy o grype) (Phase 0)
- Patch management via Dependabot incl. docker (Phase 0)
- Resource limits (CPU/memory) in compose + k8s (Phase 6)

### G. Data protection / Privacy
- TLS in transito + AES-256 a riposo per DB (Phase 4+6)
- Camera/video retention policy + access control (Phase 4)
- PII minimization e redaction nei log (Phase 4+6)
- GDPR-style data export / delete su richiesta (Phase 6, doc)
- Audit log append-only + hash chain o constraint DB (Phase 4)

### H. Drone / IoT specific
- Geofence enforcement server-side su ogni MissionTask (Phase 6)
- Battery / link / weather thresholds enforced server-side (Phase 6)
- Stream URL allowlist scheme `rtsps://` `https://` only (Phase 5)
- Adapter auth via vault keys (Phase 5+6)
- Drone link encryption (vendor-dependent, documentato) (Phase 5)
- Emergency stop / RTL automatico su link loss (Phase 5)
- Sensor spoofing mitigation: confidence-bounded reporting +
  multi-source cross-check (Phase 1+3)
- Rate-limit telemetry inbound (sanity Hz cap) (Phase 5)
- Webhook signature verification se vendor lo offre (Phase 5)
- Mission DSL tipizzato (no shell exec, no string templating) (già)

### I. Logging / Monitoring / Detection
- structlog JSON + correlation IDs (Phase 1)
- Audit eventi separati da application logs (Phase 4)
- Centralized logging (Loki/ELK) (Phase 6)
- Alerting su pattern sospetti (auth failures, rate-limit hits) (Phase 6)
- Time sync NTP requirement per audit (Phase 4)

### J. Process / Operations
- `SECURITY.md` con disclosure policy (Phase 0)
- Threat model + STRIDE per service (Phase 0)
- Incident response runbook (Phase 0)
- Pen-test esterno pre-go-live (Phase 6)
- Bug bounty / responsible disclosure program (Phase 6)
- Onboarding/offboarding operator procedure (Phase 6)

### K. SAST / Code quality / Tests
- Bandit (Python SAST) in CI (Phase 0)
- Semgrep rules in CI (Phase 0)
- ESLint security plugin (Phase 0)
- Fuzz tests su parser telemetry / mission DSL (Phase 0+1)
- Coverage minima 70% su `swarm_os/` (Phase 1+)
- CodeQL su GitHub (Phase 0, free per public)

### L. Frontend specific
- React (safe by default contro XSS) + no `dangerouslySetInnerHTML`
- CSP nonce (Phase 6) — script-src no-unsafe-inline
- SRI per qualunque risorsa esterna (Phase 0, ma oggi nessuna esterna)
- X-Frame-Options DENY (Phase 0) — anti-clickjacking
- Referrer-Policy `no-referrer` (Phase 0)
- Permissions-Policy `geolocation=()` (Phase 0)
- No localStorage per token; HttpOnly cookie quando auth (Phase 6)

### M. Backend specific
- Pydantic v2 strict mode per tutti i body (Phase 1)
- Request size limit 1 MB default (Phase 0)
- Request timeout 30 s (Phase 0)
- Connection pool DB con `pool_pre_ping` (Phase 4)
- Open-redirect protection: `redirect()` accetta solo path interni
  (Phase 2)
- Error responses JSON strutturati, **mai** stack traces in prod
  (Phase 0)

## Security hardening track (numerazione persistente cross-fase)

Tabella ampliata per coprire le 13 categorie sopra. Le voci marcate
**[P0]** sono in Phase 0. Le altre sono in fase relativa indicata.

| #    | Cambiamento | Fase | Categ. | Effetto |
|------|-------------|------|--------|---------|
| S1   | `frontend/.pnpmrc` con `ignore-scripts=true` + `engine-strict=true` + `audit-level=high` + `fund=false` + `strict-peer-dependencies=true` | P0 | B | No postinstall arbitrario; pin Node major |
| S2   | `.nvmrc` Node 24 LTS line | P0 | B | Runtime supportato e riproducibile |
| S3   | Install frontend via `corepack pnpm install --frozen-lockfile --ignore-scripts`; aggiungere `pnpm audit --audit-level=high` step | P0 | B | Audit attivo in CI |
| S4   | SHA-pin (40 char) di tutte le GitHub Actions | P0 | B | No takeover via tag re-push |
| S5   | `permissions: contents: read` esplicito per workflow | P0 | B | GITHUB_TOKEN least-privilege |
| S6   | `.github/dependabot.yml` weekly (frontend JavaScript, pip, docker, actions) | P0 | B | Alert + patch auto |
| S7   | Docker digest-pin `@sha256:…` (timescale + redis) | P0 | B,F | No silent base image update |
| S8   | CORS allowlist env-driven + WS Origin check + close 1008 | P0 | A,E | No `*`, no WS cross-origin |
| S9   | Security headers middleware: CSP, X-CTO nosniff, X-Frame-Options DENY, Referrer-Policy no-referrer, Permissions-Policy geolocation=(), HSTS in prod | P0 | A,L | Hardening HTTP |
| S10  | `uv.lock` + workflow `uv sync --frozen` | P0 | B | Build Python deterministico |
| S11  | `SECURITY.md` con disclosure policy + scope + contatto + Private Vulnerability Reporting GitHub | P0 | J | Canale vuln strutturato |
| S12  | `.github/workflows/dependency-review.yml` per PR | P0 | B | Blocca PR con CVE high |
| S13  | Bandit (Python SAST) in CI | P0 | K | SAST automatico |
| S14  | Semgrep rules in CI (`p/python`, `p/typescript`, `p/owasp-top-ten`) | P0 | K | SAST policy-as-code |
| S15  | ESLint security plugin (`eslint-plugin-security`) | P0 | K,L | Frontend SAST |
| S16  | Pre-commit hooks con `gitleaks` + `detect-secrets` | P0 | D | No secrets nel repo |
| S17  | `.github/workflows/secret-scanning.yml` con gitleaks-action | P0 | D | Secrets in CI |
| S18  | CodeQL workflow (Python + JS) | P0 | K | SAST profondo |
| S19  | Trivy o Grype image scan in CI | P0 | F | Container scan |
| S20  | Container hardening compose: `user: 1000:1000`, `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]` per backend; idem dove sensato per postgres/redis | P0 | F | Container least privilege |
| S21  | Resource limits in compose (mem_limit, cpus) | P0 | F | DoS containment |
| S22  | Request size limit 1 MB (`MaxRequestBodyMiddleware`) | P0 | A,M | Anti-flood |
| S23  | Request timeout 30 s middleware | P0 | A,M | Anti-Slowloris |
| S24  | Error handler globale: JSON strutturato, no stack traces in prod | P0 | A,M | No info leak |
| S25  | Open-redirect guard su `redirect()` Next.js (accetta solo path interni) | P0/P2 | M | OWASP A01 |
| S26  | `docs/security/threat-model.md` con STRIDE per service | P0 | J | Threat model formale |
| S27  | `docs/security/incident-response.md` runbook | P0 | J | Procedura IR |
| S28  | Fuzz tests `tests/fuzz/test_messages_fuzz.py` per Pydantic models | P0 | K | Robustness parser |
| S29  | `make audit` target: `pip-audit` + `pnpm audit --audit-level=high` + `bandit` + `semgrep` | P0 | B,K | Single command audit |
| S30  | Operator handle regex `^op-[a-z0-9]{4,32}$` + enum chiuso `rejected_reason` | P1 | A,C | No echo input |
| S31  | Rate-limit middleware token-bucket 30 req/min/IP su `/actions/*` | P1 | A | Anti-flood |
| S32  | structlog JSON + correlation IDs + audit logger separato | P1 | I | Audit-grade logging |
| S33  | Pydantic v2 `model_config = ConfigDict(extra="forbid", strict=True)` per tutti i body | P1 | A,M | Strict parsing |
| S34  | Open-redirect protection nel routing console | P2 | M | OWASP A01 |
| S35  | Schema Timescale con audit log append-only + hash chain | P4 | A,G,I | Audit integrity |
| S36  | DB credentials env, `sslmode=require` fuori dev | P4 | A,E | DB hardening |
| S37  | SQL injection test suite (filtri storici) | P4 | A | Difesa injection |
| S38  | PII redaction nei log + retention policy | P4 | G | Privacy |
| S39  | Backup encryption + restore test | P4 | G | DR |
| S40  | NTP / time-sync requirement documentato | P4 | I | Audit logs trustworthy |
| S41  | Stream URL allowlist scheme `rtsps://` `https://` only | P5 | H | Anti-SSRF/RCE |
| S42  | Telemetry rate-limit inbound (Hz cap sanity) | P5 | H | Vendor sanity |
| S43  | Sigstore / package provenance check per dipendenze vendor | P5 | B,H | Supply chain vendor |
| S44  | Webhook signature verification se vendor lo offre | P5 | H | Source authenticity |
| S45  | Adapter auth: vendor API keys via vault | P5 | D,H | No secrets at rest in env |
| S46  | Drone link encryption (vendor-dependent) — documentato | P5 | E,H | Trasporto drone cifrato |
| S47  | Emergency RTL automatico su link loss | P5 | H | Safety |
| S48  | mTLS bus / Redis TLS in prod | P5/P6 | E | Trasporto interno cifrato |
| S49  | JWT/OIDC + RBAC (`viewer`/`operator`/`commander`) + revocation list | P6 | C | Authn/Authz |
| S50  | Short-lived access tokens + refresh + key rotation | P6 | C | Token hygiene |
| S51  | Cookie `HttpOnly` `Secure` `SameSite=Strict` | P6 | C,L | Session hardening |
| S52  | MFA per `commander` role | P6 | C | High-priv hardening |
| S53  | IDOR check per `site_id` su ogni endpoint | P6 | A | OWASP A01 |
| S54  | Geofence enforcement runtime su ogni MissionTask | P6 | H | Safety policy |
| S55  | Weather lock server-side via provider reale | P6 | H | Safety policy |
| S56  | SBOM CycloneDX in CI (backend + frontend) | P6 | B | Inventario rilasciato |
| S57  | `cosign` / sigstore signing degli artefatti | P6 | B | Supply chain in uscita |
| S58  | Secrets vault integration prod (HashiCorp / Doppler) | P6 | D | No secrets at rest in env |
| S59  | Centralized logging (Loki/ELK) con integrity | P6 | I | SIEM-ready |
| S60  | Alerting su auth failures, rate-limit hits, anomaly patterns | P6 | I | Detection |
| S61  | TLS terminator reverse proxy con HSTS + cert rotation | P6 | E,L | Trasporto pubblico |
| S62  | Firewall egress allowlist | P6 | E | Network segment |
| S63  | AppArmor/Seccomp profile in prod | P6 | F | OS hardening |
| S64  | Pen-test esterno pre-go-live | P6 | J | Validazione |
| S65  | Bug bounty / responsible disclosure program | P6 | J | Continuous external review |
| S66  | GDPR-style data export/delete documentato | P6 | G | Privacy compliance |
| S67  | CSP nonce con script-src no-unsafe-inline | P6 | L | XSS hardening avanzato |
| S68  | Subresource Integrity per risorse esterne (se aggiunte) | P0/P6 | L | Supply chain frontend |

## Portabilità del piano tra sessioni

Questo file vive in `/root/.claude/plans/…` ed è effimero (cambia per
sessione). Per riusarlo in ogni sessione futura senza dover ripetere il
contesto, lo rendiamo **persistente nel repo** e **auto-disponibile**.

### Meccanismo
1. **Committare il piano nel repo** come `docs/plan/swarmos-roadmap.md`
   (single source of truth). Da quel momento ogni sessione può leggerlo
   con `Read /home/user/swarm/docs/plan/swarmos-roadmap.md`.
2. **Creare `CLAUDE.md` al root del repo** che:
   - referenzia `docs/plan/swarmos-roadmap.md` come "piano di sviluppo
     ufficiale";
   - elenca la terminologia (SWARM / SwarmOS / Console / ...);
   - elenca le regole hard (no rosso, no fake video, no chart lib,
     confidence-bound voice, 360° security);
   - indica lo stato corrente (es. "siamo a fine Phase 0; prossima =
     Phase 1");
   - punta a `SECURITY.md` e ai runbook in `docs/`.
   Claude Code legge automaticamente `CLAUDE.md` dal root del repo
   all'avvio di ogni nuova sessione, quindi il contesto si carica
   da solo.
3. **Aggiornare CLAUDE.md a fine di ogni fase** con la riga "stato
   corrente" — diventa il bookmark del piano.
4. **Riferimenti dall'utente nelle nuove sessioni**: per essere espliciti,
   in una nuova sessione si può aprire con
   `@docs/plan/swarmos-roadmap.md continuiamo da Phase X` e Claude
   carica il piano + lo stato.

### File aggiunti per portabilità (in Phase 0)
- `docs/plan/swarmos-roadmap.md` — copia di questo file
- `CLAUDE.md` — quick context loader (stato + terminologia +
  regole hard + link al piano)
- `docs/CONVENTIONS.md` — convenzioni codice/commit/branch
  (estratto sintetico)
- `docs/STATUS.md` — file vivo aggiornato a fine di ogni fase con:
  fase corrente, prossima fase, decisioni aperte, link a PR

### Come usarlo concretamente
- **Sessione futura per Phase 1**:
  Apri Claude Code nel repo; il sistema legge `CLAUDE.md`; tu scrivi:
  > "iniziamo Phase 1 dal piano (docs/plan/swarmos-roadmap.md)"

  Claude trova il file, identifica la sezione Phase 1, esegue.

- **Sessione futura per riprendere a metà fase**:
  Aggiorna `docs/STATUS.md` con quello che resta da fare
  (lo farò io a fine fase). Apri sessione:
  > "vedi docs/STATUS.md e continua"

- **Cambiare scope / aggiungere requisiti**:
  Modifica direttamente `docs/plan/swarmos-roadmap.md` con Edit
  in-session, oppure chiedimi di farlo. Il file è in repo, quindi
  è versionato in git.

## Sequenza implementativa (esecuzione una alla volta)

L'utente eseguirà le fasi una alla volta. **Questa sessione = Phase 0**.

| Sessione    | Fase                       | Stato          |
|-------------|----------------------------|----------------|
| Questa      | Phase 0 — repo discipline + security baseline + shared types | **PROSSIMA** |
| Successiva  | Phase 1 — SwarmOS Sim Kernel + endpoints + actions          | Pianificata    |
| Successiva  | Phase 2 — Console Operating Shell + routing + components    | Pianificata    |
| Successiva  | Phase 3 — Truth Layer (no DERIVED)                          | Pianificata    |
| Successiva  | Phase 4 — Persistence (Timescale + Alembic + audit)         | Pianificata    |
| Successiva  | Phase 5 — Real Adapter (MAVLink o DJI, da decidere)         | Pianificata    |
| Successiva  | Phase 6 — Production OS (policy, geofence, auth, SBOM)      | Pianificata    |

## Funzioni / file esistenti da riusare

- `core/swarm_core/geometry.py`: `haversine_m`, `point_in_polygon`,
  `tile_polygon`, `bbox`, `midpoint` — base per `sectors.py`.
- `core/swarm_core/missions.py`: `MissionKind`, `PATROL()`, `VERIFY()`,
  `RTL_DOCK()` — backing per `MissionView`.
- `core/swarm_core/allocator.py`: `select_winner()` — lasciare in pace.
- `orchestrator/swarm_orchestrator/bus.py`: `InMemoryBus`/`RedisBus` —
  `swarm_os` si abbona ai topic `swarm:*`.
- `backend/app/bus_consumer.py`: pattern bus → state → WS — estendere.
- `frontend/components/Map.tsx`: `MapView` (MapLibre Langhe) — esteso con
  `<SectorLayer/>` e `<RouteLayer/>` come children/source-layers.
- `frontend/components/{AnomalyCard,DockCard,FleetGrid,EventFeed,
  UnitDetail,AwarenessScore,StatusPill,Eyebrow}` — wrappati nei route
  group nuovi.
- `frontend/lib/tokens.ts`: `agentStateToSwarm`, palette già pronta.

## Anti-overreach trasversale (PDF §10)

- Non lasciare campi derivati dal client senza flag `derived: true`.
- Non turn operator actions in manual drone control wording.
- Non rosso, mai (escalation = amber).
- Non video stock o placeholder mascherato.
- Non libraries chart/modal/toast/snackbar.
- Non glassmorphism / backdrop-blur / linear-gradient fuori allowlist.
- Non skippare la sicurezza per arrivare prima ad una feature.

## Verifica end-to-end (Definition of Done a Phase 6)

```bash
make setup
make lint && make test && make audit       # tutti verdi
make demo                                   # sim + backend + frontend
# Phase 2+
grep -rE "Intruder|Manual|fly drone|alarm|red[- ]?(alert|state)" \
  frontend/components frontend/app core/swarm_core swarm_os    # 0
grep -rE "box-shadow|drop-shadow|backdrop-blur|linear-gradient" \
  frontend/components frontend/styles frontend/app             # 0
# Routes
open http://localhost:3000/                 # → /(console)/
open http://localhost:3000/\(console\)/{verify,system}
open http://localhost:3000/m
# Action contract
curl -X POST -H "X-Operator-Id: op-davide" -H "content-type: application/json" \
  -d '{"target":"sector:north-a"}' localhost:8765/actions/verify     # 202
# Security smoke
curl -I -H "Origin: https://evil.example" localhost:8765/health      # no ACAO evil
websocat -H "Origin: https://evil.example" ws://localhost:8765/ws/telemetry # 1008
grep -E "@sha256:" docker-compose.yml                                # 2 match
grep -E 'uses: actions/.+@[0-9a-f]{40}' .github/workflows/*.yml      # tutte
# Phase 4+
psql -c "select count(*) from events where kind='operator'"          # > 0
# Phase 6
jwt-decode $TOKEN | jq .roles                                        # operator|commander|viewer
```

## Note di esecuzione

- Branch di lavoro: `claude/swarm-security-implementation-S8MRv` (come
  istruzioni). Per Phase 0 committo qui.
- Non aprire PR senza richiesta esplicita.
- Ogni fase = un commit chiaro (o più piccoli sequenziali) con
  scope-line nel messaggio: `phase-0: ...`, `phase-1: ...`.
- Se durante Phase 1 emerge ambiguità su `swarm_os.coordinator` vs
  `orchestrator/swarm_orchestrator/`, già scelto: `coordinator.py`
  (lo abbiamo deciso in fase di design).
- Al termine di ogni fase: `make lint && make test && make audit`
  prima di committare.
