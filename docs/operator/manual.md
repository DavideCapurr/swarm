# Guida operatore Console

## Obiettivo
Questa guida descrive come un operatore supervisiona la flotta in Console usando intent approvati da SwarmOS.

## Flusso standard
1. Accedi via `/login` con account autorizzato.
2. Verifica stato generale su `/session`, `/fleet`, `/awareness`.
3. Valuta anomalie su `/anomalies` e timeline `/events`.
4. Invia intent solo quando necessario:
   - `verify`
   - `hold-patrol`
   - `dismiss`
   - `return`

## Flusso di emergenza
Per blocco operativo di flotta:
1. Apri il controllo emergenza in Console.
2. Seleziona intento `EMERGENCY_RTL_ALL`.
3. Conferma digitando esattamente `RETURN ALL UNITS`.
4. Verifica esito in timeline eventi e stato unità.

## Runbook collegati
- Deploy: [`docs/ops/deploy.md`](../ops/deploy.md)
- Migrations: [`docs/ops/migrations.md`](../ops/migrations.md)
- Performance: [`docs/ops/performance.md`](../ops/performance.md)
- Disaster recovery: [`docs/ops/disaster-recovery.md`](../ops/disaster-recovery.md)
- Drone day checklist: [`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md)
- Observability: [`docs/observability/overview.md`](../observability/overview.md)
- Auth design: [`docs/security/auth.md`](../security/auth.md)
