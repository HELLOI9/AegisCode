# tests/governance/test_fence_ctx_root.py
"""C1 regression: the path fence must anchor to the workspace the tool actually
runs in (ctx.workspace_root), NOT the config-frozen path_config.workspace_root.

On the host CLI path (`aegiscode run --workspace /home/me/project`) and on
`serve`, config.workspace.root (e.g. "/workspace") diverges from the per-task
ctx.workspace_root. When they diverge, the fence used to check a nonexistent
path under the config root (taking its "new file" branch and returning allowed),
while the tool resolved the path against the REAL workspace and could follow an
in-workspace symlink (report.txt -> .env) to read a sensitive file — re-opening
the symlink→sensitive bypass that commit b48f4a9 fixed.
"""
import os
from types import SimpleNamespace

from aegiscode.governance.dispatcher import Dispatcher
from aegiscode.governance.decision import Decision
from aegiscode.governance.engine import PolicyEngine, GovernanceVerdict
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.file_tools import ReadFileTool
from aegiscode.protocol.action import Action


def _ctx_for(workspace: str) -> SimpleNamespace:
    def resolve(p: str) -> str:
        return p if os.path.isabs(p) else os.path.join(workspace, p)

    return SimpleNamespace(
        task_id="t",
        workspace_root=workspace,
        resolve=resolve,
        snapshot=lambda abspath: None,
        write_max_bytes=1_000_000,
    )


def test_fence_uses_ctx_root_blocks_symlink_to_sensitive(tmp_path):
    """Divergent roots: config root != real task workspace. An in-workspace
    symlink report.txt -> .env must be DENIED and the secret must NOT be read."""
    ws = tmp_path / "real_ws"
    ws.mkdir()
    (ws / ".env").write_text("OPENAI_API_KEY=sk-supersecret\n")
    os.symlink(str(ws / ".env"), str(ws / "report.txt"))

    # Different, frozen config root (simulates config.workspace.root="/workspace").
    other_root = tmp_path / "config_root"
    other_root.mkdir()

    reg = ToolRegistry()
    reg.register(ReadFileTool())
    eng = PolicyEngine([], default_fn=lambda a, c: GovernanceVerdict(Decision.ALLOW, "D", "ok"))
    d = Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(other_root),
        sensitive_patterns=[".env", "*.pem", "*.key", "*credentials*"]))

    ctx = _ctx_for(str(ws))
    verdict, result = d.dispatch(Action(tool="read_file", arguments={"path": "report.txt"}), ctx)

    assert verdict.decision == Decision.DENY
    assert verdict.rule_id == "PATH_FENCE"
    assert result.status == "denied"
    assert result.category == "POLICY_DENIED"
    # Secret must never surface in the tool result.
    assert "sk-supersecret" not in str(result.__dict__)


def test_execute_approved_uses_ctx_root_blocks_symlink(tmp_path):
    """Same divergence, but through execute_approved (post-approval path)."""
    ws = tmp_path / "real_ws"
    ws.mkdir()
    (ws / ".env").write_text("OPENAI_API_KEY=sk-supersecret\n")
    os.symlink(str(ws / ".env"), str(ws / "report.txt"))

    other_root = tmp_path / "config_root"
    other_root.mkdir()

    reg = ToolRegistry()
    reg.register(ReadFileTool())
    eng = PolicyEngine([], default_fn=lambda a, c: GovernanceVerdict(Decision.ALLOW, "D", "ok"))
    d = Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(other_root),
        sensitive_patterns=[".env", "*.pem", "*.key", "*credentials*"]))

    ctx = _ctx_for(str(ws))
    result = d.execute_approved(Action(tool="read_file", arguments={"path": "report.txt"}), ctx)

    assert result.status == "denied"
    assert result.category == "POLICY_DENIED"
    assert "sk-supersecret" not in str(result.__dict__)


def test_fence_falls_back_to_pc_root_when_ctx_has_no_workspace_root(tmp_path):
    """Backward compat: when ctx lacks workspace_root, fence uses pc.workspace_root.
    A traversal escape relative to pc root must still be denied."""
    reg = ToolRegistry()
    reg.register(ReadFileTool())
    eng = PolicyEngine([], default_fn=lambda a, c: GovernanceVerdict(Decision.ALLOW, "D", "ok"))
    d = Dispatcher(reg, eng, path_config=SimpleNamespace(
        workspace_root=str(tmp_path), sensitive_patterns=[".env"]))

    # ctx without workspace_root attribute; resolve joins against tmp_path.
    ctx = SimpleNamespace(resolve=lambda p: os.path.join(str(tmp_path), p))
    verdict, result = d.dispatch(
        Action(tool="read_file", arguments={"path": "../../etc/passwd"}), ctx)

    assert verdict.decision == Decision.DENY
    assert verdict.rule_id == "PATH_FENCE"
    assert result.category == "POLICY_DENIED"
