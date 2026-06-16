"""Phase 8.B-bis — mandatory shadow mode: decide + log + compare to a baseline.

Shadow mode runs a *candidate* decider alongside the human-baseline oracle,
records both verdicts for every anomaly without acting on either, and
reports the divergence against the Phase 8 ``< 5%`` gate. It is the
prerequisite the three-month plan calls out for Phase 10.C (the ML
anomaly-disposition classifier that *replaces* the 8.B thresholds) and
10.E (RL): every new decider must pass shadow mode before it is trusted.

Built once, reused: a `Decider` is just ``(state, now) -> dispositions`` —
the exact signature `swarm_os.autonomy.decide_all` already satisfies and the
one a future ML decider will implement. The 8.B engine is the first
candidate through the harness; the baseline is `BaselineOracle`
(`swarm_os.shadow_oracle`).

Pure + side-effect-free: nothing here touches `state.commands`, emits a WS
frame, or persists. The harness *observes* deciders; acting is the
coordinator's job and stays on the existing operator-command path
(CLAUDE.md §10 — autonomy is verifiable because every actioned decision is
already audited there).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from swarm_os.autonomy import AnomalyDisposition, AutonomyVerdict
from swarm_os.autonomy import decide_all as engine_decide_all
from swarm_os.shadow_oracle import BaselineOracle

if TYPE_CHECKING:  # pragma: no cover
    from swarm_os.autonomy_config import AutonomyConfig
    from swarm_os.shadow_oracle import OracleConfig
    from swarm_os.state import SwarmState

# The Phase 8 gate: a candidate decider must diverge from the baseline on
# fewer than this fraction of decision points.
GATE_DIVERGENCE = 0.05

# A decider proposes one disposition per anomaly for the given state + time.
Decider = Callable[["SwarmState", datetime], Sequence[AnomalyDisposition]]


def engine_decider(config: AutonomyConfig | None = None) -> Decider:
    """The Phase 8.B deterministic engine as a `Decider` (config bound)."""

    def _decide(state: SwarmState, now: datetime) -> Sequence[AnomalyDisposition]:
        return engine_decide_all(state, now, config=config)

    return _decide


def oracle_decider(config: OracleConfig | None = None) -> Decider:
    """The human-baseline oracle as a `Decider`."""

    return BaselineOracle(config).decide_all


@dataclass(frozen=True)
class ShadowEntry:
    """One anomaly's candidate-vs-baseline verdict pair — the shadow log row.

    The full decision record the Phase 8.B-bis logger keeps: both verdicts,
    both voice-clean reasons, and the profile that applied — enough to audit
    *why* a divergence happened, not just that it did.
    """

    anomaly_id: str
    profile: str
    candidate: AutonomyVerdict
    baseline: AutonomyVerdict
    candidate_reason: str
    baseline_reason: str

    @property
    def agreed(self) -> bool:
        return self.candidate == self.baseline

    @property
    def transition(self) -> str:
        """``"candidate→baseline"`` label, e.g. ``"verify→wait"`` — for the
        divergence breakdown. Only meaningful when ``not agreed``."""

        return f"{self.candidate.value}→{self.baseline.value}"


# A WAIT placeholder for an anomaly a decider failed to score at all — itself
# a divergence (the decider didn't even consider the anomaly).
_NOT_EVALUATED = "decider did not evaluate this anomaly"


def shadow_step(
    state: SwarmState,
    now: datetime,
    *,
    candidate: Decider,
    baseline: Decider,
) -> list[ShadowEntry]:
    """Compare one tick: run both deciders on the same state, pair by anomaly.

    Returns one `ShadowEntry` per anomaly seen by either decider, in a
    deterministic (sorted-by-id) order. An anomaly a decider omits is paired
    against a WAIT placeholder so the omission shows up as a divergence
    rather than silently vanishing.
    """

    cand = {d.anomaly_id: d for d in candidate(state, now)}
    base = {d.anomaly_id: d for d in baseline(state, now)}
    entries: list[ShadowEntry] = []
    for aid in sorted(set(cand) | set(base)):
        c = cand.get(aid)
        b = base.get(aid)
        # At least one is present (aid came from the union of both key sets).
        # Prefer the baseline's profile as the reference label.
        reference = b if b is not None else c
        profile = reference.profile if reference is not None else "default"
        entries.append(
            ShadowEntry(
                anomaly_id=aid,
                profile=profile,
                candidate=c.verdict if c is not None else AutonomyVerdict.WAIT,
                baseline=b.verdict if b is not None else AutonomyVerdict.WAIT,
                candidate_reason=c.reason if c is not None else _NOT_EVALUATED,
                baseline_reason=b.reason if b is not None else _NOT_EVALUATED,
            )
        )
    return entries


@dataclass(frozen=True)
class DivergenceReport:
    """Aggregate divergence of a candidate decider from the baseline oracle."""

    total: int
    diverged: int
    by_profile: dict[str, dict[str, int]]  # profile -> {"total", "diverged"}
    by_transition: dict[str, int]  # "candidate→baseline" -> count (diverged only)
    gate: float = GATE_DIVERGENCE

    @property
    def divergence_rate(self) -> float:
        return self.diverged / self.total if self.total else 0.0

    @property
    def within_gate(self) -> bool:
        """Strictly below the gate — the plan reads "< 5%", not "<= 5%"."""

        return self.divergence_rate < self.gate

    def summary(self) -> dict[str, Any]:
        """JSON-friendly view for the bench artifact."""

        return {
            "total": self.total,
            "diverged": self.diverged,
            "divergence_rate": round(self.divergence_rate, 6),
            "gate": self.gate,
            "within_gate": self.within_gate,
            "by_profile": {
                name: {
                    **counts,
                    "divergence_rate": round(
                        counts["diverged"] / counts["total"], 6
                    )
                    if counts["total"]
                    else 0.0,
                }
                for name, counts in sorted(self.by_profile.items())
            },
            "by_transition": dict(sorted(self.by_transition.items())),
        }


@dataclass
class ShadowDecisionLog:
    """The Phase 8.B-bis shadow decision logger.

    Accumulates `ShadowEntry` rows (across ticks and runs) and folds them
    into a `DivergenceReport`. Holding the raw rows — not just the running
    counts — keeps the log auditable: a divergence can be traced back to the
    anomaly, profile, and both reasons that produced it.
    """

    gate: float = GATE_DIVERGENCE
    entries: list[ShadowEntry] = field(default_factory=list)

    def record(self, entry: ShadowEntry) -> None:
        self.entries.append(entry)

    def extend(self, entries: Iterable[ShadowEntry]) -> None:
        self.entries.extend(entries)

    def report(self) -> DivergenceReport:
        diverged = sum(1 for e in self.entries if not e.agreed)
        by_profile: dict[str, dict[str, int]] = {}
        for e in self.entries:
            bucket = by_profile.setdefault(e.profile, {"total": 0, "diverged": 0})
            bucket["total"] += 1
            if not e.agreed:
                bucket["diverged"] += 1
        transitions: Counter[str] = Counter(
            e.transition for e in self.entries if not e.agreed
        )
        return DivergenceReport(
            total=len(self.entries),
            diverged=diverged,
            by_profile=by_profile,
            by_transition=dict(transitions),
            gate=self.gate,
        )


__all__ = (
    "GATE_DIVERGENCE",
    "Decider",
    "DivergenceReport",
    "ShadowDecisionLog",
    "ShadowEntry",
    "engine_decider",
    "oracle_decider",
    "shadow_step",
)
