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
    # feedback from round2 must appear in round3's messages
    assert any("TEST_FAILURE" in m or "fail" in m.lower() for m in spy.messages_at_round(3))
    assert spy.action_at(3) != spy.action_at(1)        # action changed
    assert reason == TerminationReason.COMPLETED        # decided by final_verifier, not MockLLM
