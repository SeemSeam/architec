from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class FailoverPolicy:
    transport_failures_before_switch: int = 2
    parse_failures_before_switch: int = 1
    cooldown_sec: float = 180.0


@dataclass(frozen=True)
class FailoverCandidate:
    key: str


@dataclass
class _CandidateState:
    transport_failures: int = 0
    parse_failures: int = 0
    suspended_until: float = 0.0
    last_failure_at: float = 0.0


@dataclass
class FailoverTracker:
    _states: dict[str, _CandidateState] = field(default_factory=dict)

    def ordered_candidates(
        self,
        candidates: Iterable[FailoverCandidate],
        *,
        policy: FailoverPolicy,
        now: float | None = None,
    ) -> list[FailoverCandidate]:
        ts = time.time() if now is None else float(now)
        ready: list[tuple[int, int, FailoverCandidate]] = []
        cooling: list[tuple[float, int, int, FailoverCandidate]] = []
        for index, candidate in enumerate(candidates):
            state = self._get_state(candidate.key, now=ts)
            if state is None:
                ready.append((0, index, candidate))
                continue
            penalty = state.transport_failures + state.parse_failures
            if state.suspended_until > ts:
                cooling.append((state.suspended_until, penalty, index, candidate))
                continue
            ready.append((penalty, index, candidate))
        ready.sort(key=lambda item: (item[0], item[1]))
        cooling.sort(key=lambda item: (item[0], item[1], item[2]))
        ordered = [candidate for _, _, candidate in ready]
        ordered.extend(candidate for _, _, _, candidate in cooling)
        return ordered

    def record_success(self, key: str) -> None:
        self._states.pop(key, None)

    def record_transport_failure(
        self,
        key: str,
        *,
        policy: FailoverPolicy,
        now: float | None = None,
    ) -> None:
        self._record_failure(
            key,
            threshold=max(1, int(policy.transport_failures_before_switch)),
            cooldown_sec=float(policy.cooldown_sec),
            failure_type="transport",
            now=now,
        )

    def record_parse_failure(
        self,
        key: str,
        *,
        policy: FailoverPolicy,
        now: float | None = None,
    ) -> None:
        self._record_failure(
            key,
            threshold=max(1, int(policy.parse_failures_before_switch)),
            cooldown_sec=float(policy.cooldown_sec),
            failure_type="parse",
            now=now,
        )

    def _record_failure(
        self,
        key: str,
        *,
        threshold: int,
        cooldown_sec: float,
        failure_type: str,
        now: float | None = None,
    ) -> None:
        ts = time.time() if now is None else float(now)
        state = self._states.setdefault(key, _CandidateState())
        if failure_type == "transport":
            state.transport_failures += 1
        else:
            state.parse_failures += 1
        state.last_failure_at = ts
        counter = (
            state.transport_failures
            if failure_type == "transport"
            else state.parse_failures
        )
        if counter >= threshold:
            state.suspended_until = ts + max(1.0, cooldown_sec)

    def _get_state(self, key: str, *, now: float | None = None) -> _CandidateState | None:
        state = self._states.get(key)
        if state is None:
            return None
        ts = time.time() if now is None else float(now)
        if state.suspended_until > 0.0 and state.suspended_until <= ts:
            self._states.pop(key, None)
            return None
        return state


_TRACKER = FailoverTracker()


def ordered_candidates(
    candidates: Iterable[FailoverCandidate],
    *,
    policy: FailoverPolicy,
) -> list[FailoverCandidate]:
    return _TRACKER.ordered_candidates(candidates, policy=policy)


def record_success(key: str) -> None:
    _TRACKER.record_success(key)


def record_transport_failure(key: str, *, policy: FailoverPolicy) -> None:
    _TRACKER.record_transport_failure(key, policy=policy)


def record_parse_failure(key: str, *, policy: FailoverPolicy) -> None:
    _TRACKER.record_parse_failure(key, policy=policy)


def reset_failover_state() -> None:
    _TRACKER._states.clear()
