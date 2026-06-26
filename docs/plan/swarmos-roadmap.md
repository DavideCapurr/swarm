# SwarmOS — Phase 0 → Phase 6 technical plan (PDF foundation)

> **Scope (2026-06-26):** this file is the **Phase 0-6 technical reference**
> only — the original PDF-derived foundation (security baseline, sim kernel,
> Console, truth layer, persistence, real adapter, production OS). It is
> referenced as such by `CLAUDE.md`.
>
> **Phase 7 and beyond are NOT planned here.** The canonical Phase 7→30
> execution order and numbering live in
> [`swarm-roadmap-evidence-to-scale.md`](swarm-roadmap-evidence-to-scale.md).
> The earlier Phase 7→30 draft that used to live in this file (with a
> colliding Phase 8 = autonomy / 9 = federation / 10 = ML numbering) is
> preserved at
> [`archive/swarmos-roadmap-phase7-30-draft.md`](archive/swarmos-roadmap-phase7-30-draft.md).

Phase 0–6 = original PDF roadmap (technical foundation, largely done).

Decisioni aggiornate 2026-05-22:
1. Il prodotto davanti diventa **SWARM Patrol Cell**: pattuglia mobile,
   verifica, evidence packet ed escalation per territori privati ad alto
   valore, senza richiedere sensori fissi proprietari nel MVP. Wildfire
   resta il primo beachhead/proof path, ma non il confine del prodotto.
   La North Star resta una rete autonoma di risposta e resilienza
   territoriale.
2. La maturita 2026 e l'avvio di **BIEF Bocconi a settembre 2026** sono
   vincoli di calendario. YC Summer 2026 non e il target operativo:
   eventuale candidatura YC usa un batch successivo / Early Decision.
3. Il de-risk reale non aspetta piu la fine di tutte le feature software:
   PX4/SITL, hardware bench e primo test fisico supervisionato entrano
   appena la demo Phase 7 e ripetibile.
4. UAE, HAX, B4i e altri ecosistemi sono piste da validare con intro,
   buyer e pilot path. Non sono relocation o product pivot automatici.
5. Ogni affermazione esterna distingue `sim`, `SITL`, `bench`,
   `supervised field`, `pilot` e `commercial production`.

Casi supportabili dallo stesso loop: wildfire-risk cue, intrusione,
persona/veicolo ignoto, search/verification in sito delimitato, danni
post-evento, asset anomaly, richiesta manuale e settore stale. Non vanno
presentati come prodotti separati simultanei: entrano solo se riusano il
loop Patrol Cell di pattuglia, verifica, evidenza e supervisione.

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

## Phase 7+ current roadmap

The current Phase 7-30 execution order lives in
[`swarm-roadmap-evidence-to-scale.md`](swarm-roadmap-evidence-to-scale.md).
It was updated on 2026-05-22 after re-evaluating YC timing, maturita,
BIEF Bocconi, UAE as a discovery lane, market validation and the need to
de-risk PX4/SITL and hardware before a year of extra simulation work.


The earlier detailed Phase 7→30 draft that used to continue here — with its
own Phase 8 = autonomy / 9 = federation / 10 = ML numbering — has been moved
to [`archive/swarmos-roadmap-phase7-30-draft.md`](archive/swarmos-roadmap-phase7-30-draft.md)
to remove the phase-number collision. **This file is now the Phase 0-6
technical reference only.** All Phase 7+ planning and numbering is owned by
[`swarm-roadmap-evidence-to-scale.md`](swarm-roadmap-evidence-to-scale.md).
