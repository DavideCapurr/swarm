# TAKE — foglio di montaggio (offset verificati sul file)

**Video**: `artifacts/take-A/TAKE-A-2560x1440-30fps.webm` — 2560×1440, 16:9, **30 fps**, 80.17 s, 56 MB.

**Probe**: `yc_demo_recording_probe.py` — status **pass**, 13/13 step, durata 68.978 s. Mission 1 owner `mav-002`, mission 2 owner `mav-001`.

Due colonne diverse, non confonderle:

- **RUN +** = istante reale della verità sul bus. È il numero da bruciare negli overlay.
- **SEEK** = dove trovare il beat nel file video.

Coincidono entro ~0.12 s: è la latenza di render della Console fra verità sul bus e pixel a schermo, misurata sui frame (0.122 s a +40.7 s, ~0.000 s a +74.1 s — costante, nessuna deriva).

| Beat | Step probe | RUN + | SEEK | Cosa deve essere leggibile |
|---|---|---|---|---|
| Stato pulito | `clean_startup` | `00:00.0` | `+5.47s` | LINK CONNECTED · Fleet entrambi DOCKED 100% |
| Evento 1 | `event_1` | `00:00.0` | `+5.47s` | 01 OBJECTIVE · INTRUSION 95% · id evento |
| Valutazione flotta | `event_1_allocation` | `00:00.0` | `+5.47s` | 02 FLEET EVALUATED BY SWARMOS · MODE·AUCTION · SERVER REASONS |
| Selezione | `event_1_dispatch` | `00:00.0` | `+5.47s` | 03 SELECTED BY SWARMOS · mav-002 · WINNER SCORE 2.258 |
| Dispatch | `event_1_en_route` | `00:01.0` | `+6.43s` | 05 PHYSICAL EXECUTION · EN ROUTE |
| JUMP CUT 1 → | `event_1_verified_on_station` | `00:35.3` | `+40.74s` | 06 EVIDENCE · MISSION_ITEM_REACHED · PX4 SITL |
| Payload attivo | `event_1_payload_active` | `00:35.4` | `+40.83s` | LIGHT ON · PX4 OUTPUT CONFIRMED / SPEAKER ACTIVE · SIMULATED |
| Evento 2 | `event_2_busy_reallocation` | `00:35.4` | `+40.84s` | mav-002 EXCLUDED·BUSY + mission id, poi mav-001 SELECTED 2.271 |
| Concorrenza | `concurrent_missions_visible_truth` | `00:36.3` | `+41.74s` | MISSION TIMELINE · due swimlane sovrapposte, owner diversi |
| Cleanup | `payload_cleanup` | `00:55.4` | `+60.89s` | SPEAKER STOPPED · LIGHT OFF |
| JUMP CUT 2 → | `mission_1_rtl` | `00:55.4` | `+60.91s` | OBJ 01 DONE·CLOSED · RTL COMMAND ACKNOWLEDGED PX4 SITL |
| Chiusura missione 2 | `mission_2_closure` | `01:08.7` | `+74.13s` | OBJ 02 ON STATION → DONE · seconda swimlane chiude |

## I due tagli

- **JUMP CUT 1** — taglia da `+6.43s` a `+40.74s`: **34.3 s** di EN ROUTE. Overlay `RUN +00:35.3 · JUMP CUT`.
- **JUMP CUT 2** — taglia da `+60.91s` a `+74.13s`: **13.2 s**. Overlay `RUN +01:08.7 · JUMP CUT`.

Pre-roll pulito utilizzabile: 0 → +5.47s. Post-roll dopo la chiusura: +74.13s → 80.17s.

Materiale netto dopo i due tagli ≈ 32.6 s.

## Caveat verificato sui dati

`event_1`, `event_1_allocation` e `event_1_dispatch` cadono entro **7 millisecondi** l'uno dall'altro. Sul bus sono un istante solo, non tre beat separati: fra "Evento 1" e "Selezione" **non esistono cut point da cercare nel file**. La durata di quella sezione è tempo di lettura, deciso in montaggio. Gli unici offset che ancorano un taglio vero sono i tre distanziati (`+6.43s`, `+40.74s`, `+60.91s` → `+74.13s`).

## Sorgente per ri-encode

`artifacts/take-A/raw/` contiene i 4518 frame originali JPEG 2560×1440 con `frame-index.json` (timestamp wall-clock per frame). Da lì si ri-codifica a qualsiasi fps/codec senza rigirare la take. **Pesa 1.9 GB** — cancellabile quando il montaggio è chiuso.
