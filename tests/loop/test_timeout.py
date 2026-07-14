# tests/loop/test_timeout.py
"""Wall-clock timeout stop condition (acceptance §一: "timeout" required).

decide_termination stays pure — elapsed time is injected via elapsed_sec so
tests are deterministic with NO real sleeping. The harness reads a monotonic
clock we monkeypatch, so the harness-level test also avoids sleeping.
"""
import aegiscode.loop.harness as harness_mod
from aegiscode.loop.termination import (
    decide_termination,
    LoopCounters,
    TerminationReason,
)
from tests.helpers import make_harness

# Includes the new wall_clock_timeout_sec limit.
LIM = {
    "max_steps": 25,
    "max_consecutive_failures": 5,
    "no_progress_repeat_limit": 3,
    "action_retry_limit": 3,
    "wall_clock_timeout_sec": 10,
}


def test_timeout_fires_when_elapsed_at_limit():
    # elapsed_sec >= wall_clock_timeout_sec → TIMEOUT
    assert (
        decide_termination(LoopCounters(1, 0, 0, 0), LIM, elapsed_sec=10.0)
        == TerminationReason.TIMEOUT
    )


def test_timeout_not_fired_below_limit():
    assert decide_termination(LoopCounters(1, 0, 0, 0), LIM, elapsed_sec=9.99) is None


def test_timeout_wins_over_max_steps():
    # Both timeout and max_steps breached: TIMEOUT takes precedence (hard bound).
    c = LoopCounters(step=25, consecutive_failures=0, invalid_actions=0, no_progress_hits=0)
    assert decide_termination(c, LIM, elapsed_sec=100.0) == TerminationReason.TIMEOUT


def test_timeout_wins_over_invalid_action_limit():
    # TIMEOUT is highest priority — wins even over the top counter reason.
    c = LoopCounters(step=1, consecutive_failures=0, invalid_actions=3, no_progress_hits=0)
    assert decide_termination(c, LIM, elapsed_sec=100.0) == TerminationReason.TIMEOUT


def test_no_regression_fast_run_max_steps():
    # elapsed 0 (fast run) must give the SAME reason as before the timeout param.
    c = LoopCounters(step=25, consecutive_failures=0, invalid_actions=0, no_progress_hits=0)
    assert decide_termination(c, LIM, elapsed_sec=0.0) == TerminationReason.MAX_STEPS


def test_no_regression_missing_limit_key_never_times_out():
    # A limits dict WITHOUT wall_clock_timeout_sec must never fire TIMEOUT,
    # regardless of elapsed_sec (back-compat for callers that omit the key).
    lim = {
        "max_steps": 25,
        "max_consecutive_failures": 5,
        "no_progress_repeat_limit": 3,
        "action_retry_limit": 3,
    }
    assert decide_termination(LoopCounters(1, 0, 0, 0), lim, elapsed_sec=9999.0) is None


def test_harness_stops_on_timeout_without_sleeping(tmp_path, monkeypatch):
    # A MockLLM that would otherwise loop; a tiny timeout + a fake monotonic
    # clock yields TIMEOUT with NO tools executed (fail closed).
    h, spy = make_harness(
        tmp_path,
        scripted=['{"tool":"run_command","arguments":{"command":"echo hi"}}'] * 10,
        final_ok=True,
    )
    h.config.limits.wall_clock_timeout_sec = 1

    # Fake clock: first call (loop start) = 0.0, every later call = huge → timeout.
    calls = {"n": 0}

    def fake_monotonic() -> float:
        calls["n"] += 1
        return 0.0 if calls["n"] == 1 else 1000.0

    monkeypatch.setattr(harness_mod.time, "monotonic", fake_monotonic)

    reason = h.run("loop forever")
    assert reason == TerminationReason.TIMEOUT
    assert spy.command_executions == 0  # fail closed: no action executed
    assert any(
        e["event_type"] == "TERMINATION" and e.get("reason") == "TIMEOUT"
        for e in spy.audit_events
    )
