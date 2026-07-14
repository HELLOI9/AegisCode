from aegiscode.feedback.classifier import classify, ProgressTracker
from aegiscode.feedback.pytest_parser import summarize_pytest
from aegiscode.tools.result import ToolResult

def test_classify_test_failure():
    tr = ToolResult(tool="run_tests", status="failure", exit_code=1, summary="x")
    assert classify(tr) == "TEST_FAILURE"

def test_classify_policy_denied():
    tr = ToolResult(tool="run_command", status="denied", category="POLICY_DENIED", summary="x")
    assert classify(tr) == "POLICY_DENIED"

def test_summarize_pytest_keeps_failed_names():
    raw = "tests/test_a.py::test_x FAILED\n" + "trace\n"*50 + "E assert 1 == 2\n"
    out = summarize_pytest(raw)
    assert "test_x" in out and "assert 1 == 2" in out and len(out.splitlines()) < 40

def test_progress_tracker_detects_repeat():
    t = ProgressTracker(window=3)
    assert t.seen("fp") is False
    assert t.seen("fp") is True
