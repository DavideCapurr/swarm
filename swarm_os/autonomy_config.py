"""Phase 8.B — per-scenario thresholds for the deterministic autonomy engine.

Phase 7.B carried the four decision thresholds (verify floor / escalate
floor / dismiss ceiling + their debounce/idle/stale windows) as module
constants in `swarm_os/autonomy.py` — one global tuning shared by every
scenario. Phase 8.B moves them into per-scenario *profiles* loaded from
`infra/config/autonomy.yaml`, so the wildfire arc can escalate readily
while a search arc holds a lower dismiss bar for a possible person.

An `AutonomyProfile` is the threshold set for one scenario class. An
`AutonomyConfig` carries the named profiles, a `default` fallback, and a
`kind_to_profile` map that routes an anomaly to its profile *by
`AnomalyKind`* — the only scenario signal an anomaly carries at decision
time (the single-cell kernel hosts one scenario at a time; multi-site
routing is Phase 9). The loader mirrors `swarm_os/sites.py`: read +
validate the YAML if present, else fall back to the in-code default so a
fresh clone and CI boot without any file on disk.

The schema is `extra="forbid"` + `frozen=True`: same YAML in → same
profiles out, which is the determinism contract the Phase 8.B-bis shadow
harness depends on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from swarm_core.messages import AnomalyKind

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "infra" / "config" / "autonomy.yaml"
)

_STRICT = ConfigDict(extra="forbid", frozen=True)

# Canonical Phase 7.B tuning — the field defaults below double as the
# `default` profile and as the back-compat values re-exported by
# `swarm_os.autonomy` (AUTO_VERIFY_FLOOR & friends). Keep the literals
# here; `test_autonomy_8b` pins the autonomy-module constants to them.


class AutonomyProfile(BaseModel):
    """Deterministic thresholds for one scenario class.

    Field semantics mirror the Phase 7.B rules verbatim:
      * ``verify_floor`` / ``verify_debounce_s``   — R1 auto-VERIFY.
      * ``escalate_floor`` / ``escalate_idle_s``   — R2 auto-ESCALATE.
      * ``dismiss_ceil`` / ``dismiss_stale_s``     — R3 auto-DISMISS.
    """

    model_config = _STRICT
    verify_floor: float = Field(0.50, ge=0.0, le=1.0)
    verify_debounce_s: float = Field(2.0, ge=0.0)
    escalate_floor: float = Field(0.80, ge=0.0, le=1.0)
    escalate_idle_s: float = Field(10.0, ge=0.0)
    dismiss_ceil: float = Field(0.30, ge=0.0, le=1.0)
    dismiss_stale_s: float = Field(30.0, ge=0.0)

    @model_validator(mode="after")
    def _check_band(self) -> AutonomyProfile:
        """The dismiss ceiling must sit at or below the verify floor.

        An inverted band (``dismiss_ceil > verify_floor``) would let a
        single PENDING anomaly satisfy both R1 and R3 — an ambiguous
        decision the deterministic engine must never face. Fail loudly at
        config-load time, not at decision time.
        """

        if self.dismiss_ceil > self.verify_floor:
            raise ValueError(
                "dismiss_ceil must be <= verify_floor "
                f"(got dismiss_ceil={self.dismiss_ceil}, "
                f"verify_floor={self.verify_floor})"
            )
        return self


class AutonomyConfig(BaseModel):
    """Named per-scenario profiles + the kind→profile routing table."""

    model_config = _STRICT
    default: AutonomyProfile = Field(default_factory=AutonomyProfile)
    profiles: dict[str, AutonomyProfile] = Field(default_factory=dict)
    kind_to_profile: dict[AnomalyKind, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_routing(self) -> AutonomyConfig:
        """Every routed profile name must resolve to a defined profile."""

        unknown = {
            name for name in self.kind_to_profile.values() if name not in self.profiles
        }
        if unknown:
            raise ValueError(
                f"kind_to_profile references undefined profiles: {sorted(unknown)}"
            )
        return self

    def profile_name_for(self, kind: AnomalyKind) -> str:
        """The profile name that applies to ``kind`` (``"default"`` if unmapped)."""

        name = self.kind_to_profile.get(kind)
        return name if name is not None else "default"

    def profile_for(self, kind: AnomalyKind) -> AutonomyProfile:
        """The threshold profile that applies to ``kind``.

        Falls back to ``default`` for any kind without an explicit route
        (e.g. ``AnomalyKind.UNKNOWN``) so the engine always has thresholds.
        """

        name = self.kind_to_profile.get(kind)
        if name is not None:
            return self.profiles[name]  # _check_routing guarantees presence
        return self.default


def _builtin_autonomy_config() -> AutonomyConfig:
    """In-code default that keeps CI green when the YAML is absent.

    The ``wildfire`` profile and the ``default`` fallback both equal the
    Phase 7.B constants verbatim (pinned by ``test_autonomy_8b``) so the
    Phase 7.B unit + integration suites stay green unchanged. ``intrusion``
    and ``search`` carry deliberately distinct tuning — intrusion raises
    the escalate bar so the operator owns calling it in; search lowers the
    dismiss ceiling and lengthens the stale window so a faint heat-spot
    that may be a person is not auto-dismissed.
    """

    wildfire = AutonomyProfile()  # == the Phase 7.B constants
    intrusion = AutonomyProfile(
        verify_floor=0.55,
        verify_debounce_s=3.0,
        escalate_floor=0.85,
        escalate_idle_s=15.0,
        dismiss_ceil=0.30,
        dismiss_stale_s=30.0,
    )
    search = AutonomyProfile(
        verify_floor=0.45,
        verify_debounce_s=2.0,
        escalate_floor=0.80,
        escalate_idle_s=10.0,
        dismiss_ceil=0.20,
        dismiss_stale_s=45.0,
    )
    return AutonomyConfig(
        default=AutonomyProfile(),
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


def load_autonomy_config(*, config_path: Path | None = None) -> AutonomyConfig:
    """Load + validate `infra/config/autonomy.yaml` to an `AutonomyConfig`.

    Falls back to `_builtin_autonomy_config()` when the file is absent so a
    fresh clone boots. YAML parse errors raise `yaml.YAMLError`; schema or
    band/routing violations raise `pydantic.ValidationError` — both are
    intentionally loud (CLAUDE.md root-cause discipline: no silent
    failure-swallowing).
    """

    path = config_path or DEFAULT_CONFIG_PATH
    if path.is_file():
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return AutonomyConfig.model_validate(raw)
    return _builtin_autonomy_config()


__all__ = (
    "DEFAULT_CONFIG_PATH",
    "AutonomyConfig",
    "AutonomyProfile",
    "load_autonomy_config",
)
