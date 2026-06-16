"""Phase 8.B-bis — the human-baseline oracle for shadow mode.

The Phase 8 gate is "< 5% divergence from a human decision" over 100+ runs
of the three scenarios. In a sim there is no human, so that gate needs a
**labelled reference policy per scenario** — the design item the
three-month plan flags as "the first design decision of Track A". This
module is that decision, resolved.

Design decision (real-world-transferable on purpose):
  The oracle decides on the **same observable signal the engine sees** —
  anomaly kind, confidence, lifecycle state, ``hold_patrol`` — and nothing
  else. A real operator has no privileged ground-truth channel, and a real
  deployment has no scripted truth to peek at; an oracle that read the sim's
  hidden script would measure *accuracy against truth*, not *agreement with
  a human*, and would not transfer out of the sim. So the oracle is a pure
  function of the observable signal, exactly like the production decider it
  shadows.

  Where it differs from the engine — and why divergence is meaningful — is
  representation: the engine reasons in per-scenario tuned **floats**
  (`autonomy_config.py`), the oracle in the PDF voice confidence **bands**
  (`voice.py`: low-confidence < 0.60 ≤ elevated < 0.85 ≤ verified) plus the
  documented per-scenario operator intent. Wildfire escalates a verified
  hotspot readily; intrusion and search reserve escalation for the operator
  (``escalate_delegated``); search verifies even faint heat-spots because
  missing a person is the costly error. Divergence is then the honest
  measure of how often the tuned floats depart from band-level human
  judgment — zero on the canonical scripted anomalies (the engine is tuned
  to agree), non-zero under confidence jitter near a band edge, which is
  what the < 5% gate bounds.

The oracle is a `Decider` in the `swarm_os.shadow` sense: ``decide_all``
returns one `AnomalyDisposition` per anomaly, the same DTO the engine
returns, so the shadow harness compares the two apples-to-apples. The
config mirrors `autonomy_config.py`: a frozen, ``extra="forbid"`` schema
loaded from `infra/config/autonomy_baseline.yaml` with an in-code fallback
so a fresh clone and CI boot without any file on disk.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from swarm_core.messages import AnomalyKind, AnomalyState, AnomalyView, ConfidenceBand
from swarm_core.voice import LOW_THRESHOLD, VERIFIED_THRESHOLD
from swarm_core.voice import band as confidence_band

from swarm_os.autonomy import AnomalyDisposition, AutonomyVerdict

if TYPE_CHECKING:  # pragma: no cover
    from swarm_os.state import SwarmState

DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parents[1] / "infra" / "config" / "autonomy_baseline.yaml"
)

_STRICT = ConfigDict(extra="forbid", frozen=True)

# Ordinal for "band at/above another band" comparisons. Matches the voice
# band order: low-confidence < elevated < verified.
_BAND_ORDER: dict[ConfidenceBand, int] = {
    ConfidenceBand.LOW_CONFIDENCE: 0,
    ConfidenceBand.ELEVATED: 1,
    ConfidenceBand.VERIFIED: 2,
}

# The float at the bottom of each band (from voice.py). Used by the profile
# validator to forbid a dismiss floor that would swallow the verify band.
_BAND_FLOOR: dict[ConfidenceBand, float] = {
    ConfidenceBand.LOW_CONFIDENCE: 0.0,
    ConfidenceBand.ELEVATED: LOW_THRESHOLD,
    ConfidenceBand.VERIFIED: VERIFIED_THRESHOLD,
}


class OracleProfile(BaseModel):
    """The human-baseline disposition policy for one scenario class.

    Band-level, not float-tuned (that is the engine's job). Decision order
    for a PENDING anomaly is dismiss-first, then verify, then the WAIT
    middle:

      * ``confidence < dismiss_below``         → DISMISS (clearly nothing).
      * ``band(confidence) >= verify_band``    → VERIFY (worth a look).
      * otherwise                              → WAIT (ambiguous, hold).

    For a VERIFIED anomaly:

      * ``escalate_delegated``                 → WAIT (operator owns it).
      * ``band(confidence) >= escalate_band``  → ESCALATE.
      * otherwise                              → WAIT.
    """

    model_config = _STRICT
    verify_band: ConfidenceBand = ConfidenceBand.ELEVATED
    dismiss_below: float = Field(0.30, ge=0.0, le=1.0)
    escalate_delegated: bool = False
    escalate_band: ConfidenceBand = ConfidenceBand.VERIFIED

    @model_validator(mode="after")
    def _check_dismiss_does_not_swallow_verify(self) -> OracleProfile:
        """The dismiss floor must not reach into the verify band.

        With dismiss-first precedence, a ``dismiss_below`` above the verify
        band's floor would auto-dismiss anomalies the same profile would
        otherwise verify — an incoherent reference. The ``verify_band ==
        low-confidence`` regime is the deliberate exception (search verifies
        everything above the dismiss floor), so it is skipped.
        """

        if self.verify_band is ConfidenceBand.LOW_CONFIDENCE:
            return self
        floor = _BAND_FLOOR[self.verify_band]
        if self.dismiss_below > floor:
            raise ValueError(
                "dismiss_below must not reach into the verify band "
                f"(got dismiss_below={self.dismiss_below}, verify_band="
                f"{self.verify_band.value} floor={floor})"
            )
        return self


class OracleConfig(BaseModel):
    """Named per-scenario oracle profiles + the kind→profile routing table.

    Mirrors `autonomy_config.AutonomyConfig` so the oracle routes an anomaly
    to its profile by the same `AnomalyKind` signal the engine uses — the
    only scenario signal an anomaly carries at decision time.
    """

    model_config = _STRICT
    default: OracleProfile = Field(default_factory=OracleProfile)
    profiles: dict[str, OracleProfile] = Field(default_factory=dict)
    kind_to_profile: dict[AnomalyKind, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_routing(self) -> OracleConfig:
        unknown = {
            name for name in self.kind_to_profile.values() if name not in self.profiles
        }
        if unknown:
            raise ValueError(
                f"kind_to_profile references undefined profiles: {sorted(unknown)}"
            )
        return self

    def profile_name_for(self, kind: AnomalyKind) -> str:
        name = self.kind_to_profile.get(kind)
        return name if name is not None else "default"

    def profile_for(self, kind: AnomalyKind) -> OracleProfile:
        name = self.kind_to_profile.get(kind)
        if name is not None:
            return self.profiles[name]  # _check_routing guarantees presence
        return self.default


def _builtin_oracle_config() -> OracleConfig:
    """In-code human-baseline reference that keeps CI green without the YAML.

    The per-scenario intent is the one documented in the scenario YAMLs:
      * wildfire — verify elevated smoke, escalate a verified hotspot.
      * intrusion — verify elevated signal, *reserve escalation* for the
        operator (``escalate_delegated``).
      * search — verify even faint (low-confidence) heat-spots and rarely
        dismiss, because missing a person is the costly error; escalation
        again reserved for the operator.
    """

    wildfire = OracleProfile(
        verify_band=ConfidenceBand.ELEVATED,
        dismiss_below=0.30,
        escalate_delegated=False,
        escalate_band=ConfidenceBand.VERIFIED,
    )
    intrusion = OracleProfile(
        verify_band=ConfidenceBand.ELEVATED,
        dismiss_below=0.30,
        escalate_delegated=True,
        escalate_band=ConfidenceBand.VERIFIED,
    )
    search = OracleProfile(
        verify_band=ConfidenceBand.LOW_CONFIDENCE,
        dismiss_below=0.15,
        escalate_delegated=True,
        escalate_band=ConfidenceBand.VERIFIED,
    )
    return OracleConfig(
        default=OracleProfile(),
        profiles={
            "wildfire": wildfire,
            "intrusion": intrusion,
            "search": search,
        },
        kind_to_profile={
            AnomalyKind.SMOKE: "wildfire",
            AnomalyKind.FIRE: "wildfire",
            AnomalyKind.HEAT_SPOT: "search",
            AnomalyKind.INTRUSION: "intrusion",
        },
    )


def load_oracle_config(*, config_path: Path | None = None) -> OracleConfig:
    """Load + validate `infra/config/autonomy_baseline.yaml`.

    Falls back to `_builtin_oracle_config()` when the file is absent so a
    fresh clone boots. Parse/schema errors are intentionally loud (CLAUDE.md
    root-cause discipline: no silent failure-swallowing).
    """

    path = config_path or DEFAULT_BASELINE_PATH
    if path.is_file():
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return OracleConfig.model_validate(raw)
    return _builtin_oracle_config()


class BaselineOracle:
    """The human-baseline reference decider.

    A `Decider` in the `swarm_os.shadow` sense: ``decide_all(state, now)``
    returns one `AnomalyDisposition` per anomaly. Pure — it never acts, never
    touches `state.commands`, and ignores `state.autonomy_enabled` (a shadow
    reference decides regardless of whether the live engine is armed).
    """

    def __init__(self, config: OracleConfig | None = None) -> None:
        self._config = config or load_oracle_config()

    @property
    def config(self) -> OracleConfig:
        return self._config

    def decide_all(
        self, state: SwarmState, now: datetime
    ) -> list[AnomalyDisposition]:
        # `now` is part of the Decider contract (the engine uses it for the
        # debounce/idle/stale windows). The band-level oracle has no timing
        # windows, so it is unused here — kept for signature parity.
        del now
        return [self._decide(a, state) for a in state.anomalies.values()]

    def _decide(self, anomaly: AnomalyView, state: SwarmState) -> AnomalyDisposition:
        profile = self._config.profile_for(anomaly.kind)
        profile_name = self._config.profile_name_for(anomaly.kind)
        conf = anomaly.confidence
        band = confidence_band(conf)

        def out(verdict: AutonomyVerdict, reason: str) -> AnomalyDisposition:
            return AnomalyDisposition(
                anomaly_id=anomaly.id,
                verdict=verdict,
                rule=None,  # the oracle is a reference, not an engine rule
                confidence=conf,
                profile=profile_name,
                reason=reason,
            )

        if state.hold_patrol:
            return out(AutonomyVerdict.WAIT, "patrol held by operator")

        if anomaly.state == AnomalyState.PENDING:
            if conf < profile.dismiss_below:
                return out(
                    AutonomyVerdict.DISMISS,
                    f"baseline: confidence {_pct(conf)} below dismiss floor "
                    f"{_pct(profile.dismiss_below)}",
                )
            if _band_at_least(band, profile.verify_band):
                return out(
                    AutonomyVerdict.VERIFY,
                    f"baseline: {band.value} confidence {_pct(conf)} warrants "
                    f"verification",
                )
            return out(
                AutonomyVerdict.WAIT,
                f"baseline: confidence {_pct(conf)} below the "
                f"{profile.verify_band.value} band — hold",
            )

        if anomaly.state == AnomalyState.VERIFIED:
            if profile.escalate_delegated:
                return out(
                    AutonomyVerdict.WAIT, "baseline: escalation reserved for operator"
                )
            if _band_at_least(band, profile.escalate_band):
                return out(
                    AutonomyVerdict.ESCALATE,
                    f"baseline: verified confidence {_pct(conf)} warrants escalation",
                )
            return out(
                AutonomyVerdict.WAIT,
                f"baseline: verified confidence {_pct(conf)} below the "
                f"{profile.escalate_band.value} band — hold",
            )

        # VERIFYING + terminal states (DISMISSED / ESCALATED / MARKED_KNOWN).
        return out(
            AutonomyVerdict.WAIT,
            f"baseline: no action in state {anomaly.state.value}",
        )


def _band_at_least(band: ConfidenceBand, floor: ConfidenceBand) -> bool:
    return _BAND_ORDER[band] >= _BAND_ORDER[floor]


def _pct(value: float) -> str:
    """Confidence-bound percentage copy — e.g. 0.5 → ``050%`` (PDF voice)."""

    return f"{round(value * 100):03d}%"


__all__ = (
    "DEFAULT_BASELINE_PATH",
    "BaselineOracle",
    "OracleConfig",
    "OracleProfile",
    "load_oracle_config",
)
