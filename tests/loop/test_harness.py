# tests/loop/test_harness.py
from tests.helpers import make_harness
from aegiscode.loop.termination import TerminationReason


def test_demo1_dangerous_command_denied(tmp_path):
    # MockLLM asks to run "rm -rf /" then finish
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_command","arguments":{"command":"rm -rf /"}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)
    h.run("do something")
    assert spy.command_executions == 0                 # never executed
    assert any(e["event_type"] == "GOVERNANCE_DECISION" and e["decision"] == "DENY"
               for e in spy.audit_events)
    # DENY must NOT emit a TOOL_EXECUTED event for the run_command action —
    # nothing ran, so auditing an execution would corrupt the record.
    denied_step = next(
        e["step_index"] for e in spy.audit_events
        if e["event_type"] == "GOVERNANCE_DECISION" and e.get("decision") == "DENY"
    )
    assert not any(
        e["event_type"] == "TOOL_EXECUTED" and e["step_index"] == denied_step
        for e in spy.audit_events
    ), "DENY step must have no TOOL_EXECUTED event"
    # DENY feeds back POLICY_DENIED at that step.
    assert any(
        e["event_type"] == "FEEDBACK" and e.get("category") == "POLICY_DENIED"
        and e["step_index"] == denied_step
        for e in spy.audit_events
    )


def test_finish_rejected_continues_to_max_steps(tmp_path):
    # LLM always emits finish, but final_verifier returns False → FINISH_REJECTED
    # is fed back as FEEDBACK and the loop continues until MAX_STEPS.
    h, spy = make_harness(
        tmp_path,
        scripted=['{"tool":"finish","arguments":{}}'] * 10,
        final_ok=False,
    )
    h.config.limits.max_steps = 3
    reason = h.run("try to finish")
    assert reason == TerminationReason.MAX_STEPS
    assert any(
        e["event_type"] == "FEEDBACK" and e.get("category") == "FINISH_REJECTED"
        for e in spy.audit_events
    )
    # FINISH_REJECTED is never a terminal return reason.
    assert not any(
        e["event_type"] == "TERMINATION" and e.get("reason") == "FINISH_REJECTED"
        for e in spy.audit_events
    )


def test_demo2_failure_feedback_changes_action(tmp_path):
    # round1 write bad, round2 run_tests (fail), round3 write different,
    # round4 run_tests (pass), round5 finish
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"write_file","arguments":{"path":"src/m.py","content":"def f():\\n    return 0\\n"}}',
        '{"tool":"run_tests","arguments":{}}',
        '{"tool":"write_file","arguments":{"path":"src/m.py","content":"def f():\\n    return 1\\n"}}',
        '{"tool":"run_tests","arguments":{}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True, fail_first_test=True)
    reason = h.run("fix f")
    # The ACTUAL failure signal from round2 must reach round3's messages —
    # no "fail" substring escape hatch (that matched POLICY_DENIED "fail-closed"
    # back when run_tests was wrongly DENied).
    assert any("TEST_FAILURE" in m for m in spy.messages_at_round(3))
    # run_tests actually EXECUTED (the sensor ran, was not denied) — twice:
    # round2 (fail) and round4 (pass).
    assert spy.run_tests_executions >= 2
    # round2 produced a genuine TEST_FAILURE feedback event, not POLICY_DENIED.
    assert any(
        e["event_type"] == "FEEDBACK" and e.get("category") == "TEST_FAILURE"
        for e in spy.audit_events
    )
    assert spy.action_at(3) != spy.action_at(1)        # action changed
    assert reason == TerminationReason.COMPLETED        # decided by final_verifier, not MockLLM


def test_internal_error_on_unexpected_exception(tmp_path):
    # An unexpected exception inside the per-turn body must not crash the caller:
    # the loop audits a TERMINATION/INTERNAL_ERROR and returns INTERNAL_ERROR.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)

    class _Boom:
        def dispatch(self, action, ctx):
            raise RuntimeError("boom")

    h.dispatcher = _Boom()
    reason = h.run("trigger error")
    assert reason == TerminationReason.INTERNAL_ERROR
    assert any(
        e["event_type"] == "TERMINATION" and e.get("reason") == "INTERNAL_ERROR"
        for e in spy.audit_events
    )


def test_cancel_check_returns_cancelled(tmp_path):
    # A cancel_check that trips at the top of the loop → run() returns CANCELLED
    # and audits it, without executing any tools.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)

    calls = {"n": 0}

    def cancel_check() -> bool:
        calls["n"] += 1
        return calls["n"] >= 1  # cancel on the first check

    h.cancel_check = cancel_check
    reason = h.run("cancel me")
    assert reason == TerminationReason.CANCELLED
    assert any(
        e["event_type"] == "TERMINATION" and e.get("reason") == "CANCELLED"
        for e in spy.audit_events
    )
    assert spy.command_executions == 0
