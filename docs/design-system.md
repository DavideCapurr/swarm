# SWARM — Design System

> The canonical source is `docs/pdf/SWARM-design-system-v1.pdf`. Until we can extract
> tokens from that PDF (no `pdftotext`/`poppler`/PDF Python libs in the current
> environment), the frontend ships with a **placeholder token set in
> `frontend/lib/tokens.ts`** that is consistent with the voice and minimal visual
> motifs observed in the text-only PDFs.

## Status

| Item | Status | Source of truth |
|---|---|---|
| Token file | Placeholder | `frontend/lib/tokens.ts` |
| Color palette | Placeholder (black/whites/orbital) | `SWARM-design-system-v1.pdf` |
| Typography | Placeholder (system + thin geometric) | `SWARM-design-system-v1.pdf` |
| Spacing scale | Placeholder (4 / 8 / 12 / 16 / 24 / 32) | `SWARM-design-system-v1.pdf` |
| Components | Map / FleetGrid / EventFeed (skeleton) | `SWARM-design-system-v1.pdf` |

## How to graduate from placeholder

One of:

1. **(preferred)** User shares directly: hex codes, font families, type scale,
   spacing scale, icon set, component states (default, hover, focus, disabled,
   loading, error).
2. Environment gains `poppler-utils` so the team can extract pages and image
   regions from the PDF programmatically.
3. A vision-capable assistant reads the PDF and we transcribe to tokens.

Then update `frontend/lib/tokens.ts`, audit the three components against the PDF
spec, and remove this notice.

## Voice (already known)

From the textual PDFs:

- **Quiet. Precise. Already arrived.**
- **Many units. One intention.**
- Operational, not cinematic.
- Restrained typography, dark canvas, thin orbital line motifs as a brand signature.
- No emoji, no marketing exclamation, no warm gradients.
