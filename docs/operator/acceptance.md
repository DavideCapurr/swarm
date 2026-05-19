# Acceptance test — operatore reale su sito di prova

Phase 6.J — runbook che un nuovo operatore (cliente o pilota della
flotta) esegue durante l'acceptance test in campo. È la controparte
manuale del test end-to-end automatico
([`tests/e2e/test_anomaly_lifecycle.py`](../../tests/e2e/test_anomaly_lifecycle.py)):
stessa sequenza di stati, stesso ordine, stessa rubric pass/fail, ma
guidata dall'operatore con drone reale o SITL.

L'esecuzione live è un drone-day item — vedi
[`docs/ops/drone-day-checklist.md` §2.J](../ops/drone-day-checklist.md).

## Pre-flight equipment

- [ ] Console attiva su laptop dell'operatore (sessione di prova, account
      operator + commander pre-provisionati come da
      [`docs/security/pentest-scope.md`](../security/pentest-scope.md)
      "Credentials policy" — gli account `op-test-acceptance-A/B/C` sono
      i corrispondenti per acceptance).
- [ ] Site config caricato (`SWARM_SITE_ID` corretto in `.env`, polygon
      verificato a mano contro la mappa del sito).
- [ ] Drone(s) carichi al 100 % e dock online (controlla `/docks`).
- [ ] Weather provider sano (`/health` non riporta `weather_lock`).
- [ ] Manuale operatore aperto in browser:
      [`docs/operator/manual.md`](manual.md).

## Sequenza di scenari (1-to-1 con il test e2e)

Ogni scenario ha un riferimento esplicito alla transizione del test e2e
canonico. Il rubric è pass/fail puro: ogni casella spuntata è "comportato
come da manuale; nessuna azione fuori dal lessico intent".

### Scenario A — `pending`
*Riferimento*: pubblicazione di una anomaly via perception.

- [ ] L'operatore vede l'anomaly in `/anomalies` con `state=pending`.
- [ ] L'operatore non invia comandi manuali al drone — solo intent.
- [ ] La timeline `/events` mostra un evento `anomaly`.

### Scenario B — `verifying`
*Riferimento*: `/actions/verify` con `target=anomaly:<id>`.

- [ ] L'operatore individua l'anomaly, valuta confidenza, decide di
      verificare.
- [ ] Invia intent `verify` da ActionRail.
- [ ] L'anomaly transita a `state=verifying`; `verifying_agent` valorizzato.
- [ ] CommandTimeline mostra il command in stato `accepted`.

### Scenario C — `verified`
*Riferimento*: la missione di verify completa.

- [ ] Il drone raggiunge la geo dell'anomaly entro l'ETA atteso.
- [ ] Dopo il completamento della verify, `/anomalies[i].state=verified`.
- [ ] Awareness mostra `mode=escalation` (no red — amber band).

### Scenario D — escalation
*Riferimento*: nessun comando esplicito; transizione automatica di mode.

- [ ] L'operatore osserva il banner di escalation nel Console.
- [ ] La timeline elenca l'evento `event verified · operator decision required`.
- [ ] Nessun manual override viene tentato.

### Scenario E — `return`
*Riferimento*: `/actions/return` con `target=unit:<verifier>`.

- [ ] L'operatore decide di rientrare l'unità di verifica.
- [ ] Invia intent `return` su quella unità.
- [ ] `/missions` mostra una mission `RTL_DOCK` assegnata all'unità.

### Scenario F — dock
*Riferimento*: la fleet-state DOCKED.

- [ ] Il drone atterra al dock entro l'ETA stimato.
- [ ] `/units[<verifier>].fsm_state=DOCKED`.
- [ ] `/docks[<dock_id>].units_docked` incrementa.

### Scenario G — emergency drill
*Riferimento*: `EMERGENCY_RTL_ALL` (Phase 6.G).

- [ ] L'operatore commander apre il pulsante EmergencyStop.
- [ ] Digita esattamente `RETURN ALL UNITS` per confermare.
- [ ] Tutti gli unit airborne ricevono una mission `RTL_DOCK` con
      `priority=100`.
- [ ] L'evento di audit con bypass policy compare in timeline.

### Scenario H — auth boundary
*Riferimento*: l'account viewer non può inviare intent.

- [ ] L'operatore esegue logout, login come `op-test-acceptance-A`
      (viewer-only).
- [ ] Tentativo di `/actions/verify` → 403 nella UI; nessun command in
      audit.

### Scenario I — geofence rifiutato
*Riferimento*: PolicyEngine rifiuta una verify fuori polygon.

- [ ] L'operatore tenta `verify` su un'anomaly fuori dal geofence di sito.
- [ ] Il backend rifiuta con `rejected_reason=outside_geofence` (422).
- [ ] L'audit log registra il rifiuto senza dispatchare il drone.

### Scenario J — weather lock
*Riferimento*: provider meteo emette `weather_lock=true` sul dock.

- [ ] Il dock mostra `weather_lock` nel pannello.
- [ ] Lo scheduler non lancia nuovi patrol (verifica via `/events`).
- [ ] Verify operatore manuale viene rifiutata con
      `rejected_reason=weather_lock`.

## Sign-off

| Sezione | Esito | Firmato da | Data |
|---------|-------|------------|------|
| Pre-flight equipment | ☐ pass / ☐ fail | _____________ | _________ |
| Scenari A–F (happy path) | ☐ pass / ☐ fail | _____________ | _________ |
| Scenario G (emergency) | ☐ pass / ☐ fail | _____________ | _________ |
| Scenari H–J (boundary) | ☐ pass / ☐ fail | _____________ | _________ |
| Acceptance test completo | ☐ pass / ☐ fail | _____________ | _________ |

Sito: _______________________________ Versione SwarmOS: _____________

Operatore: __________________________ Pilota in command: ____________

## Defect triage SLA

Le anomalie rilevate durante l'acceptance test seguono lo stesso
SLA del pen-test esterno
([`docs/security/pentest-scope.md`](../security/pentest-scope.md) §"Remediation SLA"),
con la stessa scala di severità. Un fallimento "scenario blocker" (A–F)
blocca il sign-off di Phase 6; un fallimento boundary (H–J) richiede
mitigation entro 14 giorni ma non blocca.

## Phase 6 acceptance gate

Per [`docs/plan/swarmos-roadmap.md`](../plan/swarmos-roadmap.md) §"Verifica
Phase 6": un operatore nuovo deve poter eseguire una verify end-to-end
seguendo solo [`docs/operator/manual.md`](manual.md). Questo runbook è
il banco di prova esplicito di quella richiesta.
