# SwarmOS — Piano completo Phase 0 → Phase 6 (PDF roadmap)

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
