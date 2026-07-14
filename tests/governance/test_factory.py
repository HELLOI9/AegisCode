# tests/governance/test_factory.py
"""
TDD tests for aegiscode.governance.factory.
Write FIRST — all must fail (ImportError / AttributeError) before factory.py exists.
"""
from types import SimpleNamespace

import pytest

from aegiscode.config.schema import AegisConfig, Decision
from aegiscode.governance.engine import GovernanceVerdict
from aegiscode.governance.factory import (
    build_default_fn,
    build_dispatcher,
    build_engine,
    build_path_config,
)
from aegiscode.protocol.action import Action
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult


# ---------------------------------------------------------------------------
# Shared helpers / spy tools
# ---------------------------------------------------------------------------

def _ctx():
    return SimpleNamespace()


class _SpyTool:
    """Records every call to run(); never actually does anything."""

    def __init__(self, name: str):
        self.name = name
        self.executed: list[dict] = []

    def run(self, arguments, ctx):
        self.executed.append(arguments)
        return ToolResult(tool=self.name, status="success", summary="spy-ran")


def _registry(*tools):
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


# ---------------------------------------------------------------------------
# build_path_config
# ---------------------------------------------------------------------------

def test_build_path_config_workspace_root():
    cfg = AegisConfig()
    pc = build_path_config(cfg)
    assert pc.workspace_root == cfg.workspace.root


def test_build_path_config_sensitive_patterns():
    cfg = AegisConfig()
    pc = build_path_config(cfg)
    assert pc.sensitive_patterns == cfg.governance.sensitive_file_patterns


# ---------------------------------------------------------------------------
# build_engine
# ---------------------------------------------------------------------------

def test_build_engine_returns_policy_engine():
    from aegiscode.governance.engine import PolicyEngine

    cfg = AegisConfig()
    eng = build_engine(cfg)
    assert isinstance(eng, PolicyEngine)
    assert eng.rules == []


# ---------------------------------------------------------------------------
# build_default_fn — unit tests for each tier
# ---------------------------------------------------------------------------

def test_default_fn_run_command_pip_install_requires_approval():
    """pip install x → CMD_RULE match → REQUIRE_APPROVAL (baked-in rule)."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="run_command", arguments={"command": "pip install requests"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.REQUIRE_APPROVAL


def test_default_fn_run_command_pytest_allowed():
    """pytest -q → not in dangerous rules, in allowlist → ALLOW."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="run_command", arguments={"command": "pytest -q"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.ALLOW


def test_default_fn_run_command_rm_rf_denied():
    """rm -rf / → argv0 'rm' not in allowlist → DENY."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="run_command", arguments={"command": "rm -rf /"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.DENY


def test_default_fn_read_file_allows():
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="read_file", arguments={"path": "src/foo.py"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.ALLOW
    assert verdict.rule_id == "TIER_READONLY"


def test_default_fn_list_files_allows():
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    verdict = fn(Action(tool="list_files", arguments={}), _ctx())
    assert verdict.decision == Decision.ALLOW
    assert verdict.rule_id == "TIER_READONLY"


def test_default_fn_search_text_allows():
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    verdict = fn(Action(tool="search_text", arguments={"query": "foo"}), _ctx())
    assert verdict.decision == Decision.ALLOW
    assert verdict.rule_id == "TIER_READONLY"


def test_default_fn_write_file_allowlisted_dir_allows():
    """write_file to src/x.py → under write_allowlist_dirs → ALLOW."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="write_file", arguments={"path": "src/foo.py", "content": "x"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.ALLOW
    assert verdict.rule_id == "TIER_WRITE_ALLOWLISTED"


def test_default_fn_write_file_tests_dir_allows():
    """write_file to tests/x.py → under write_allowlist_dirs → ALLOW."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="write_file", arguments={"path": "tests/test_foo.py", "content": "x"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.ALLOW
    assert verdict.rule_id == "TIER_WRITE_ALLOWLISTED"


def test_default_fn_write_file_outside_allowlist_requires_approval():
    """write_file to config/x.py → NOT in write_allowlist_dirs → REQUIRE_APPROVAL."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    action = Action(tool="write_file", arguments={"path": "config/x.py", "content": "y"})
    verdict = fn(action, _ctx())
    assert verdict.decision == Decision.REQUIRE_APPROVAL
    assert verdict.rule_id == "TIER_WRITE"


