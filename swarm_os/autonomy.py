"""Phase 7.B — deterministic autonomy baseline.

Decides VERIFY / ESCALATE / DISMISS on anomalies surfacing in the three
owner-land scenarios (wildfire / intrusion / search). Three rules, no
configuration — the per-scenario thresholds belong to Phase 8.B.

  * R1 (auto-VERIFY)   — PENDING + confidence >= AUTO_VERIFY_FLOOR + aged
                         >= AUTO_VERIFY_DEBOUNCE_S + no in-flight VERIFY
                         on the same anomaly + hold_patrol off.
  * R2 (auto-ESCALATE) — VERIFIED + confidence >= AUTO_ESCALATE_FLOOR +
                         idle >= AUTO_ESCALATE_IDLE_S + no operator
                         ESCALATE/DISMISS already in flight.
  * R3 (auto-DISMISS)  — PENDING + confidence < AUTO_DISMISS_CEIL +
                         aged >= AUTO_DISMISS_STALE_S.

`tick(state, now)` is pure: it inspects `state.anomalies` +
`state.commands` and returns a list of `AutonomyDecision` records. The
coordinator translates each decision into an `OperatorCommand(source=
"autonomy", operator_id=AUTONOMY_OPERATOR_ID, …)` and dispatches via
`command_submit()`. Reusing the operator command bus means autonomy
inherits the existing policy gate (geofence / battery / link / weather),
the existing audit log, the existing event detector, and the existing
MissionView lifecycle — no parallel autonomy plumbing.

CLAUDE.md anti-overreach §10: autonomy that isn't verifiable is
forbidden. Every decision lands in `state.commands` (audit), emits a
WS frame (UI), and persists through the repository (DB) — same path
operator commands take, just with `source="autonomy"`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from swarm_core.messages import (
    AnomalyState,
    AnomalyView,
    CommandStatus,
    OperatorAction,
    OperatorCommand,
)

if TYPE_CHECKING:  # pragma: no cover
    from swarm_os.state import SwarmState

# ── R1 (auto-VERIFY) ─────────────────────────────────────────────────────────
AUTO_VERIFY_FLOOR = 0.50  # confidence at/above which we auto-VERIFY
AUTO_VERIFY_DEBOUNCE_S = 2.0  # PENDING age before R1 may fire

# ── R2 (auto-ESCALATE) ───────────────────────────────────────────────────────
AUTO_ESCALATE_FLOOR = 0.80  # confidence at/above which we auto-ESCALATE
AUTO_ESCALATE_IDLE_S = 10.0  # VERIFIED idle time before R2 may fire

# ── R3 (auto-DISMISS) ────────────────────────────────────────────────────────
AUTO_DISMISS_CEIL = 0.30  # confidence below which we auto-DISMISS
AUTO_DISMISS_STALE_S = 30.0  # PENDING age before R3 may fire

# Non-terminal lifecycle states — used to spot commands "already in flight"
# against an anomaly so autonomy doesn't double-submit.
_NON_TERMINAL_STATUSES = frozenset(
    {CommandStatus.SUBMITTED, CommandStatus.ACCEPTED, CommandStatus.IN_FLIGHT}
)


@dataclass(frozen=True)
class AutonomyDecision:
    """A single autonomy verdict ready to become an `OperatorCommand`.

    The coordinator is responsible for translation + dispatch. Keeping
    this as a frozen dataclass means the autonomy module itself is
    side-effect-free and trivially testable.
    """

    anomaly_id: str
    action: OperatorAction
    rule: str  # "R1" | "R2" | "R3" — appears in audit + tests
    confidence: float


def tick(state: SwarmState, now: datetime) -> list[AutonomyDecision]:
    """Return one decision per anomaly that satisfies a rule this tick.

    Idempotency: once a decision is recorded as an `OperatorCommand` in
    `state.commands`, the corresponding anomaly transition takes effect
    on the same `_refresh` cycle, so the same rule cannot fire twice on
    the same anomaly. The `_command_in_flight` guard additionally blocks
    rule firing while an operator-issued command is in flight on the
    same target.
    """

    if not state.autonomy_enabled:
        return []

    decisions: list[AutonomyDecision] = []
    for anomaly in state.anomalies.values():
        decision = _decide(anomaly, state, now)
        if decision is not None:
            decisions.append(decision)
    return decisions


def _decide(
    anomaly: AnomalyView, state: SwarmState, now: datetime
) -> AutonomyDecision | None:
    """Apply R1 → R3 in order; first match wins.

    The rules are mutually exclusive on a single anomaly: R1 fires only
    on PENDING + confidence >= 0.50, R3 fires only on PENDING + confidence
    < 0.30, R2 fires only on VERIFIED. The 0.30-0.50 PENDING band is
    intentionally a no-op — Phase 8.B will widen R1's coverage.
    """

    if anomaly.state == AnomalyState.PENDING:
        if (
            anomaly.confidence >= AUTO_VERIFY_FLOOR
            and not state.hold_patrol
            and _aged(anomaly, now) >= AUTO_VERIFY_DEBOUNCE_S
            and not _command_in_flight(state, anomaly.id, OperatorAction.VERIFY)
        ):
            return AutonomyDecision(
                anomaly_id=anomaly.id,
                action=OperatorAction.VERIFY,
                rule="R1",
                confidence=anomaly.confidence,
            )
        if (
            anomaly.confidence < AUTO_DISMISS_CEIL
            and _aged(anomaly, now) >= AUTO_DISMISS_STALE_S
            and not _command_in_flight(state, anomaly.id, OperatorAction.DISMISS)
        ):
            return AutonomyDecision(
                anomaly_id=anomaly.id,
                action=OperatorAction.DISMISS,
                rule="R3",
                confidence=anomaly.confidence,
            )
        return None

    if anomaly.state == AnomalyState.VERIFIED:
        if (
            anomaly.confidence >= AUTO_ESCALATE_FLOOR
            and _aged(anomaly, now) >= AUTO_ESCALATE_IDLE_S
            and not _command_in_flight(state, anomaly.id, OperatorAction.ESCALATE)
            and not _command_in_flight(state, anomaly.id, OperatorAction.DISMISS)
        ):
            return AutonomyDecision(
                anomaly_id=anomaly.id,
                action=OperatorAction.ESCALATE,
                rule="R2",
                confidence=anomaly.confidence,
            )
        return None

    return None


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
