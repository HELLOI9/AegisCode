# tests/governance/test_run_command_fence.py
"""C3 regression: run_command was not path-fenced. Allowlisted commands
(cat/ls) could read host files (`cat /etc/passwd`) and sensitive files
(`cat .env`) that the file-tool fence blocks, fully sidestepping the fence.

Fix has two parts:
  1. `cat` and `ls` removed from the DEFAULT command allowlist (fenced
     read_file/list_files exist for those jobs; a general file reader in the
     allowlist can always take an arbitrary path).
  2. A path fence for run_command: every path-like argv token is run through
     path_fence.check_path against the workspace the command runs in. A token
     that escapes the workspace or matches a sensitive pattern -> DENY with
     rule_id CMD_PATH_FENCE, before the command executes, in BOTH dispatch()
     and execute_approved().

These tests exercise the FENCE (using allowlisted commands carrying bad paths),
not merely the allowlist removal, plus non-regression for normal usage.
"""
from types import SimpleNamespace

from aegiscode.config.schema import AegisConfig, Governance
from aegiscode.governance.decision import Decision
from aegiscode.governance.factory import build_dispatcher
from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult
from aegiscode.protocol.action import Action


class SpyRun:
    name = "run_command"

    def __init__(self):
        self.calls = []

    def run(self, arguments, ctx):
        self.calls.append(arguments)
        return ToolResult(tool="run_command", status="success", summary="ran")


def _disp(tmp_path):
    cfg = AegisConfig()
    reg = ToolRegistry()
    spy = SpyRun()
    reg.register(spy)
    d = build_dispatcher(cfg, reg)
    return d, spy


def _ctx(tmp_path):
    return SimpleNamespace(workspace_root=str(tmp_path))


def _cmd(command):
    return Action(tool="run_command", arguments={"command": command})


# ---- default allowlist no longer contains cat/ls ------------------------
def test_default_allowlist_excludes_cat_and_ls():
    g = Governance()
    assert "cat" not in g.command_allowlist
    assert "ls" not in g.command_allowlist
    # the useful interpreters/tools stay.
    for keep in ["python", "python3", "pip", "pytest", "ruff", "mypy", "git"]:
        assert keep in g.command_allowlist


# ---- FENCE: absolute escape --------------------------------------------
def test_absolute_escape_denied_by_fence(tmp_path):
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("python /etc/passwd"), _ctx(tmp_path))
    assert v.decision == Decision.DENY
    assert v.rule_id == "CMD_PATH_FENCE"
    assert r.status == "denied" and r.category == "POLICY_DENIED"
    assert spy.calls == []  # command must NOT execute


# ---- FENCE: relative traversal escape ----------------------------------
def test_relative_escape_denied_by_fence(tmp_path):
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("python ../outside.py"), _ctx(tmp_path))
    assert v.decision == Decision.DENY
    assert v.rule_id == "CMD_PATH_FENCE"
    assert spy.calls == []


# ---- FENCE: sensitive basename with no slash ---------------------------
def test_sensitive_basename_no_slash_denied(tmp_path):
    # `.env` has no slash but matches a sensitive pattern -> fenced.
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("python .env"), _ctx(tmp_path))
    assert v.decision == Decision.DENY
    assert v.rule_id == "CMD_PATH_FENCE"
    assert spy.calls == []


def test_sensitive_glob_basename_no_slash_denied(tmp_path):
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("python key.pem"), _ctx(tmp_path))
    assert v.decision == Decision.DENY
    assert v.rule_id == "CMD_PATH_FENCE"
    assert spy.calls == []


# ---- FENCE: --opt=path form --------------------------------------------
def test_opt_equals_escape_denied(tmp_path):
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("python --config=/etc/passwd"), _ctx(tmp_path))
    assert v.decision == Decision.DENY
    assert v.rule_id == "CMD_PATH_FENCE"
    assert spy.calls == []


# ---- NON-REGRESSION: in-workspace paths / flags / subcommands -----------
def test_pytest_tests_dir_not_fenced(tmp_path):
    (tmp_path / "tests").mkdir()
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("pytest tests/"), _ctx(tmp_path))
    assert v.decision in (Decision.ALLOW, Decision.ALLOW_WITH_AUDIT)
    assert r.status == "success"
    assert spy.calls == [{"command": "pytest tests/"}]


def test_git_status_not_fenced(tmp_path):
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("git status"), _ctx(tmp_path))
    assert v.decision in (Decision.ALLOW, Decision.ALLOW_WITH_AUDIT)
    assert spy.calls == [{"command": "git status"}]


def test_pip_install_still_requires_approval_not_fence_denied(tmp_path):
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("pip install requests"), _ctx(tmp_path))
    assert v.decision == Decision.REQUIRE_APPROVAL
    assert v.rule_id != "CMD_PATH_FENCE"
    assert r is None
    assert spy.calls == []


def test_in_workspace_script_allowed_by_fence(tmp_path):
    (tmp_path / "script.py").write_text("print('hi')\n")
    d, spy = _disp(tmp_path)
    v, r = d.dispatch(_cmd("python script.py"), _ctx(tmp_path))
    assert v.decision in (Decision.ALLOW, Decision.ALLOW_WITH_AUDIT)
    assert spy.calls == [{"command": "python script.py"}]


# ---- execute_approved also fences --------------------------------------
def test_execute_approved_fences_bad_path(tmp_path):
    # `pip install /etc/passwd` would be REQUIRE_APPROVAL; even once approved
    # the fence must still block the escaping path.
    d, spy = _disp(tmp_path)
    r = d.execute_approved(_cmd("pip install /etc/passwd"), _ctx(tmp_path))
    assert r.status == "denied" and r.category == "POLICY_DENIED"
    assert spy.calls == []


def test_execute_approved_runs_when_paths_in_workspace(tmp_path):
    (tmp_path / "tests").mkdir()
    d, spy = _disp(tmp_path)
    r = d.execute_approved(_cmd("pytest tests/"), _ctx(tmp_path))
    assert r.status == "success"
    assert spy.calls == [{"command": "pytest tests/"}]