def test_default_fn_finish_allows():
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    verdict = fn(Action(tool="finish", arguments={}), _ctx())
    assert verdict.decision == Decision.ALLOW
    assert verdict.rule_id == "TIER_FINISH"


def test_default_fn_unknown_tool_denies():
    """Catch-all: unknown tool → DENY via TIER_DEFAULT."""
    cfg = AegisConfig()
    fn = build_default_fn(cfg)
    verdict = fn(Action(tool="do_something_weird", arguments={}), _ctx())
    assert verdict.decision == Decision.DENY
    assert verdict.rule_id == "TIER_DEFAULT"


# ---------------------------------------------------------------------------
# Integration tests through Dispatcher.dispatch (M2 review requirement)
# ---------------------------------------------------------------------------

def test_dispatch_rm_rf_denied_no_exec(tmp_path):
    """
    run_command 'rm -rf /' MUST be denied via the factory-wired command pipeline.
    The spy tool must never execute.
    """
    spy = _SpyTool("run_command")
    reg = _registry(spy)

    cfg = AegisConfig(workspace={"root": str(tmp_path)})
    d = build_dispatcher(cfg, reg)

    verdict, result = d.dispatch(
        Action(tool="run_command", arguments={"command": "rm -rf /"}),
        _ctx(),
    )

    assert verdict.decision == Decision.DENY
    assert result is not None
    assert result.category == "POLICY_DENIED"
    assert spy.executed == [], "tool must NOT execute when DENY"


def test_dispatch_write_outside_allowlist_requires_approval(tmp_path):
    """
    write_file to a path NOT under write_allowlist_dirs → REQUIRE_APPROVAL.
    Path fence must pass (in-workspace path), tool must not execute.
    """
    spy = _SpyTool("write_file")
    reg = _registry(spy)

    cfg = AegisConfig(workspace={"root": str(tmp_path)})
    d = build_dispatcher(cfg, reg)

    verdict, result = d.dispatch(
        Action(tool="write_file", arguments={"path": "config/x.py", "content": "y"}),
        _ctx(),
    )

    assert verdict.decision == Decision.REQUIRE_APPROVAL
    assert result is None, "result must be None on REQUIRE_APPROVAL"
    assert spy.executed == [], "tool must NOT execute when approval required"


def test_dispatch_write_allowlisted_dir_executes(tmp_path):
    """write_file to src/x.py under allowlist → ALLOW → spy tool executes."""
    # Create src/ inside tmp_path so path-fence parent check passes for new files
    (tmp_path / "src").mkdir()

    spy = _SpyTool("write_file")
    reg = _registry(spy)

    cfg = AegisConfig(workspace={"root": str(tmp_path)})
    d = build_dispatcher(cfg, reg)

    verdict, result = d.dispatch(
        Action(tool="write_file", arguments={"path": "src/new.py", "content": "pass"}),
        _ctx(),
    )

    assert verdict.decision == Decision.ALLOW
    assert result is not None
    assert result.status == "success"
    assert spy.executed == [{"path": "src/new.py", "content": "pass"}]


def test_dispatch_read_file_allows_and_executes(tmp_path):
    """read_file → TIER_READONLY ALLOW → tool executes."""
    spy = _SpyTool("read_file")
    reg = _registry(spy)

    cfg = AegisConfig(workspace={"root": str(tmp_path)})
    d = build_dispatcher(cfg, reg)

    target = tmp_path / "hello.py"
    target.write_text("print('hi')")

    verdict, result = d.dispatch(
        Action(tool="read_file", arguments={"path": "hello.py"}),
        _ctx(),
    )

    assert verdict.decision == Decision.ALLOW
    assert result is not None and result.status == "success"
    assert spy.executed != []
