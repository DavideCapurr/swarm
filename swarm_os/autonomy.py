"""Phase 8.B — deterministic autonomy engine.

Decides one of ``VERIFY | DISMISS | ESCALATE | WAIT`` on **every** anomaly
surfacing in the three owner-land scenarios (wildfire / intrusion /
search). Phase 7.B carried three firing rules with one global tuning;
Phase 8.B completes the decision set with an explicit ``WAIT`` verdict on
every anomaly and moves the thresholds into per-scenario profiles loaded
from `infra/config/autonomy.yaml` (see `swarm_os/autonomy_config.py`).

  * R1 (auto-VERIFY)   — PENDING + confidence >= profile.verify_floor +
                         aged >= profile.verify_debounce_s + no in-flight
                         VERIFY on the same anomaly + hold_patrol off.
  * R2 (auto-ESCALATE) — VERIFIED + confidence >= profile.escalate_floor +
                         idle >= profile.escalate_idle_s + no operator
                         ESCALATE/DISMISS already in flight.
  * R3 (auto-DISMISS)  — PENDING + confidence < profile.dismiss_ceil +
                         aged >= profile.dismiss_stale_s.
  * WAIT               — every anomaly a rule does not fire on: the
                         dead band, the debounce/idle/stale windows, a
                         command already in flight, hold_patrol, and any
                         non-actionable state (VERIFYING / terminal).

`decide_all(state, now)` is pure: it inspects `state.anomalies` +
`state.commands` and returns one `AnomalyDisposition` per anomaly —
the full verdict surface the Phase 8.B-bis shadow harness will log.
`tick(state, now)` is the actionable adapter: it gates on
`state.autonomy_enabled` and returns the non-WAIT decisions as
`AutonomyDecision` records. The coordinator translates each into an
`OperatorCommand(source="autonomy", operator_id=AUTONOMY_OPERATOR_ID, …)`
and dispatches via `command_submit()`. Reusing the operator command bus
means autonomy inherits the existing policy gate (geofence / battery /
link / weather), the existing audit log, the existing event detector, and
the existing MissionView lifecycle — no parallel autonomy plumbing.

CLAUDE.md anti-overreach §10: autonomy that isn't verifiable is
forbidden. Every actioned decision lands in `state.commands` (audit),
emits a WS frame (UI), and persists through the repository (DB) — same
path operator commands take, just with `source="autonomy"`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from swarm_core.messages import (
    AnomalyState,
    AnomalyView,
    CommandStatus,
    OperatorAction,
    OperatorCommand,
)

from swarm_os.autonomy_config import (
    AutonomyConfig,
    AutonomyProfile,
    load_autonomy_config,
)

if TYPE_CHECKING:  # pragma: no cover
    from swarm_os.state import SwarmState

# Back-compat: Phase 7.B exposed the thresholds as module constants. They
# now derive from the `default` profile so a single source of truth feeds
# both the config and the legacy imports (tests pin the equality).
_DEFAULTS = AutonomyProfile()
AUTO_VERIFY_FLOOR = _DEFAULTS.verify_floor
AUTO_VERIFY_DEBOUNCE_S = _DEFAULTS.verify_debounce_s
AUTO_ESCALATE_FLOOR = _DEFAULTS.escalate_floor
AUTO_ESCALATE_IDLE_S = _DEFAULTS.escalate_idle_s
AUTO_DISMISS_CEIL = _DEFAULTS.dismiss_ceil
AUTO_DISMISS_STALE_S = _DEFAULTS.dismiss_stale_s

# Non-terminal lifecycle states — used to spot commands "already in flight"
# against an anomaly so autonomy doesn't double-submit.
_NON_TERMINAL_STATUSES = frozenset(
    {CommandStatus.SUBMITTED, CommandStatus.ACCEPTED, CommandStatus.IN_FLIGHT}
)

# Lazily-loaded process default. Tests pass `config=` to override; the
# coordinator uses this singleton so the YAML is read once per process.
_CONFIG: AutonomyConfig | None = None


def _default_config() -> AutonomyConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_autonomy_config()
    return _CONFIG


class AutonomyVerdict(str, Enum):
    """The complete Phase 8.B decision set, one per anomaly per tick."""

    VERIFY = "verify"
    ESCALATE = "escalate"
    DISMISS = "dismiss"
    WAIT = "wait"


# Map an actionable verdict to the operator intent that executes it. WAIT
# is absent on purpose — it never becomes a command.
_VERDICT_TO_ACTION: dict[AutonomyVerdict, OperatorAction] = {
    AutonomyVerdict.VERIFY: OperatorAction.VERIFY,
    AutonomyVerdict.ESCALATE: OperatorAction.ESCALATE,
    AutonomyVerdict.DISMISS: OperatorAction.DISMISS,
}

# Map an actionable verdict to its rule label (audit + Console `AUTO · R*`).
_VERDICT_TO_RULE: dict[AutonomyVerdict, str] = {
    AutonomyVerdict.VERIFY: "R1",
    AutonomyVerdict.ESCALATE: "R2",
    AutonomyVerdict.DISMISS: "R3",
}


@dataclass(frozen=True)
class AnomalyDisposition:
    """The autonomy verdict for a single anomaly this tick.

    Unlike `AutonomyDecision` (the command-bound DTO), a disposition exists
    for *every* anomaly — including the WAIT no-ops — and carries the
    `profile` that applied plus a voice-clean `reason`. This is the full
    decision record the Phase 8.B-bis shadow harness compares against a
    baseline oracle.
    """

    anomaly_id: str
    verdict: AutonomyVerdict
    rule: str | None  # "R1" | "R2" | "R3" for actionable verdicts; None for WAIT
    confidence: float
    profile: str  # the scenario profile name that supplied the thresholds
    reason: str  # confidence-bound copy — never user-controlled

    @property
    def is_actionable(self) -> bool:
        return self.verdict is not AutonomyVerdict.WAIT


@dataclass(frozen=True)
class AutonomyDecision:
    """A single actionable autonomy verdict ready to become an `OperatorCommand`.

    The coordinator is responsible for translation + dispatch. Keeping
    this as a frozen dataclass means the autonomy module itself is
    side-effect-free and trivially testable.
    """

    anomaly_id: str
    action: OperatorAction
    rule: str  # "R1" | "R2" | "R3" — appears in audit + tests
    confidence: float


def decide_all(
    state: SwarmState,
    now: datetime,
    *,
    config: AutonomyConfig | None = None,
) -> list[AnomalyDisposition]:
    """Return one `AnomalyDisposition` per anomaly — the full verdict surface.

    Pure decision logic: it does **not** gate on `state.autonomy_enabled`
    (a shadow run decides without acting). `hold_patrol`, the
    debounce/idle/stale windows, and in-flight commands all shape the
    verdict (most resolve to WAIT) rather than dropping the anomaly, so the
    record is complete for every anomaly the engine observes.
    """

    cfg = config or _default_config()
    return [_decide(anomaly, state, now, cfg) for anomaly in state.anomalies.values()]


def tick(
    state: SwarmState,
    now: datetime,
    *,
    config: AutonomyConfig | None = None,
) -> list[AutonomyDecision]:
    """Return the actionable decisions for this tick (WAIT verdicts dropped).

    Gates on `state.autonomy_enabled` — the boot-time switch on the
    deterministic baseline. Idempotency: once a decision is recorded as an
    `OperatorCommand` in `state.commands`, the corresponding anomaly
    transition takes effect on the same `_refresh` cycle, so a rule cannot
    fire twice on the same anomaly. The `_command_in_flight` guard
    additionally resolves a competing in-flight command to WAIT.
    """

    if not state.autonomy_enabled:
        return []

    decisions: list[AutonomyDecision] = []
    for disposition in decide_all(state, now, config=config):
        if not disposition.is_actionable:
            continue
        rule = disposition.rule
        assert rule is not None  # actionable verdicts always carry a rule
        decisions.append(
            AutonomyDecision(
                anomaly_id=disposition.anomaly_id,
                action=_VERDICT_TO_ACTION[disposition.verdict],
                rule=rule,
                confidence=disposition.confidence,
            )
        )
    return decisions


def _decide(
    anomaly: AnomalyView,
    state: SwarmState,
    now: datetime,
    cfg: AutonomyConfig,
) -> AnomalyDisposition:
    """Apply R1 → R3 in order for one anomaly; otherwise return WAIT.

    The rules are mutually exclusive on a single anomaly: R1 fires only on
    PENDING + confidence >= verify_floor, R3 fires only on PENDING +
    confidence < dismiss_ceil, R2 fires only on VERIFIED. The
    [dismiss_ceil, verify_floor) PENDING band, the timing windows, and
    every non-actionable state all resolve to an explicit WAIT.
    """

    profile = cfg.profile_for(anomaly.kind)
    profile_name = cfg.profile_name_for(anomaly.kind)
    conf = anomaly.confidence
    age = _aged(anomaly, now)

    def out(
        verdict: AutonomyVerdict, reason: str, rule: str | None = None
    ) -> AnomalyDisposition:
        return AnomalyDisposition(
            anomaly_id=anomaly.id,
            verdict=verdict,
            rule=rule,
            confidence=conf,
            profile=profile_name,
            reason=reason,
        )

    if anomaly.state == AnomalyState.PENDING:
        # R1 — auto-VERIFY at/above the verify floor.
        if conf >= profile.verify_floor:
            if state.hold_patrol:
                return out(AutonomyVerdict.WAIT, "patrol held by operator")
            if age < profile.verify_debounce_s:
                return out(AutonomyVerdict.WAIT, "within verify debounce window")
            if _command_in_flight(state, anomaly.id, OperatorAction.VERIFY):
                return out(AutonomyVerdict.WAIT, "verification already in flight")
            return out(
                AutonomyVerdict.VERIFY,
                f"confidence {_pct(conf)} at/above verify floor "
                f"{_pct(profile.verify_floor)}",
                rule="R1",
            )
        # R3 — auto-DISMISS below the dismiss ceiling once stale.
        if conf < profile.dismiss_ceil:
            if age < profile.dismiss_stale_s:
                return out(AutonomyVerdict.WAIT, "within dismiss stale window")
            if _command_in_flight(state, anomaly.id, OperatorAction.DISMISS):
                return out(AutonomyVerdict.WAIT, "dismissal already in flight")
            return out(
                AutonomyVerdict.DISMISS,
                f"confidence {_pct(conf)} below dismiss ceiling "
                f"{_pct(profile.dismiss_ceil)}, stale",
                rule="R3",
            )
        # Dead band: above the dismiss ceiling, below the verify floor.
        return out(
            AutonomyVerdict.WAIT,
            f"confidence {_pct(conf)} between dismiss ceiling "
            f"{_pct(profile.dismiss_ceil)} and verify floor "
            f"{_pct(profile.verify_floor)}",
        )

    if anomaly.state == AnomalyState.VERIFIED:
        # R2 — auto-ESCALATE at/above the escalate floor once idle.
        if conf < profile.escalate_floor:
            return out(
                AutonomyVerdict.WAIT,
                f"verified confidence {_pct(conf)} below escalate floor "
                f"{_pct(profile.escalate_floor)}",
            )
        if age < profile.escalate_idle_s:
            return out(AutonomyVerdict.WAIT, "within escalate idle window")
        if _command_in_flight(
            state, anomaly.id, OperatorAction.ESCALATE
        ) or _command_in_flight(state, anomaly.id, OperatorAction.DISMISS):
            return out(
                AutonomyVerdict.WAIT, "escalation or dismissal already in flight"
            )
        return out(
            AutonomyVerdict.ESCALATE,
            f"verified confidence {_pct(conf)} at/above escalate floor "
            f"{_pct(profile.escalate_floor)}",
            rule="R2",
        )

    # VERIFYING + terminal states (DISMISSED / ESCALATED / MARKED_KNOWN).
    return out(
        AutonomyVerdict.WAIT,
        f"no autonomy action in state {anomaly.state.value}",
    )


def _pct(value: float) -> str:
    """Confidence-bound percentage copy — e.g. 0.5 → ``050%`` (PDF voice)."""

    return f"{round(value * 100):03d}%"


def _aged(anomaly: AnomalyView, now: datetime) -> float:
    """Seconds since the anomaly last transitioned (`ts` is set on every state
    update by the coordinator). For PENDING anomalies that's effectively the
    detection age; for VERIFIED it's the time spent in VERIFIED."""

    delta = (now - anomaly.ts).total_seconds()
    return max(0.0, delta)


