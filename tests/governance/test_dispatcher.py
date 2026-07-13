# tests/governance/test_dispatcher.py
from types import SimpleNamespace
from aegiscode.governance.dispatcher import Dispatcher
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import PolicyEngine, GovernanceVerdict, PolicyRule
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult
from aegiscode.protocol.action import Action


class OkTool:
    name = "read_file"
    def run(self, arguments, ctx): return ToolResult(tool="read_file", status="success", summary="ok")


def _disp(tmp_path, rules=None):
    reg = ToolRegistry(); reg.register(OkTool())
    eng = PolicyEngine(rules or [], default_fn=lambda a,c: GovernanceVerdict(Decision.ALLOW,"DEFAULT","ok"))
    return Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(tmp_path), sensitive_patterns=[], readonly_tools={"read_file","list_files","search_text"}))


def test_unknown_tool_not_executed(tmp_path):
    d = _disp(tmp_path)
    verdict, result = d.dispatch(Action(tool="nope", arguments={}), SimpleNamespace())
    assert result.category == "INVALID_ACTION"


def test_path_escape_denied_before_exec(tmp_path):
    d = _disp(tmp_path)
    v, r = d.dispatch(Action(tool="read_file", arguments={"path":"../../etc/passwd"}),
                      SimpleNamespace(resolve=lambda p: p))
    assert v.decision == Decision.DENY and r.category == "POLICY_DENIED"


def test_matcher_exception_returns_internal_error(tmp_path):
    """A rule whose matcher raises must become INTERNAL_ERROR; tool must NOT execute."""
    executed = []

    class BoomTool:
        name = "write_file"
        def run(self, arguments, ctx):
            executed.append(True)
            return ToolResult(tool="write_file", status="success", summary="written")

    def exploding_matcher(action, ctx):
        raise RuntimeError("matcher bug")

    reg = ToolRegistry()
    reg.register(BoomTool())
    rules = [PolicyRule(rule_id="BOOM", matcher=exploding_matcher, decision=Decision.ALLOW, reason="n/a")]
    eng = PolicyEngine(rules, default_fn=lambda a, c: GovernanceVerdict(Decision.ALLOW, "DEFAULT", "ok"))
    d = Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(tmp_path), sensitive_patterns=[], readonly_tools=set()))

    verdict, result = d.dispatch(Action(tool="write_file", arguments={}), SimpleNamespace())
    assert result is not None
    assert result.category == "INTERNAL_ERROR"
    assert result.status == "error"
    assert len(executed) == 0, "tool must NOT execute when matcher raises"
