from __future__ import annotations

from architec.backend_llm_failover import (
    FailoverCandidate,
    FailoverPolicy,
    FailoverTracker,
)


def test_failover_tracker_suspends_after_threshold_and_recovers() -> None:
    tracker = FailoverTracker()
    policy = FailoverPolicy(
        transport_failures_before_switch=2,
        parse_failures_before_switch=1,
        cooldown_sec=30,
    )
    first = FailoverCandidate(key="first")
    second = FailoverCandidate(key="second")

    tracker.record_transport_failure("first", policy=policy, now=100.0)
    ordered = tracker.ordered_candidates([first, second], policy=policy, now=100.0)
    assert [item.key for item in ordered] == ["second", "first"]

    tracker.record_transport_failure("first", policy=policy, now=101.0)
    ordered = tracker.ordered_candidates([first, second], policy=policy, now=101.0)
    assert [item.key for item in ordered] == ["second", "first"]

    ordered = tracker.ordered_candidates([first, second], policy=policy, now=132.0)
    assert [item.key for item in ordered] == ["first", "second"]


def test_failover_tracker_parse_failure_suspends_immediately() -> None:
    tracker = FailoverTracker()
    policy = FailoverPolicy(
        transport_failures_before_switch=3,
        parse_failures_before_switch=1,
        cooldown_sec=20,
    )
    first = FailoverCandidate(key="first")
    second = FailoverCandidate(key="second")

    tracker.record_parse_failure("first", policy=policy, now=50.0)
    ordered = tracker.ordered_candidates([first, second], policy=policy, now=50.0)
    assert [item.key for item in ordered] == ["second", "first"]