def _command_in_flight(
    state: SwarmState, anomaly_id: str, action: OperatorAction
) -> bool:
    """True if *any* non-terminal command (operator or autonomy) of `action`
    already targets this anomaly.

    Conservative on purpose: a race between an operator VERIFY and an R1
    auto-VERIFY would otherwise double-submit and double-audit. The check
    spans `source` so an in-flight autonomy command also blocks a retry
    on the same tick (idempotency within a single coordinator refresh).
    """

    target = f"anomaly:{anomaly_id}"
    for command in state.commands.values():
        if command.target != target:
            continue
        if command.action != action:
            continue
        if command.status in _NON_TERMINAL_STATUSES:
            return True
    return False


def to_command(decision: AutonomyDecision) -> OperatorCommand:
    """Build the `OperatorCommand` the coordinator will dispatch.

    Lives next to the rules so the AUTONOMY_OPERATOR_ID sentinel and
    `source="autonomy"` literal are colocated with the policy that
    emits them.
    """

    from swarm_os.command_bus import AUTONOMY_OPERATOR_ID

    return OperatorCommand(
        action=decision.action,
        target=f"anomaly:{decision.anomaly_id}",
        operator_id=AUTONOMY_OPERATOR_ID,
        source="autonomy",
        rule=decision.rule,
    )
