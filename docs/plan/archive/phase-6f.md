# Phase 6.F — Performance + scale targets

> **ARCHIVED 2026-06-26.** Completed implementation spec for a shipped phase
> (Phase 6 is `done`). Kept for history. Current status: [`../../STATUS.md`](../../STATUS.md).
> Internal links below are relative to the original `docs/plan/` location.

> Branch: `claude/plan-phase-6e-ef41S` (l'utente ha scritto "6E" ma Phase 6.E è già `done` in `docs/STATUS.md` e mergeato in PR #40 — la prossima fase pendente è **6.F**, confermato dall'utente via AskUserQuestion).

## Context

Phase 6 (Production OS) è in corso: 6.A → 6.E sono `done`, 6.F → 6.J restano pendenti. Phase 6.F definisce e **valida** i target di performance/scale che l'intero piano deve rispettare prima di dichiarare la Phase 6 completa:

- Per sito: **50 unit concorrenti**, 5 dock, telemetria 10 Hz/unit (= **500 msg/s sul bus**), **WS frame p95 < 200 ms**, **REST p95 < 100 ms**.
- Multi-sito: **10 site concorrenti** per istanza.
- Burst: **200 unit** con **degradazione graceful** (rate-limit, mai crash).
- **Load test settimanale in CI** sotto `tests/load/` con threshold di fail se p95 sfora.
- **Chaos test**: kill backend → frontend riconnette in < 6 s; kill Redis → orchestrator passa a `InMemoryBus`, anomaly detection degradata ma sicura.

Verifica Phase 6 (gate finale): "Load test: target Phase 6.F rispettati a p95" + "Chaos test: nessun crash con component kill".

## Decisioni chiave (recommended)

1. **Driver load test**: pure-Python `asyncio` + `httpx` + `websockets`. Entrambe sono **già core deps** (`pyproject.toml:19`, `pyproject.toml:27`). Niente `locust`/`k6`: aggiungerebbero dipendenze/toolchain non necessarie.
2. **Due livelli di test**:
   - **In-process pytest** (`tests/load/test_load_inproc.py`, marker `@pytest.mark.load_smoke`) che pubblica su un `InMemoryBus` reale e misura latenza p95 fanout WS + REST. Riproducibile, niente docker, gira a ogni push (smoke 50 msg/s × 30 s, threshold = 2× baseline registrato in `tests/load/results/baseline.json`).
   - **Driver out-of-process** (`tests/load/driver.py`) che colpisce il backend live via REST+WS. Usato da `make load-soak` (500 msg/s × 5 min) e dal job settimanale.
3. **CI**: nuovo workflow `.github/workflows/load-test.yml` con `schedule: cron "17 4 * * 1"` (lun 04:17 UTC, off-window rispetto a `image-scan.yml` daily `11 3 * * *`) + `workflow_dispatch`. Action SHA-pinnate come tutto il resto del repo. Smoke aggiunto come job extra in `test.yml`.
4. **Chaos**: `docker compose pause redis` (recovery pulito senza data loss) + `kill -SIGTERM` sull'uvicorn (stesso lifecycle di Kubernetes via `infra/helm/swarmos/`). Script in `scripts/chaos/`.
5. **DB write batching**: **contingente**. Strumentazione misurata prima; se `make load-soak` mostra che le scritture per-message in `bus_consumer.py:145,161,177,192` sono il bottleneck del p95, si introduce un `RepositoryBatcher` con `asyncio.Queue(maxsize=4096)` drainato ogni 100 ms via `bulk_insert_mappings`. Touch points: `backend/app/db/repository.py:96-189`, `backend/app/bus_consumer.py:135-192`.
6. **Coordinator `_refresh` per-event**: **misurare prima**. `_refresh()` (`swarm_os/coordinator.py:225-252`) gira per ogni bus message; debounce 50 ms è il piano-B se p95 > 200 ms (cambia semantica derived-frame → rischio regressione test esistenti).

## File da creare / modificare

