# tests/loop/test_approval_binding.py
"""Loop-level tests: approval is bound to the action's fingerprint.

The harness captures ``approved_fp = fingerprint(action)`` at the moment approval
is REQUESTED (before the resolver runs) and re-validates the about-to-run action
against it before executing. So an approval granted for action A does NOT
authorize a different action A':
  - unchanged action after approval  -> executes exactly once (no false supersede)
  - action changed after approval     -> SUPERSEDED, tool never runs, re-judged

To make the "action changed after approval" case real and in-process we use a
resolver that mutates the action object between capture and execution (models a
plan drift / async-resume divergence). No resolver-contract change is needed:
the harness already captured the fingerprint of the ORIGINAL action.
"""
from tests.helpers import make_harness
from aegiscode.loop.termination import TerminationReason


def _step_of(spy, decision):
    return next(
        e["step_index"] for e in spy.audit_events
        if e["event_type"] == "GOVERNANCE_DECISION" and e.get("decision") == decision
    )


def test_binding_executes_on_match(tmp_path):
    # pip install → REQUIRE_APPROVAL; resolver approves WITHOUT changing the action.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_command","arguments":{"command":"pip install x"}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)
    h.approval_resolver = lambda action, verdict: True

    reason = h.run("install a dep")

    assert spy.command_executions == 1                 # the approved action ran once
    assert reason == TerminationReason.COMPLETED
    # APPROVAL_DECIDED APPROVED recorded, and the command step has a TOOL_EXECUTED.
    assert any(
        e["event_type"] == "APPROVAL_DECIDED" and e.get("state") == "APPROVED"
        for e in spy.audit_events
    )
    app_step = _step_of(spy, "REQUIRE_APPROVAL")
    assert any(
        e["event_type"] == "TOOL_EXECUTED" and e["step_index"] == app_step
        for e in spy.audit_events
    )


def test_supersede_on_change_does_not_execute(tmp_path):
    # pip install x → REQUIRE_APPROVAL. The resolver approves but MUTATES the
    # action to a different command, so the action that reaches execute differs
    # from the one whose fingerprint was approved.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_command","arguments":{"command":"pip install x"}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)

    def mutating_resolver(action, verdict):
        # divergence introduced AFTER the harness captured the approved fingerprint
        action.arguments["command"] = "pip install evil"
        return True

    h.approval_resolver = mutating_resolver

    reason = h.run("install a dep")

    # The modified action MUST NOT execute (fail closed).
    assert spy.command_executions == 0
    # The supersede is recorded on the approval decision.
    assert any(
        e["event_type"] == "APPROVAL_DECIDED" and e.get("state") == "SUPERSEDED"
        for e in spy.audit_events
    )
    # No TOOL_EXECUTED for the superseded approval step — nothing ran.
    app_step = _step_of(spy, "REQUIRE_APPROVAL")
    assert not any(
        e["event_type"] == "TOOL_EXECUTED" and e["step_index"] == app_step
        for e in spy.audit_events
    ), "superseded action must not emit TOOL_EXECUTED"
    # It did NOT silently pass: the step is fed back as a failure (not SUCCESS),
    # so the loop re-judges on the next turn rather than treating it as done.
    assert any(
        e["event_type"] == "FEEDBACK" and e["step_index"] == app_step
        and e.get("category") not in (None, "SUCCESS")
        for e in spy.audit_events
    )
    # The loop continued and reached the (unmutated) finish afterwards.
    assert reason == TerminationReason.COMPLETED


def test_rejected_action_not_executed(tmp_path):
    # Non-regression: a rejected approval never executes the tool.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_command","arguments":{"command":"pip install x"}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)
    h.approval_resolver = lambda action, verdict: False

    h.run("install a dep")

    assert spy.command_executions == 0
    assert any(
        e["event_type"] == "APPROVAL_DECIDED" and e.get("state") == "REJECTED"
        for e in spy.audit_events
    )


def test_allow_path_unaffected_by_binding(tmp_path):
    # Non-regression: a normal ALLOW action (run_tests sensor) is unaffected.
    h, spy = make_harness(tmp_path, scripted=[
        '{"tool":"run_tests","arguments":{}}',
        '{"tool":"finish","arguments":{}}',
    ], final_ok=True)

    reason = h.run("run the tests")

    assert spy.run_tests_executions == 1
    assert reason == TerminationReason.COMPLETED
