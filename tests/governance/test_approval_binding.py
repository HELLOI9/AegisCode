# tests/governance/test_approval_binding.py
"""Dispatcher-level unit tests for approval fingerprint binding.

execute_approved(action, ctx, approved_fp=...) must:
  - run the tool when the current action still matches the approved fingerprint,
  - refuse (fail closed, SUPERSEDED) when the action changed since approval,
  - preserve the pre-existing 2-arg contract (approved_fp defaults to None => no
    re-validation) so callers/tests that never bound a fingerprint still work.
"""
from types import SimpleNamespace

from aegiscode.governance.dispatcher import Dispatcher
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import PolicyEngine, GovernanceVerdict
from aegiscode.governance.approval import fingerprint
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult
from aegiscode.protocol.action import Action


class SpyCmd:
    """A run_command tool that records every execution (no path args → no fence)."""
    name = "run_command"

    def __init__(self):
        self.calls = []

    def run(self, arguments, ctx):
        self.calls.append(arguments)
        return ToolResult(tool="run_command", status="success", summary="ran")


def _disp(tmp_path, tool):
    reg = ToolRegistry(); reg.register(tool)
    eng = PolicyEngine([], default_fn=lambda a, c: GovernanceVerdict(Decision.ALLOW, "D", "d"))
    return Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(tmp_path), sensitive_patterns=[]))


def test_execute_approved_same_fingerprint_runs(tmp_path):
    tool = SpyCmd()
    d = _disp(tmp_path, tool)
    action = Action(tool="run_command", arguments={"command": "pip install x"})
    fp = fingerprint(action)

    r = d.execute_approved(action, SimpleNamespace(), approved_fp=fp)

    assert r.status == "success"
    assert tool.calls == [{"command": "pip install x"}]  # ran exactly once


def test_execute_approved_changed_fingerprint_superseded(tmp_path):
    tool = SpyCmd()
    d = _disp(tmp_path, tool)
    # Approval was granted for action A ...
    approved = Action(tool="run_command", arguments={"command": "pip install x"})
    approved_fp = fingerprint(approved)
    # ... but a DIFFERENT action A' reaches execution.
    changed = Action(tool="run_command", arguments={"command": "pip install evil"})

    r = d.execute_approved(changed, SimpleNamespace(), approved_fp=approved_fp)

    assert r.status == "denied"
    assert r.category == "POLICY_DENIED"
    assert r.artifacts.get("superseded") is True
    assert tool.calls == []  # the modified action MUST NOT execute (fail closed)


def test_execute_approved_no_fingerprint_is_backward_compatible(tmp_path):
    """Legacy 2-arg call (no bound fingerprint) still executes as before."""
    tool = SpyCmd()
    d = _disp(tmp_path, tool)
    action = Action(tool="run_command", arguments={"command": "pip install x"})

    r = d.execute_approved(action, SimpleNamespace())

    assert r.status == "success"
    assert tool.calls == [{"command": "pip install x"}]
