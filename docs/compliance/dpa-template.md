# Data Processing Agreement — Template (Phase 6.I)

> **This is a template, not a signed agreement.** The legal team of the
> SwarmOS controller and processor must tailor every clause to the
> concrete deployment (jurisdiction, sub-processors, audit rights,
> transfer mechanism, etc.) before signing. Nothing here constitutes
> legal advice.

This template covers the SwarmOS-specific clauses of a GDPR Art. 28
Data Processing Agreement. It is meant to be merged into the
controller's standard processor framework or to seed a stand-alone
DPA where none exists.

## 1. Parties

* **Controller**: the legal entity operating the SwarmOS deployment on
  its own infrastructure ("the Operator").
* **Processor**: the legal entity supplying SwarmOS as a service ("the
  Vendor"). When SwarmOS is self-hosted from the published repository
  with no operational support contract in place, no processor
  relationship is created.

## 2. Subject matter and duration

* **Subject matter**: provision of the SwarmOS software and, where
  applicable, the managed-service operations of a drone fleet
  supervision platform.
* **Duration**: the term of the underlying service agreement, with the
  post-termination obligations in §9 applying for the retention floor
  declared in [`retention.md`](retention.md).

## 3. Nature and purpose of processing

The Processor processes personal data only for the following purposes:

1. Operating the SwarmOS backend (authentication, authorisation, audit
   trail, telemetry ingestion).
2. Providing security operations (incident response, vulnerability
   management, log review).
3. Providing support and maintenance to the Controller.

## 4. Categories of data and data subjects

| Category                 | Subjects                          |
|--------------------------|-----------------------------------|
| Operator identifier      | The Controller's authorised operators (employees / contractors). |
| Authentication material  | Same as above (password hash, MFA seed). |
| Operational audit data   | Same as above (intent submissions, login events). |
| Drone telemetry          | Operational data — personal only if a drone is consistently linked to one identifiable person. |
| Client IP                | Operators connecting from a managed device. |
| Camera frames (future)   | Members of the public present in the operating area, once the camera payload is wired (drone-day). |

## 5. Processor obligations (Art. 28(3))

The Processor:

* (a) **Processes personal data only on documented instructions** from
  the Controller, including with regard to transfers of personal data
  to a third country or international organisation, unless required to
  do so by Union or Member State law to which the Processor is
  subject; in such a case, the Processor informs the Controller of
  that legal requirement before processing, unless that law prohibits
  such information on important grounds of public interest.
* (b) **Ensures that persons authorised to process the personal data
  have committed themselves to confidentiality or are under an
  appropriate statutory obligation of confidentiality.**
* (c) **Takes all measures required pursuant to Article 32** — the
  concrete control set is the SwarmOS threat-model document
  ([`docs/security/threat-model.md`](../security/threat-model.md)) and
  the controls catalogued in
  [`gdpr.md`](gdpr.md) §6.
* (d) **Respects the conditions for engaging another processor**
  referred to in paragraphs 2 and 4 of Art. 28 (see §6 below).
* (e) **Assists the Controller** by appropriate technical and
  organisational measures, insofar as this is possible, for the
  fulfilment of the Controller's obligation to respond to requests
  for exercising the data subject's rights — the SwarmOS data-subject
  endpoints are `/admin/export` and `/admin/forget`, both
  commander+MFA gated.
* (f) **Assists the Controller** in ensuring compliance with the
  obligations pursuant to Art. 32 to 36 taking into account the
  nature of processing and the information available to the Processor
  — see the breach-notification flow in
  [`gdpr.md`](gdpr.md) §7.
* (g) **At the choice of the Controller, deletes or returns all the
  personal data** to the Controller after the end of the provision of
  services relating to processing, and deletes existing copies unless
  Union or Member State law requires storage of the personal data.
  SwarmOS supports an offline export via `pg_dump` + GPG encryption
  (see [`docs/ops/deploy.md`](../ops/deploy.md)) and an in-place
  erasure via `/admin/forget`.
* (h) **Makes available to the Controller all information necessary to
  demonstrate compliance** with the obligations laid down in this
  Article and allows for and contributes to audits, including
  inspections, conducted by the Controller or another auditor
  mandated by the Controller.

## 6. Sub-processors

In the default self-hosted deployment, **no sub-processors are wired**.
Optional integrations that introduce a sub-processor must be authorised
in writing by the Controller, listed in an annex to this DPA, and the
Processor remains fully liable to the Controller for the performance
of the sub-processor's obligations.

| Integration                       | Sub-processor (when enabled) | Default state |
|-----------------------------------|------------------------------|---------------|
| Real weather API (Phase 6.A hook) | e.g. OpenWeather, Aviationweather | Off — stub provider used |
| NOTAM / U-space feed              | Civil aviation authority feed | Off — drone-day |
| OpenTelemetry exporter            | The Operator's tracing backend | Off — `SWARM_OTLP_ENDPOINT` unset |
| Container registry                | GHCR (GitHub Container Registry) | Off in self-hosted; on for the published images |
| Signing                           | Sigstore                     | Off in self-hosted; on for release-tag images |

## 7. International transfers

The default self-hosted deployment performs no international transfer
beyond the Controller's chosen infrastructure. When an optional
sub-processor is enabled, the transfer mechanism (Adequacy decision,
Standard Contractual Clauses, BCRs) is the Controller's responsibility
to document and the Processor's responsibility to honour.

## 8. Audit rights

The Controller may audit the Processor's compliance with this DPA
with reasonable notice (default: 30 days) and at the Controller's
expense, with the Processor providing:

* The SwarmOS audit log of `system` events for the requested period
  (`POST /admin/export` against an internal `op-audit` account, or
  direct SQL access to `events` and `operator_commands` with a
  read-only role).
* The SBOM and signing materials for the deployed image.
* The retention-policy evidence (`SELECT * FROM
  timescaledb_information.jobs WHERE proc_name='policy_retention'`).
* The penetration-test report for the relevant period.

## 9. Termination

On termination, the Processor:

1. Stops all processing on the Controller's instruction effective
   date.
2. Returns a final `pg_dump | gpg` of all personal data to the
   Controller's GPG recipient.
3. Deletes the in-place datastore after the Controller confirms
   receipt and integrity of the dump.
4. Preserves the audit floor declared in
   [`retention.md`](retention.md) only insofar as a legal obligation
   requires it; otherwise deletes it.

## 10. Liability and indemnity

Per the underlying service agreement.

## 11. Governing law

Per the underlying service agreement.

---

## Annex A — Technical and organisational measures

Concrete control list mapped to ISO/IEC 27001 Annex A is documented
inline in [`gdpr.md`](gdpr.md) §6 and
[`threat-model.md`](../security/threat-model.md). The annex of a signed
DPA should reference these documents at a stable commit hash.

## Annex B — Authorised sub-processors

(See §6 above. Populate per concrete deployment.)

## Annex C — Data subject request workflow

The Controller's DSAR procedure handles data-subject authentication.
The Processor's commander runs `/admin/export` or `/admin/forget`
after the Controller's confirmation. The two endpoints are documented
in [`gdpr.md`](gdpr.md) §4 and exercised by the test suite.
