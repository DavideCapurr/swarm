# SwarmOS — Piano completo Phase 0 → Phase 27

Phase 0–6 = PDF roadmap originale (fondazione tecnica, in larga parte
fatta).
Phase 7–11 = **pre-seed sprint** (founder solo + Claude Code + Codex
fino a primo capitale). Include test reale su terreno privato del
founder prima del pitch.
Phase 12–27 = **post-seed execution** (visione finale dopo team +
capitale + giurisdizione target attiva).

Giurisdizioni (decisione utente 2026-05-18, aggiornata):
1. **Terreno privato del founder in Italia** per il bench reale
   pre-pitch (categoria ENAC Open su proprietà privata, niente SORA
   necessario per VLOS sotto 25 kg, "freghiamoci di regulations a
   livello prodotto").
2. **Rwanda + Dubai (UAE)** post-seed per il deploy commerciale.
3. UE/USA solo in Phase 27 dopo trazione.

Casi MVP: incendio + protezione case + bene pubblico (defibrillatore,
ricerca dispersi, supporto Protezione Civile).

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

## Phase 7 → Phase 22 — Pre-seed sprint (solo + Claude Code + Codex)

**Contesto reale (decisione utente 2026-05-18, aggiornata)**: il "team"
oggi è **founder solo + Claude Code + Codex**. Niente assunti, niente
investitori, niente partner.

**Ordine temporale richiesto dall'utente**: prima TUTTO il software in
simulazione (Phase 7-18, founder + AI possono farlo senza spese), poi
SOLO ALLA FINE l'acquisto hardware e il bench reale sul terreno
privato del founder in Italia (Phase 19), poi pitch con video reali
(Phase 20), outreach (Phase 21), seed close (Phase 22).

Vantaggi di questo ordine:
- Software è il pezzo a costo zero (solo tempo founder + AI tools).
- Hardware costa, non lo si compra finché software non è maturo.
- Quando arriva hardware in Phase 19, è solo integrazione +
  validazione finale, non build.
- Pitch in Phase 20 mostra software completo + video reali + drone
  vero che ha già volato → narrativa molto più forte di "abbiamo
  fatto MVP basico, fidatevi del piano".

**Obiettivo pre-seed**: arrivare a seed round chiuso (o term sheet
firmato) entro 12-18 mesi. Pre-seed più lungo rispetto alla versione
precedente del piano, ma con prodotto molto più maturo all'arrivo
del pitch.

**Strategia geografica pre-seed**:
1. **Phase 19** (hardware bench) sul **terreno privato del founder in
   Italia** — categoria ENAC Open su proprietà privata recintata,
   VLOS, sotto 25 kg, sotto 120m. Niente SORA, niente autorizzazione
   speciale, niente comune, niente VVF: solo proprietà privata +
   consenso founder + assicurazione drone professionale
   (€300-800/anno standard). "Freghiamoci di regulations" = nessuna
   procedura pubblica, solo invariante di sicurezza basico.
2. **Phase 23+** (post-seed) sul terreno **Rwanda + Dubai** per il
   deploy commerciale, con tutte le autorizzazioni del caso.

**Giurisdizioni commerciali (post-seed)**: Rwanda + Dubai (UAE).
Rwanda per "bene pubblico" (Zipline ha già aperto la strada), Dubai
per "premium / protezione case + incendio sterpaglie".

**Principio guida nuovo** (sostituisce "SwarmOS decides. Console
supervises." una volta entrati in Fase 7): **"SwarmOS decide ed
esegue. L'umano può intervenire se necessario."** Human-on-the-loop,
non in-the-loop.

### Mappa Phase 7-22 in sintesi

| Phase | Categoria | Cosa | Durata stimata |
|---|---|---|---|
| 7 | sw sim | MVP base + 3 scenari | 3-5 sett |
| 8 | sw sim | Autonomy engine completo | 3-4 sett |
| 9 | sw sim | Federazione sciame-di-sciami | 4-6 sett |
| 10 | sw sim | Intelligenza ML/AI (pretrained + custom) | 6-8 sett |
| 11 | sw sim | Detection multimodale (mock sensori) | 2-3 sett |
| 12 | sw | App cittadino (working, backend mock) | 4-6 sett |
| 13 | sw sim | Dispatch city-scale (algoritmo completo) | 3-4 sett |
| 14 | sw sim | Intervento attivo logica (senza payload reale) | 3-4 sett |
| 15 | sw | Multi-tenant + business + mock payments | 2-3 sett |
| 16 | sw | Decision log firmato + cyber sw | 2-3 sett |
| 17 | sw | Resilience sw (failover, degraded mode) | 2 sett |
| 18 | sw | Privacy mask + explainability + bias check | 2-3 sett |
| 19 | hw | Bench su terreno privato founder (Italia) | 4-10 sett |
| 20 | sw + media | Pitch materials con video reali | 2-4 sett |
| 21 | outreach | Outreach pre-seed investitori | 4-12 sett |
| 22 | corporate | Seed close + team minimo | mesi 13-18 |

Totale pre-seed: ~13-18 mesi solo + AI.

## Phase 7 — Software MVP base in simulazione (3-5 settimane)

**Obiettivo**: software end-to-end girabile in sim sui 3 scenari MVP,
fondazione su cui costruire tutto il resto delle fasi software.

- **7.A** Tre scenari simulati in `sim/scenarios/`, costruiti per
  essere **replicabili sul terreno del founder** in Phase 19:
  - `wildfire_owner_land.yaml`: incendio sterpaglie su area
    rettangolare ~1-3 ettari (dimensione terreno founder),
    detection CV + termocamera, dispatch multi-drone autonomo,
    contenimento perimetrale.
  - `intrusion_owner_land.yaml`: intrusione su perimetro recintato,
    dispatch drone, ispezione, live feed.
  - `search_owner_land.yaml`: soggetto disperso su area, ricerca
    con termocamera + CV.
- **7.B** `swarm_os/autonomy.py` versione baseline deterministica
  funzionante sui 3 scenari (versione production in Phase 8).
- **7.C** Console esistente come "osservatorio" con eyebrow `AUTO`
  per ogni decisione autonoma.
- **7.D** Computer vision baseline (pretrained, no fine-tuning):
  - Fuoco: **FLAME** + **D-Fire** dataset, YOLOv8 pretrained.
  - Persona aerial: **VisDrone** pretrained.
  - Inferenza live nello scenario.
- **7.E** "Make demo" target: `make demo-wildfire-sim`,
  `make demo-intrusion-sim`, `make demo-search-sim`. Replicabili in
  1 comando.

**Gate**: i 3 scenari girano end-to-end in sim, ogni decisione
autonoma è loggata, metriche baseline raccolte.

## Phase 8 — Autonomy engine production (sim) (3-4 settimane)

**Obiettivo**: portare l'autonomy.py da baseline a production-grade.
Tutto ancora in sim — l'hardware reale arriva in Phase 19.

- **8.A** Inversione default in Console: diventa osservatorio. Le 4
  intent attuali (`verify / hold-patrol / dismiss / return`) restano
  come pulsanti di override, non sono più il flusso primario.
- **8.B** `swarm_os/autonomy.py` completo: decisioni `VERIFY |
  DISMISS | ESCALATE | WAIT` su ogni anomalia. Soglie deterministiche
  configurabili per scenario.
- **8.B-bis** Modalità ombra obbligatoria per ogni nuovo decisore
  prima del go-live: decide + logga + confronta con decisione umana.
- **8.C** Hook intervento umano completi:
  - Override soft (annulla/modifica decisione autonoma in corso).
  - Policy nudge a scadenza (alza/abbassa soglie temporaneamente).
  - Kill switch (atterra tutti i droni in sim; unica eccezione alla
    regola "no red" del design system).
- **8.D** Eyebrow `AUTO` / `OVERRIDE` ovunque nella Console + timeline.

**Gate**: 100+ esecuzioni dei 3 scenari in sim con autonomy completo,
< 5% divergenza da decisione umana baseline.

## Phase 9 — Federazione "sciame di sciami" (sim) (4-6 settimane)

**Obiettivo**: architettura completa multi-cella, non più singleton.
Tutto in sim.

- **9.A** Nuova entità `Swarm` in `core/swarm_core/messages.py` (id,
  goal corrente, droni assegnati, area di responsabilità, salute).
- **9.B** `SwarmCellCoordinator` per ogni sciame al posto del
  singleton `SwarmCoordinator`. Lock per `swarm_id`.
- **9.C** Bus Redis namespaced per cella: `swarm:cell:<id>:telemetry`,
  `swarm:cell:<id>:events`.
- **9.D** `swarm_os/meta_coordinator.py`: assegna obiettivi alle celle
  (non missioni atomiche). Bilanciamento carico, copertura, riserva.
- **9.E** Protocollo mesh inter-sciame: topic `swarm:mesh:offer`,
  `swarm:mesh:request`, `swarm:mesh:commit`. Algoritmo contract-net.
- **9.F** Fusione/scissione dinamica sciami.
- **9.G** Backpressure: cella può rifiutare assegnazioni in emergenza.
- **9.H** Multi-site simultaneo in una sola istanza (sostituisce
  Phase 6.B one-site-at-a-time).

**Gate**: chaos test in sim (kill random di celle) → sistema converge
senza intervento; latenza inter-cell mesh p95 < 200ms in sim.

## Phase 10 — Intelligenza ML/AI (sim + dati propri) (6-8 settimane)

**Obiettivo**: sostituire le regole deterministiche con modelli
appresi. Shield deterministico (Fase 6.A) resta intatto sotto.

- **10.A** Computer vision custom training: fine-tuning YOLOv8 / RT-DETR
  su dataset pubblici + dataset sintetici generati nella sim.
- **10.B** Tracking soggetti (ByteTrack / BoT-SORT) per frame-su-frame.
- **10.C** Classificatore disposizione anomalie (gradient boosting,
  leggero, interpretabile, calibrato). Sostituisce le soglie di Fase 8.B.
- **10.D** Pipeline retraining (anche se senza override umani reali,
  preparare l'infrastruttura per quando arriveranno post-seed).
- **10.E** Reinforcement learning per pattugliamento (PPO o bandit
  contestuali) addestrato nella sim.
- **10.F** Multi-agent RL per allocazione tra sciami (in sim).
- **10.G** Forecast: degrado batterie, meteo nowcasting, picchi
  anomalie. Addestrati su dati sim.
- **10.H** LLM per briefing turno + spiegazione decisioni +
  configurazione assistita. **MAI** safety runtime.
- **10.I** Pipeline MLOps: model registry, A/B shadow deployment,
  drift detection. Codice + infra pronta.
- **10.J** Feature store leggero su TimescaleDB esistente.
- **10.K** Modulo `swarm_os/intelligence/` con classifier, scoring,
  calibration, explainability.

**Gate**: ogni modello ML ha passato shadow mode in sim + audit di
calibrazione + SHAP/attention salvate nel decision log.

## Phase 11 — Detection multimodale (sim, mock sensori) (2-3 settimane)

**Obiettivo**: software che fonde input da molteplici sorgenti
sensoriali. Sensori reali post-seed; qui mock.

- **11.A** Integrazione mock sensori IoT: microfoni, qualità aria,
  fumo, vibrazioni (eventi sim, non hardware vero).
- **11.B** Detection audio software (modelli pretrained ShotSpotter-
  like su sample sim).
- **11.C** Fusione multi-sorgente (sensore + camera + segnalazione
  app utente).
- **11.D** Trigger automatico dispatching senza intervento umano.
- **11.E** Filtro falsi positivi multimodale.

**Gate**: tasso falsi positivi < 1% su dataset sim di 30 giorni.

## Phase 12 — App cittadino (software completo, backend mock) (4-6 settimane)

**Obiettivo**: app reale funzionante, con backend che parla con la sim.
Niente cloud production ancora — backend gira locale + tunnel.

- **12.A** App nativa iOS/Android via React Native o Expo.
  Localizzazioni: EN, IT (per founder testing), AR + KIN come stub
  per dopo.
- **12.B** Pulsante SOS one-tap con timer "annulla" + anti-misclick.
- **12.C** SOS silenzioso (movimento, password coercion, shake).
- **12.D** Geolocalizzazione opt-in.
- **12.E** Notifiche push: drone in arrivo, ETA, drone sul posto.
- **12.F** Video live dal drone all'utente (rassicurazione). In sim
  → finto stream sintetico; in Phase 19 → stream vero.
- **12.G** Comunicazione audio bidirezionale utente↔drone (TTS).
- **12.H** Storico personale interventi.
- **12.I** Profilo medico/contatti d'emergenza.
- **12.J** Sharing localizzazione con persone fidate durante emergenza.

**Gate**: app installabile e funzionante su iPhone + Android del
founder; SOS → evento sim → drone parte in < 2s.

## Phase 13 — Dispatch city-scale (sim) (3-4 settimane)

**Obiettivo**: algoritmo dispatch completo per scenario città grande.

- **13.A** Algoritmo "qual drone mandare" (distanza, batteria, tipo
  payload, meteo, traffico aereo).
- **13.B** Path planning 3D urbano (evita palazzi sim, alberi, linee).
- **13.C** ETA garantito 1-2 minuti come SLO.
- **13.D** Backup drone automatico se primo fallisce.
- **13.E** Dispatch multi-drone con ruoli specializzati.
- **13.F** Coda priorità (emergenza vitale > incendio > protezione
  case > ronda).
- **13.G** Pre-posizionamento predittivo (sposta droni dove
  probabilmente serviranno, da forecast 10.G).
- **13.H** Coordinamento traffico aereo locale simulato.

**Gate**: SLO ETA p95 < 120s su 1000+ dispatch sim; zero collision in
sim multi-drone.

## Phase 14 — Intervento attivo logica (sim, no payload) (3-4 settimane)

**Obiettivo**: tutta la logica di intervento attivo in sim. Payload
hardware reali in Phase 19 (limitato) + post-seed (completo).

### Incendio (priorità 1)
- **14.A** Logica detection precoce + targeting fonte calore (CV
  termico già in 10.A).
- **14.B** Logica sistema spegnimento mirato (sim: payload virtuale).
- **14.C** Logica coordinamento multi-drone per contenimento
  perimetrale (da Phase 9 federazione).
- **14.D** Logica evacuazione assistita (TTS multilingua).
- **14.E** Stop intervento se aria contaminata o pericolo esplosione
  (deterministico, parte dello shield 6.A).
- **14.F** Logica handoff strutturato ad autorità (interfaccia, no
  call reale).

### Protezione case/terreno (priorità 2)
- **14.G** Risposta a chiamata SOS da app del proprietario (da 12.B).
- **14.H** Risposta a sensori IoT mock (da 11.A).
- **14.I** Ispezione perimetrale on-demand.
- **14.J** Logica illuminazione perimetrale dissuasiva (sim: faro
  virtuale).
- **14.K** Logica live feed criptato proprietario.
- **14.L** Modalità "viaggio sicuro casa" (drone scorta opt-in).
- **14.M** Audio bidirezionale per dialogo proprietario↔persona.

### Bene pubblico (priorità 3)
- **14.N** Logica drone-defibrillatore (sim: payload virtuale).
- **14.O** Ricerca dispersi con termocamera + CV (sim su scenari
  sintetici).
- **14.P** Logica illuminazione zone pubbliche pericolose.
- **14.Q** Logica supporto Protezione Civile per eventi climatici.

### Fuori MVP
- **14.R** Sicurezza personale antiaggressione (faro/sirena/tracking).
  Logica non implementata; placeholder per quando si valuta
  post-seed.

**Gate**: tutti gli scenari MVP eseguibili in sim, decisioni autonome
loggate, payload virtuali "attivati" coerentemente.

## Phase 15 — Multi-tenant + business logic + mock payments (2-3 settimane)

**Obiettivo**: software pronto per multi-cliente, pagamenti mockati
(integrazione reale post-seed).

- **15.A** Multi-tenant: provider per nazione/città/quartiere/compound.
- **15.B** Piani abbonamento (free, base, premium, family) come schema
  software con prezzi configurabili per giurisdizione.
- **15.C** Integrazione billing mock (interfaccia Stripe + Flutterwave
  + MTN MoMo simulata; switch reale post-seed).
- **15.D** SLA per piano (tempo risposta garantito; gradient da
  premium a community).
- **15.E** Dashboard amministrazione city/government partner (mock
  data).
- **15.F** Interfaccia integrazione assicurazioni (mock).
- **15.G** KPI pubblici (trasparenza: tempi risposta, interventi,
  falsi positivi).
- **15.H** White-label code-side (theming, branding).

**Gate**: 3-5 tenant simulati attivi simultaneamente nella sim, ognuno
con proprio billing/SLA/branding mock.

## Phase 16 — Decision log firmato + cyber security software (2-3 settimane)

**Obiettivo**: tutta la sicurezza software-side. Sicurezza fisica
(anti-spoof GPS, anti-jam) in Phase 26 post-seed.

- **16.A** Decision log firmato (hash chain immutabile su `events`).
- **16.B** Explainability completa per ogni decisione autonoma
  (SHAP / feature attribution / regola applicata, salvata nel decision
  log) — estende 10.K.
- **16.C** Chain of custody video/audio software-side per uso
  giudiziale futuro.
- **16.D** Anti-hijacking comandi software (firma crittografica
  end-to-end del piano missione).
- **16.E** Penetration testing software (bandit + semgrep estesi).
- **16.F** SBOM completo + supply chain attestation per ogni dependency
  (estende Phase 6.E cosign).

**Gate**: hash chain verificabile su 30 giorni di sim; pen-test
software interno passato; SBOM clean.

## Phase 17 — Resilience software (failover, degraded) (2 settimane)

**Obiettivo**: il software gestisce situazioni avverse. Test reali di
failover regionale post-seed.

- **17.A** Failover regionale (codice + config; cross-region replication
  attivabile).
- **17.B** Modalità degraded software (rete cellulare giù → mesh radio
  drone-to-drone simulato, LoRa backup interface).
- **17.C** Backup energia logica (gestione drone con dock offline).
- **17.D** Continuità durante eventi di massa (priority queue
  emergenza vitale, batch deferral missioni di ronda).
- **17.E** Disaster mode (sospende SLA normali, prioritizza vite umane).

**Gate**: tutti i fallimenti simulati (kill region, kill bus, kill dock)
gestiti senza loss di stato critico.

## Phase 18 — Privacy mask + explainability + bias check (2-3 settimane)

**Obiettivo**: chiudere il "compliance software" che serve a girare
post-seed senza riscritture. La legalità per giurisdizione è in Phase 25
post-seed; qui le primitive software.

- **18.A** Privacy mask automatica su video (volti, targhe, finestre
  edifici terzi). Pipeline CV su ogni frame prima della persistenza.
- **18.B** Diritto all'oblio video: API + UI per richiesta
  cancellazione, conferma immutabile nel decision log.
- **18.C** Conservazione dati: retention policy software (cancellazione
  automatica dopo N giorni, configurabile per giurisdizione).
- **18.D** Bias check tool: dataset sintetici con varianti
  demografiche, misura accuracy gap, flag per audit.
- **18.E** Opt-out cittadini: schema dati + endpoint per registrare
  preferenza, rispetto in dispatch.
- **18.F** Trasparenza statistiche pubbliche: API pubblica + dashboard
  Grafana per metriche aggregate (no PII).

**Gate**: privacy mask attiva su 100% video in sim; bias gap < 5%;
opt-out rispettato; dashboard pubblica accessibile.

## Phase 19 — Hardware bench su terreno privato del founder (4-10 settimane)

**Obiettivo**: portare TUTTO il software delle Phase 7-18 sul **drone
vero sul terreno proprio del founder**, generando video reali ad
altissima densità informativa per il pitch.

**Capitale richiesto**: 5-15k EUR personali del founder (out-of-pocket
o piccola linea di credito). Non si aspetta seed.

**Setup legale leggero (decisione utente: "freghiamoci di
regulations")**:
- Categoria ENAC Open A2/A3 (sotto 25 kg, VLOS, sotto 120m, su
  proprietà privata recintata con consenso del proprietario =
  founder stesso). Nessuna autorizzazione speciale richiesta.
- Patentino pilota drone Open A1/A3 ENAC: gratuito online, 1 giorno.
- Iscrizione operatore ENAC: gratuita, online.
- Assicurazione RC droni professionale: €300-800/anno (UnipolSai,
  AON, brokers specializzati).
- DPIA leggero per dati personali eventualmente catturati (founder
  + collaboratori consenzienti = banale).
- Totale tempo bureaucracy: ~1 settimana.

**Hardware shopping list (5-15k EUR)**:
- **19.A** 1-2 droni PX4-compatibili:
  - Holybro X500 V2 (kit ARF ~$700) + autopilot Pixhawk 6X (~$300)
    + payload bay = base configurabile.
  - Oppure ModalAI Starling 2 (~$5k) — più caro ma onboard compute
    pronto.
  - Telemetria radio SiK 433/915 MHz (~$80 coppia).
- **19.B** Camera + termocamera:
  - Visible: Runcam o GoPro Hero (~$200-400).
  - Termica: FLIR Boson 320 (~$2-3k) o Seek Thermal modulo OEM
    (~$500-1k) — risoluzione bassa OK per MVP.
- **19.C** GPS RTK (Ardusimple simpleRTK2B base + rover, ~$600 totale).
- **19.D** Batterie + spare parts + caricabatterie (€500-1k).
- **19.E** Docking station prototype "casalinga": ricarica
  semi-manuale + pannello solare basico. Per MVP basta uno spazio
  coperto con caricabatterie automatico (€200-500 componenti).
- **19.F** Sicurezza: estintore CO2 a bordo, kit primo soccorso,
  elmetto, area zero terzi durante test fuoco. **Non negoziabile**.

**Integrazione hardware → SwarmOS**:
- **19.G** Validazione Phase 5 sull'hardware reale (MAVLink/PX4):
  HEARTBEAT, mission upload, RTL, fence enable, param writes tutti
  verificati col drone reale. Finalmente passa il gate hardware
  pending della Phase 5.
- **19.H** CV su feed video reale del drone: fine-tuning leggero
  YOLOv8 (già allenato in Phase 10) su immagini girate sul terreno
  per aumentare detection accuracy su scenari italiani specifici.
- **19.I** Adapter termocamera (FLIR Boson o Seek): integrato come
  payload secondario, frame termici allineati a frame visibili.
- **19.J** Onboard compute: Raspberry Pi 5 o Jetson Nano/Orin Nano
  sul drone per inference CV in volo.
- **19.K** Tooling registrazione: pipeline che salva ogni volo come
  bundle (telemetria + video visibile + video termico + decisioni
  SwarmOS + audio scriptato) per debug e per montaggio pitch.

**Scenari testati sul terreno reale**:
- **19.L** **Pattugliamento autonomo** del perimetro del terreno:
  drone decolla, fa la ronda, rientra, si ricarica, da solo. Replica
  reale di 7-8-9 (autonomy + federation se 2 droni).
- **19.M** **Detection intrusione**: amico/collaboratore entra nel
  terreno, drone lo rileva con CV, si avvicina, illumina, manda audio
  dissuasivo TTS, registra. Replica reale 14.G-M (protezione casa).
- **19.N** **Detection incendio + intervento minimo**: fuoco
  controllato in barile metallico (con tutte le sicurezze), drone lo
  rileva con termocamera, si avvicina, telecamera punta la fonte.
  Spegnimento attivo **opzionale** (capsula gel se si trova un payload
  economico e sicuro; altrimenti solo detection + handoff a estintore
  manuale dietro). Replica reale 14.A-F (incendio).
- **19.O** **Ricerca soggetto**: amico nascosto in vegetazione del
  terreno, drone lo trova con termocamera + CV. Replica reale 14.O.
- **19.P** **Notte + illuminazione**: ronda notturna con faro LED ad
  alta intensità, detection di soggetti in zone non illuminate.
- **19.Q** **Multi-drone coordinato**: se in 19.A si comprano 2 droni,
  test di handoff sciame su scenario pattugliamento. Replica reale 9.

**Output di Phase 19**:
- **19.R** Video pitch reali (non sim): 5-10 minuti totali di footage
  girato, pronto per montaggio Phase 20.
- **19.S** Lessons learned: cosa funziona, cosa va riscritto, metriche
  realisticamente raggiungibili.
- **19.T** Lista bug + miglioramenti per backlog post-seed.
- **19.U** Self-validated SwarmOS che vola davvero — sblocca tutte le
  affermazioni "we have flown" nel pitch.

**Gate Phase 19**: almeno 10 ore di volo cumulativo, almeno 5 scenari
testati con successo end-to-end, video raw raccolto, zero incidenti
con feriti o danni terzi. Nessun pitch parte finché Phase 19 non passa
questo gate.

## Phase 20 — Materiali pitch con video reali (2-4 settimane)

**Obiettivo**: pacchetto pitch professionale, demo call ready.

- **20.A** Pitch deck 12-15 slide: problema → mercato → soluzione →
  demo embed (video Phase 19) → traction (=metriche sim + ore di volo
  reali) → team (=founder + AI stack) → business model → giurisdizione
  + go-to-market Rwanda/Dubai → roadmap → ask + use-of-funds.
- **20.B** Demo video editato 90s da raw Phase 19, sottotitolato
  inglese, per email/LinkedIn/landing.
- **20.C** Technical whitepaper 15-25 pagine: architettura SwarmOS,
  shield deterministico vs ML, federazione, decision log firmato,
  perché Rwanda+Dubai, evidence dal bench Phase 19.
- **20.D** One-pager PDF per cold email.
- **20.E** Financial model Google Sheets, 5 anni (costi, ricavi,
  break-even per città).
- **20.F** Business plan 20 pagine.
- **20.G** Landing page (Next.js, hostata su Vercel) con email capture,
  demo video embed, contatto founder.
- **20.H** Press kit minimal.
- **20.I** Profili pubblici: LinkedIn, Twitter/X, AngelList/Crunchbase.

**Gate**: pacchetto inviabile a investitore Tier-1 — verificato da
almeno 1 advisor esterno.

## Phase 21 — Outreach pre-seed (4-12 settimane)

**Obiettivo**: chiudere primo capitale (target 500K-3M EUR pre-seed o
seed, più alto rispetto a piano precedente perché il prodotto è più
maturo).

- **21.A** Lista 100 investitori target:
  - VC deep-tech UE/USA (Lakestar, NGP Capital, Bessemer, In-Q-Tel,
    Lockheed Martin Ventures).
  - VC climate-tech (per wildfire/Protezione Civile).
  - VC Africa-focused (Partech Africa, TLcom, Norrsken22).
  - VC GCC / Middle East (MEVP, Wamda, Mubadala, PIF-linked).
  - Angel italiani con exit deep-tech.
  - Family office Gulf + Italian.
- **21.B** Lista 30 partner potenziali:
  - Rwanda: RCAA, MININFRA, Rwanda Development Board, Kigali City,
    Zipline (benchmark), Civil Protection Rwanda.
  - Dubai: DCAA, RTA, Dubai Civil Defense, DEWA, EmiratesNBD.
  - Insurance: SwissRe, Munich Re Africa, Dubai Islamic Insurance.
- **21.C** Lista 20 advisor (equity-only o fractional): ex-Zipline,
  ex-EASA/FAA, ex-founder con exit deep-tech, ex-Civil Defense,
  legal counsel drone law UAE + UE.
- **21.D** Cold outreach: email + LinkedIn + intro warm. Target: 30-50
  demo call nei primi 3 mesi.
- **21.E** Letter of Intent da 3-5 partner potenziali (non vincolanti).
- **21.F** Contatti preliminari regolatori: email/call esplorative con
  RCAA + Dubai DCAA / GCAA.
- **21.G** Iterazione pitch su feedback.
- **21.H** Convertire interesse in term sheet.

**Gate**: term sheet firmato, oppure 3+ investitori in due diligence
attiva con LOI verbali.

## Phase 22 — Seed close + team minimo (mesi 13-18)

**Obiettivo**: trasformarsi da founder solo + AI in azienda operativa
minima.

- **22.A** Setup legale: holding (probabilmente Delaware o Singapore
  per investitori internazionali) + opco locale Rwanda e/o Dubai.
- **22.B** Closing seed round.
- **22.C** Prime 3-5 assunzioni in ordine di criticità:
  1. CTO / tech-lead senior.
  2. ML/CV engineer.
  3. Hardware/integrazione engineer.
  4. Business development + legal locale.
  5. (Opzionale) Operations fractional.
- **22.D** Workspace fisico minimo.
- **22.E** Hardware procurement scala: 5-10 droni PX4-compatible
  + 1-2 docking station prototype.
- **22.F** Primo pilota concordato con partner pubblico (Rwanda
  preferibile come primo per AED/ricerca dispersi; Dubai parallelo per
  wildfire test in zone desertiche extra-urbane).
- **22.G** Apertura cantieri Fasi 23+ in parallelo.

**Gate**: primo drone reale vola sotto controllo SwarmOS in spazio
aereo controllato in giurisdizione target (campo prove Dubai o area
test Rwanda autorizzata).

---

## Phase 23 → Phase 30 — Post-seed execution (con team + capitale + giurisdizione attiva)

> Queste 8 fasi sono ciò che richiede genuinamente team, capitale,
> infrastruttura fisica, autorità locali, o trazione utenti — niente
> di tutto questo è bootstrappabile da founder solo + AI.
>
> Tutto il software è stato sviluppato in Phase 7-18, validato su
> hardware in Phase 19, mostrato agli investitori in Phase 20-21, e il
> seed è chiuso in Phase 22. Le 16 fasi software pre-seed coprono ~90%
> del codice; post-seed è prevalentemente hardware fisico, partnership,
> regolatorio, ops.
>
> **Giurisdizioni commerciali**: Rwanda + Dubai (UAE) prima. Espansione
> ulteriore (incluso eventuale rientro UE/USA) in Phase 30.

## Phase 23 — Infrastruttura docking stations fisica

**Obiettivo**: rete di docking station strategicamente posizionate sul
territorio. Software dispatch (Phase 13) e ML positioning algorithm
(Phase 10) sono già pronti — qui si dispiegano fisicamente.

Profili ambientali distinti: Rwanda (clima collinare, 1500m, piogge) e
Dubai (deserto, 50°+ estate, polvere, salinità costiera).

- **23.A** Hardware docking station weather-proof per due profili
  ambientali: tropical highland (Rwanda) + desert/coastal (Dubai).
  Anti-vandalismo.
- **23.B** Applicare algoritmo posizionamento Phase 10.E sul layout
  reale (copertura città, ETA target, vincoli legali locali).
- **23.C** Permessi pubblici: Kigali City + Rwanda Development Board
  per suolo pubblico; Dubai Municipality + RTA per suolo pubblico;
  accordi con sviluppatori privati (Emaar/Damac Dubai, Vision City
  Rwanda) per palazzi privati.
- **23.D** Alimentazione (rete + solare backup obbligatorio — Rwanda
  rete instabile, Dubai sole abbondante; UPS sempre).
- **23.E** Connettività (4G/5G primaria + LoRaWAN backup; Rwanda ha
  MTN e Airtel, Dubai ha du e Etisalat).
- **23.F** Diagnostica remota docking station (software dashboard
  esistente da Phase 16.A).
- **23.G** Manutenzione predittiva drone + dock (ML model da Phase 10.G).
- **23.H** Inventory management droni (rotazione, riparazioni;
  supply chain hardware da Cina via Dubai hub).
- **23.I** Carico drone su dock libero più vicino dopo intervento
  (logica software da Phase 13.A).

**Gate**: densità docking station sufficiente a garantire ETA < 120s
sul 95% del territorio coperto in zona pilota (un quartiere Kigali e
un quartiere Dubai).

## Phase 24 — Integrazione autorità locali

**Obiettivo**: il sistema lavora **prima** dei servizi tradizionali,
mai **al posto** loro. Posizionamento "infrastruttura primo strato",
non "polizia privata" — coerente con la sensibilità locale.

- **24.A** Chiamata automatica numero emergenza nazionale (codice già
  pronto da Phase 14.F, qui si firma il contratto con il provider
  telecomunicazioni che permette l'inoltro):
  - Rwanda: 912 (emergency), 113 (police), 912 (medical/fire).
  - Dubai: 999 (police), 998 (ambulance), 997 (fire).
- **24.B** Live feed alle autorità competenti con autenticazione
  (Dubai Civil Defense per incendi, Rwanda Fire & Rescue + RBC per
  emergenze mediche). Software pronto da Phase 16.C; qui contratti +
  endpoint reali.
- **24.C** Handoff custodia evento (drone passa il "caso" all'umano
  appena arrivano).
- **24.D** Chain of custody video/audio per uso giudiziale (estende
  l'hash chain di Phase 16.A).
- **24.E** API verso centrali operative locali.
- **24.F** Coordinamento con elisoccorso e altri servizi aerei
  (separazione altitudini).
- **24.G** Protocollo "stand-down" quando arriva pattuglia (drone si
  ritira o supporta in modo subordinato).

**Gate**: accordo operativo scritto con almeno una autorità per
giurisdizione (Dubai Civil Defense per incendi, Rwanda Civil
Protection per emergenze mediche); protocollo handoff testato in
esercitazione congiunta.

## Phase 25 — Compliance giurisdizione target

**Obiettivo**: il sistema è legale e auditabile in Rwanda e Dubai.
Software privacy/explainability/bias-check è già in Phase 18 — qui si
fa la parte legale + autorizzazioni + insurance.

- **25.A** Autorizzazione volo BVLOS / autonomo urbano:
  - **Rwanda**: RCAA — Rwanda Civil Aviation Authority. Quadro
    progressivo, hanno già autorizzato Zipline. Categoria
    "performance-based" applicabile.
  - **Dubai**: DCAA + GCAA federale + Dubai Sky Dome iniziativa.
    Sandbox attivi per droni autonomi.
- **25.B** Coordinamento traffico aereo: Rwanda RCAA UTM nascente;
  Dubai SkyHub UTM in pilota — partecipare al pilota se accessibile.
- **25.C** Privacy data protection compliance (software già pronto
  in Phase 18.A privacy mask + 18.B oblio + 18.C retention):
  - **Rwanda**: Law N° 058/2021 (data protection); registrazione
    presso NCSA.
  - **Dubai**: PDPL (Personal Data Protection Law UAE 2021) + DIFC
    DP Law se holding DIFC.
- **25.D** Sovranità dati locale (data residency per giurisdizione,
  region cloud locale).
- **25.E** DPIA / equivalent risk assessment pubblicato per ogni
  città servita.
- **25.F** Consenso cittadini opt-in (per scenari attivi, non per
  zona pubblica con privacy mask).
- **25.G** Audit indipendente algoritmico annuale (terza parte
  certificata; tooling bias-check da Phase 18.D).
- **25.H** Compliance uso dispositivi attivi (sirene/luci/payload):
  valutazione legale locale caso per caso.
- **25.I** Polizza assicurativa civile multimilionaria (Lloyd's
  internazionale + reinsurance locale).
- **25.J** Accountability cascade chiara (provider → city partner →
  utente).
- **25.K** Public oversight committee per ogni città servita
  (composizione: cittadini + autorità + advisor).
- **25.L** Trasparenza pubblica: report quadrimestrale falsi positivi,
  interventi, danni.

**Gate**: autorizzazione regolatoria scritta da autorità competente per
ogni città servita. **Bloccante**: senza 25.A non si vola
commercialmente.

## Phase 26 — Sicurezza fisica drone in produzione

**Obiettivo**: difese hardware contro attacchi attivi. Software cyber
(decision log firmato, anti-hijack firma comandi, SBOM) già pronto in
Phase 16.

- **26.A** Anti-spoofing GPS (multi-constellation: GPS + GLONASS +
  Galileo + BeiDou; RTK quando possibile).
- **26.B** Resistenza a jamming radio (frequency hopping).
- **26.C** Backup comms multi-canale (4G + LoRa + satellite Iridium
  per fallback assoluto).
- **26.D** Protezione fisica drone (carrozzeria leggera, fail-safe
  atterraggio, ditching sicuro).
- **26.E** Decommissioning sicuro se catturato (wipe + brick remoto;
  trigger da Phase 16.D).
- **26.F** Difesa anti-drone offensivo (se qualcuno cerca di
  abbatterli).
- **26.G** Penetration testing annuale obbligatorio (red team esterno,
  estende il pen-test software di Phase 16.E).
- **26.H** Bug bounty program (target hardware + cloud).
- **26.I** Cosign + Sigstore identity reale per immagini production
  (estende Phase 6.E + 16.F).

**Gate**: red team esterno (drone hijack + GPS spoof + radio jam +
abbattimento fisico) tutti respinti, almeno una volta per giurisdizione.

## Phase 27 — Etica e accettazione locale

**Obiettivo**: il sistema è accettato culturalmente. Le metriche di
"accettazione" cambiano profondamente tra Kigali (comunità
collettivista, post-genocidio, alta fiducia istituzioni) e Dubai
(multiculturale, transitoria, alta tolleranza tech).

Software-side (bias check, explainability, opt-out cittadini) già
pronto in Phase 18 — qui si fa la parte community + comunicazione.

- **27.A** Community advisory board locale (Rwanda — leader cellule
  amministrative + civil society; Dubai — rappresentanti compound +
  camere di commercio).
- **27.B** Comunicazione pubblica chiara (cosa il sistema fa e NON
  fa); ufficio stampa locale.
- **27.C** Sondaggi accettazione periodici per quartiere/compound
  (target: > 70% favorevoli a 6 mesi).
- **27.D** Modalità "drone visibile" (livrea distintiva, luci sempre
  accese, suono identificabile).
- **27.E** Pubblicazione trasparente statistiche reali (dashboard
  pubblica già pronta da Phase 18.F) — no marketing.
- **27.F** Programma educativo nelle scuole / community center
  (Rwanda: alta efficacia; Dubai: meno necessario ma utile).
- **27.G** Risposta strutturata a incidenti pubblici (PR crisis
  playbook).

**Gate**: community advisory board attivo per ogni città; accettazione
pubblica > soglia in sondaggi locali; revisione semestrale board.

## Phase 28 — Resilience operativa

**Obiettivo**: il sistema funziona anche quando il mondo intorno
crolla. Software failover/degraded/disaster mode già in Phase 17 — qui
si fanno gli esercizi reali + infra distribuita.

Profili disastro diversi: Rwanda (frane, terremoti minori, piogge);
Dubai (tempeste sabbia, alluvioni urbane occasionali, eventi
tecnologici).

- **28.A** Failover regionale operativo: AWS Bahrain o Frankfurt per
  Dubai; AWS Cape Town o GCP Johannesburg per Rwanda; cross-region
  replication attiva e testata.
- **28.B** Test reali modalità degraded (rete cellulare giù → mesh
  radio drone-to-drone + LoRa backup) — code esiste da Phase 17.B.
- **28.C** Backup energia docking station verificato sul campo
  (batteria 48h+, solare).
- **28.D** Continuità durante eventi di massa (esercitazione
  terremoto/alluvione/tempesta con comuni partner).
- **28.E** Disaster mode (Phase 17.E già scritto) attivato in drill
  almeno una volta per giurisdizione.
- **28.F** Off-site backup encrypted + restore drill quarterly.
- **28.G** RTO/RPO dichiarati per giurisdizione e rispettati.

**Gate**: DR drill annuale superato per giurisdizione; RTO < 4h, RPO
< 1h; restore drill verde.

## Phase 29 — Operations + supporto

**Obiettivo**: il sistema autonomo ha comunque un'organizzazione umana
dietro, distribuita tra le giurisdizioni servite.

- **29.A** Operations center 24/7 per fuso orario coperto (Dubai
  GMT+4 + Kigali GMT+2 sono solo 2h di delta — un team unico con
  shifting funziona).
- **29.B** Tier 1/2/3 support per cittadini abbonati (multilingua
  EN/AR/KIN/FR).
- **29.C** Onboarding city partner (installazione, calibrazione,
  training operatori locali).
- **29.D** Programma certificazione tecnici manutenzione locali
  (riduce dipendenza espatriati; impegno verso Rwanda Vision 2050 +
  Emiratisation Dubai).
- **29.E** Centro ricerca + sviluppo continuo (HQ R&D Dubai o
  Lussemburgo per ragioni fiscali; team distribuiti).
- **29.F** Apertura ufficio legale + business operations locale per
  giurisdizione.

**Gate**: SLO supporto p95 < target; turnover tecnici certificati
sotto soglia; tempo di risoluzione tier-1 < 1h, tier-2 < 4h, tier-3
< 24h.

## Phase 30 — Espansione

**Obiettivo**: scalare oltre Rwanda + Dubai.

- **30.A** Seconda ondata: GCC (Riyadh / NEOM Arabia Saudita, Doha
  Qatar) + East Africa (Nairobi Kenya, Kampala Uganda); copia il
  template Dubai e Rwanda con minimi adattamenti.
- **30.B** Terza ondata (post-trazione): rientro UE/USA con caso di
  successo dimostrato, dati reali in mano, framework regolatori UE
  affrontabili (SORA Specific). A questo punto Phase 25 si estende per
  coprire EASA + GDPR + FAA.
- **30.C** Adapter vendor multipli (PX4, DJI Enterprise se serve,
  custom hardware proprietario).
- **30.D** Marketplace skill plugin (detector specializzati per use
  case nuovi: agricoltura precision, monitoraggio infrastrutture).
- **30.E** Open API per integratori terzi.
- **30.F** SDK Python/TypeScript per partner.
- **30.G** Sandbox/demo cloud per prospect.

**Gate**: ogni nuova città servita con stesso codebase + adattamenti
regolatori locali + community advisory board attivo entro 6 mesi
dall'avvio.

## Dipendenze tra le fasi 7-30

```
PRE-SEED (solo + AI, nessun investitore necessario):
7 (sw MVP base) ──> 8 (autonomy) ──┬──> 9 (federazione sim)
                                    ├──> 10 (ML sim)
                                    ├──> 11 (detection multimodale sim)
                                    ├──> 12 (app cittadino)
                                    ├──> 13 (dispatch sim)
                                    ├──> 14 (intervento attivo sim)
                                    ├──> 15 (multi-tenant + biz)
                                    ├──> 16 (decision log + cyber sw)
                                    ├──> 17 (resilience sw)
                                    └──> 18 (privacy + bias + explain sw)
                                                  │
                                                  ↓
                              19 (HARDWARE BENCH su terreno founder)
                                                  │
                                                  ↓
                                          20 (pitch reale)
                                                  │
                                                  ↓
                                          21 (outreach)
                                                  │
                                                  ↓
                                          22 (SEED CLOSE)

POST-SEED (con team + capitale + giurisdizione attiva):
22 ──┬──> 23 (docking fisico) ──┬──> 30 (espansione)
     ├──> 24 (autorità locali) ─┤
     ├──> 25 (compliance) ──────┤ ← BLOCKER per 23, 24, 26
     ├──> 26 (sicurezza fisica)─┤
     ├──> 27 (etica/community) ─┤
     ├──> 28 (resilience ops) ──┤
     └──> 29 (operations) ──────┘
```

**Ordine consigliato di attacco**:

Pre-seed (sequenziale stretto):
1. Phase 7 sblocca tutto.
2. Phase 8-18 in parallelo dove possibile, ma realisticamente solo
   con AI è meglio sequenziale (focus founder = uno alla volta).
3. Phase 19 SOLO dopo che tutto il software (7-18) ha gate verde.
4. Phase 20 SOLO dopo Phase 19 con almeno 10 ore di volo reali.
5. Phase 21-22 sequenziali.

Post-seed (parallelizzabile con team):
1. Phase 25 (compliance) parte **subito** dopo seed — è il
   bloccante non-tecnico più lungo.
2. Phase 23 (docking) + Phase 24 (autorità) in parallelo.
3. Phase 26 (sicurezza fisica) + Phase 27 (community) trasversali,
   sempre on.
4. Phase 28 (resilience ops) richiesta prima del go-live.
5. Phase 29 (ops) richiesta per pilot live.
6. Phase 30 (espansione) ultimo blocco.

## Caveat sul piano 7-30

### Pre-seed (Fasi 7-22) — founder + AI

- **Effort realistico**: 13-18 mesi di lavoro intenso founder + Claude
  Code + Codex. Software (Phase 7-18) ~9-12 mesi, hardware bench
  (Phase 19) ~2 mesi, pitch+outreach+seed (Phase 20-22) ~3-5 mesi
  parallelizzati.
- **Capitale founder out-of-pocket**: ~10-20k EUR (hardware bench
  Phase 19 + iscrizioni + assicurazione + viaggi networking pre-seed).
- **Bloccanti reali**:
  - **Focus founder**: 9-12 mesi solo su software prima di vedere
    soldi è lungo. Rischio burnout serio. Mitigazione: trovare
    1-2 advisor presto (Phase 21.C anticipata anche in fase
    software), check-in mensili per sanity.
  - **Lentezza outreach**: anche con tutto pronto, chiudere seed può
    richiedere 6-12 mesi di outreach. Iniziare Phase 21 lavori
    preparatori (lista, intro warm) in parallelo a Phase 18-19.
- **Rischio principale**: il prodotto è tecnicamente pronto ma il
  mercato/regolatorio Rwanda+Dubai cambia. Mitigazione: contatti
  esplorativi RCAA + DCAA fin da Phase 21.F.

### Post-seed (Fasi 23-30) — team + capitale + regolatorio

- **Effort realistico**: 3-7 anni con team da 10-25 persone (ingegneria
  ridotta perché il software è fatto; più hardware, ops, legal,
  business dev). Il software pre-seed copre ~90% del codice; post-seed
  è hardware fisico, partnership, regolatorio, ops, scale.
- **Blocco più duro NON tecnico**: Phase 25 (regolatorio). Rwanda RCAA
  e Dubai DCAA sono **più rapide** di EASA, ma comunque 6-18 mesi di
  procedure. Va affrontata in parallelo all'hardware, **non dopo**.
- **Blocco secondo più duro**: Phase 27 (accettazione locale). Errare
  un'esercitazione pubblica in Kigali o Dubai uccide il prodotto per
  anni. Investire seriamente in community engagement.
- **Capitale**: seed serio (1-3M EUR per coprire Phase 23+25+26+27 a
  piccola scala); Series A 5-15M per scale su entrambe le giurisdizioni
  + apertura prima città Phase 30.
- **Hardware lead time**: 3-6 mesi tipici per quantità (droni custom
  + docking station prototype). Ordinare appena chiuso il seed.
- **Ordine di esecuzione potrebbe cambiare** in base a feedback
  regolatorio, capitale disponibile, primo pilota concreto. Le Fasi
  23-30 sono **scheletro decisionale**, non specifica implementativa.

Queste 24 fasi totali (16 pre-seed + 8 post-seed) sono **piano
vivente**: ogni fase, prima di partire, va espansa allo stesso livello
di dettaglio delle Fasi 0-6 (file specifici, contratti API, test,
gate di accettazione). Aspettarsi che la roadmap cambi dopo Phase 19
(feedback hardware reale), dopo seed close (feedback investitori),
dopo primo pilota commerciale (feedback regolatorio Rwanda/Dubai), e
dopo prima trazione utenti (feedback prodotto).

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