### Nuovi
- `tests/load/__init__.py` — package marker (stile `tests/fuzz/`).
- `tests/load/conftest.py` — fixture che monta `InMemoryBus` + `BusConsumer` + `WSHub`, espone `publish_telemetry(agent_id, count, hz)` + fake-client che timestampa la ricezione. Riutilizza pattern di `backend/tests/conftest.py`.
- `tests/load/test_load_inproc.py` — tre test `@pytest.mark.load_smoke`:
  - `test_p95_ws_latency_500_msg_s` — 50 agenti × 10 Hz × 30 s, asserzione p95 < 200 ms.
  - `test_rest_p95_under_load` — polling concorrente di `/awareness`, `/units`, `/anomalies`, p95 < 100 ms.
  - `test_burst_200_units_graceful` — 200 agenti distinti × 10 Hz × 10 s; assert no-exception + counter di rejection del `TelemetryRateLimiter` > 0 (prova degradazione graceful, vedi `core/swarm_core/rate_limit.py` e re-enforcement in `backend/app/bus_consumer.py:141`).
- `tests/load/driver.py` — driver stand-alone `python -m tests.load.driver --rate 500 --duration 300 --target ws://localhost:8765/ws`. Scrive p50/p95/p99 in `tests/load/results/last.json`, exit code ≠ 0 se threshold violata.
- `tests/load/README.md` — come interpretare i risultati; cross-link a `docs/ops/performance.md`.
- `tests/chaos/__init__.py` + `tests/chaos/ws_probe.py` — client `websockets` minimale che misura delta `close → open`; replica il contract di `frontend/lib/ws.ts:91,112` (primo retry @ 500 ms, cap 10 s — headroom ampio sui 6 s richiesti).
- `scripts/chaos/redis_pause.sh` — `docker compose pause redis && sleep 8 && docker compose unpause redis`; asserisce log `falling back to InMemoryBus` e `/healthz` 200 durante la pausa.
- `scripts/chaos/backend_kill.sh` — `pgrep -f "backend.app.main" | xargs kill -SIGTERM`; misura reconnect ≤ 6 s via `ws_probe.py`.
- `.github/workflows/load-test.yml` — workflow settimanale SHA-pinned, permissions `contents: read` only.
- `docs/ops/performance.md` — tabella SLO + come eseguire i target locali; rimanda a `swarm_http_request_duration_seconds` (già wired in `backend/app/observability/metrics.py`, buckets ms 5/10/25/50/100/250/500/1000/2500/5000/10000/30000 — coprono già 100 ms e 200 ms). Voice audit: niente parole vietate da CLAUDE.md.

### Da toccare
- `pyproject.toml` — registrare i marker `load_smoke` e `chaos` sotto `[tool.pytest.ini_options].markers` (sezione a riga 109). **Nessuna nuova dipendenza**.
- `Makefile` — nuovi target phony: `load-smoke`, `load-soak`, `chaos-redis`, `chaos-backend`. Aggiunti a `.PHONY`.
- `.github/workflows/test.yml` — aggiungere job `load-smoke` che gira `pytest -m load_smoke -q`. Niente nuove action.
- `docs/STATUS.md` — flip 6.F a `in_progress` all'apertura, a `done` al merge.

### Contingenti (solo se la misurazione lo richiede)
- `backend/app/db/repository.py` — `RepositoryBatcher` con queue + drain task 100 ms.
- `backend/app/bus_consumer.py:145,161,177,192` — sostituire `await get_repository().write_*` con `batcher.enqueue(...)`.
- `backend/app/observability/metrics.py` — counter `swarm_repository_batch_flush_total` per visibilità.
- `swarm_os/coordinator.py:225-252` (`_refresh`) — debounce-collapsing 50 ms se p95 > 200 ms.

## Infra esistente da riusare (NON ricreare)

- `httpx>=0.27,<1` core dep — driver load.
- `websockets>=12,<17` core dep — driver + ws_probe.
- `orchestrator/swarm_orchestrator/bus.py:145-176` `InMemoryBus` — riusato sia nei test in-process che dal fallback in chaos-redis.
- `core/swarm_core/rate_limit.py` `TelemetryRateLimiter` (50 Hz/agent default) — già rilevante per il burst test.
- `backend/app/security.py` `RateLimiter` (token-bucket, capacity 30 / refill 0.5 s) — già rilevante per il REST load test.
- `backend/app/observability/metrics.py` istogrammi `swarm_http_request_duration_seconds` — buckets coprono già le soglie.
- `frontend/lib/ws.ts:91,112` reconnect esponenziale — già conforme al target 6 s, niente UI work in 6.F.
- `.github/workflows/image-scan.yml` (cron `11 3 * * *`) + `codeql.yml` (settimanale) — precedente per `schedule:` in CI.
- `backend/tests/conftest.py` — pattern fixture autouse + auth.

## Verifica end-to-end (gate Phase 6.F)

Da una checkout pulita su `claude/plan-phase-6e-ef41S`:

```bash
make infra && make db-migrate
make backend &                  # background; attendi /readyz
make load-smoke                 # in-process: p95 WS < 200 ms, REST < 100 ms a 50 msg/s
make load-soak                  # 500 msg/s × 5 min; exit ≠ 0 se p95 sfora
make chaos-redis                # log InMemoryBus, 0 5xx durante pause
make chaos-backend              # reconnect ≤ 6 s, /healthz 200 dopo restart
make lint && make test && make audit
```

Threshold di pass numerici:
- WS broadcast-emit **p95 < 200 ms** sul finestra 5 min.
- REST **p95 < 100 ms** su `/awareness`, `/units`, `/anomalies`, `/missions`.
- Burst: **zero 5xx**, `TelemetryRateLimiter` rejection counter > 0.
- Chaos: Redis paused 8 s → 0 crash + log `InMemoryBus` presente; SIGTERM uvicorn → reconnect ≤ 6 s su 3 prove consecutive.

## Rischi & mitigazioni

- **Runner GitHub anemico → p95 falsato.** Smoke usa threshold *relativa* (2× baseline mediano catturato al primo run verde, salvato in `tests/load/results/baseline.json`); soak gira solo settimanale; opt-in self-hosted documentato ma non assunto.
- **Postgres in CI sotto carico.** Compose override `docker-compose.ci.yml` con `POSTGRES_FSYNC=off` **solo in CI**, mai locale/prod.
- **Jitter di rete nel chaos test.** Primo retry frontend a 500 ms (`ws.ts:91`) → 5.5 s di headroom sul cap 6 s. Probe gira 3 volte, asserisce max ≤ 6 s.
- **Lock contention scambiata per latenza DB.** Strumentazione `time.perf_counter()` attorno a `state.lock` (`swarm_os/coordinator.py:60-203`) **solo nel harness**, esposta in `results/last.json` per diagnosi.
- **Overflow queue InMemoryBus a 500 msg/s.** `maxsize=4096` (`bus.py:167`) drena in ~8 ms a regime — OK. Documentato in `docs/ops/performance.md`.

## Punt espliciti (NON in 6.F)

- Patroni / Redis-Sentinel failover → **6.G**.
- Soak 24 h su infra prod-shape → drone-day checklist.
- Chaos network reale (partition, latency injection via `tc netem`) → **6.G**.
- Pannelli Grafana sui nuovi istogrammi → **6.G** (in 6.F si documentano solo i bucket esistenti).
- DB write batching solo se misurazione lo richiede.
- Nessun lavoro UI: il reconnect frontend già rispetta il target 6 s.

## Branch + commit hygiene

- Sviluppo su `claude/plan-phase-6e-ef41S`.
- Commit incrementali, tutti prefissati `phase-6f:`:
  1. `phase-6f: scaffold tests/load + driver`
  2. `phase-6f: in-process p95 assertions`
  3. `phase-6f: scripts/chaos/* + Makefile targets`
  4. `phase-6f: weekly load-test workflow (SHA-pinned)`
  5. `phase-6f: docs/ops/performance.md + STATUS update`
  6. (cond.) `phase-6f: RepositoryBatcher contingency`
- Mai `--no-verify`. Lockfile invariato (zero nuove dipendenze).

## File critici (per esecuzione)

- `backend/app/bus_consumer.py` — hot path consumer + persistenza.
- `swarm_os/coordinator.py:225-252` — `_refresh()` per-event.
- `backend/app/ws/telemetry.py` + `backend/app/hub.py` — fanout WS.
- `backend/app/db/repository.py:96-189` — write paths candidati a batching.
- `orchestrator/swarm_orchestrator/bus.py:145-176` — `InMemoryBus` riusato.
- `core/swarm_core/rate_limit.py` — degradazione graceful.
- `backend/app/observability/metrics.py` — istogrammi già pronti.
- `pyproject.toml:109` — marker pytest.
- `Makefile` — target nuovi.
- `.github/workflows/test.yml` + `load-test.yml` (nuovo) — CI.

## Come riavviare il piano in un'altra sessione

Apri una nuova sessione su `claude/plan-phase-6e-ef41S` e dai questo prompt:

> Esegui il piano salvato in `docs/plan/phase-6f.md`. Rispetta `CLAUDE.md`, segui la sequenza dei commit `phase-6f:` 1→6, gate finale: `make lint && make test && make audit` + i target `make load-smoke / load-soak / chaos-redis / chaos-backend`. Non aggiungere dipendenze, non pushare su main.
