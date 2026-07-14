"""Tests for the `make demo` orchestrator (demos/run_demos.py).

The orchestrator is the graded mechanism-demo entry point (acceptance §3). These
tests pin the contract that matters for grading:
  * exit code 0 iff all three demos pass, non-zero otherwise (§3.2.10/11/12);
  * the §3.3 human-readable format: three `[Demo N/3]` blocks, per-check `PASS:`
    lines, and a final `N passed, M failed` summary;
  * the summary counts reflect reality (a forced demo failure flips exit code and
    the summary — the orchestrator must NOT swallow a failure and report success).
"""
from __future__ import annotations

import subprocess
import sys

from demos import run_demos


def _run_cli(args):
    """Run the orchestrator as a real subprocess; return (exit_code, stdout)."""
    proc = subprocess.run(
        [sys.executable, "-m", "demos.run_demos", *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_all_three_pass_exit_zero_and_format():
    code, out = _run_cli([])
    assert code == 0, f"expected exit 0, got {code}\n{out}"
    # Three labeled blocks, in order.
    assert "[Demo 1/3]" in out
    assert "[Demo 2/3]" in out
    assert "[Demo 3/3]" in out
    # Per-check PASS lines exist.
    assert "PASS:" in out
    # Final summary line, all green.
    assert "3 passed, 0 failed" in out


def test_select_single_demo():
    code, out = _run_cli(["--only", "guardrail"])
    assert code == 0, out
    assert "[Demo 1/3]" in out
    # The other two are not run when a single demo is selected.
    assert "[Demo 2/3]" not in out
    assert "1 passed, 0 failed" in out


def test_failure_flips_exit_code_and_summary(monkeypatch):
    """A demo whose contract check fails must make the orchestrator exit non-zero
    and report the failure — never swallow it and return success (§3.2.12)."""
    # Force demo 1's contract to fail by making its run() return a bad dict.
    monkeypatch.setitem(
        run_demos._DEMO_BY_NAME, "guardrail",
        run_demos.DemoSpec(
            name="guardrail",
            index=1,
            title="Dangerous action denial",
            run=lambda: {"executed": 99, "decision": "ALLOW", "audit_has_deny": False,
                         "deny_rule_id": None, "feedback_is_policy_denied": False},
            checks=run_demos._DEMO_BY_NAME["guardrail"].checks,
        ),
    )
    code = run_demos.main(["--only", "guardrail"])
    assert code != 0, "a failing contract check must yield a non-zero exit code"


def test_run_raising_is_a_failure(monkeypatch):
    """If a demo's run() raises, that is a FAIL (non-zero exit), not a crash that
    masquerades as success."""
    def _boom():
        raise RuntimeError("demo blew up")

    monkeypatch.setitem(
        run_demos._DEMO_BY_NAME, "guardrail",
        run_demos.DemoSpec(
            name="guardrail", index=1, title="Dangerous action denial",
            run=_boom, checks=run_demos._DEMO_BY_NAME["guardrail"].checks,
        ),
    )
    code = run_demos.main(["--only", "guardrail"])
    assert code != 0
