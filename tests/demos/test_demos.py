"""Tests for the four SPEC §16.4 mechanism demos.

Each demo ships inside the top-level `demos` package (NOT under tests/), is
fully self-contained (no tests.helpers import), zero-network (MockLLM only),
and exercises a REAL governance / harness / approval mechanism. These tests
assert the exact run() contract from the task PLAN plus stronger secondary
assertions that would FAIL if the underlying mechanism were broken.
"""
from demos import (
    demo1_dangerous_denied,
    demo2_feedback_loop,
    demo3_symlink_escape,
    demo4_superseded,
)


def test_demo1():
    # Governance intercepts `rm -rf /`: DENY and the spy tool NEVER runs.
    r = demo1_dangerous_denied.run()
    assert r["executed"] == 0
    assert r["decision"] == "DENY"
    # SPEC §16.4: the DENY is recorded in the audit log as a GOVERNANCE_DECISION
    # event carrying a rule_id, and the agent receives POLICY_DENIED feedback.
    assert r["audit_has_deny"] is True
    assert r["deny_rule_id"]  # non-empty rule id
    assert r["feedback_is_policy_denied"] is True


def test_demo2():
    # Failure feedback drives an action change; final verifier proves COMPLETED.
    r = demo2_feedback_loop.run()
    assert r["completed"] and r["action_changed"]
    # The round-3 LLM context must actually contain the TEST_FAILURE feedback
    # produced by the round-2 test run (proves the feedback loop is real).
    assert r["test_failure_seen_in_round3_context"] is True


def test_demo3():
    # Path fence denies a symlink that escapes the workspace to /etc/passwd.
    r = demo3_symlink_escape.run()
    assert r["decision"] == "DENY"
    # No /etc/passwd content leaked back through the tool result.
    assert r["leaked"] is False
    # SPEC §16.4: the denial is recorded in the audit log (a GOVERNANCE_DECISION
    # event with the fence's DENY rule_id) and NO TOOL_EXECUTED event was emitted.
    assert r["audit_has_deny"] is True
    assert r["no_tool_executed"] is True


def test_demo4():
    # A changed action after approval is SUPERSEDED (re-approval required).
    r = demo4_superseded.run()
    assert r["superseded"] is True
    # The identical, still-approved action must NOT be superseded.
    assert r["identical_ok"] is True
