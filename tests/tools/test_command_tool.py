# tests/tools/test_command_tool.py
from types import SimpleNamespace
from aegiscode.tools.command_tool import RunCommandTool

def _ctx(tmp_path): return SimpleNamespace(workspace_root=str(tmp_path))

def test_runs_echo(tmp_path):
    r = RunCommandTool(["echo"], [], 5, 65536).run({"command":"echo hello"}, _ctx(tmp_path))
    assert r.status == "success" and "hello" in r.detail_for_llm

def test_nonzero_exit_is_failure(tmp_path):
    r = RunCommandTool(["python"], [], 5, 65536).run(
        {"command":"python -c \"import sys;sys.exit(3)\""}, _ctx(tmp_path))
    # note: this tool executes argv directly; governance would have blocked python -c upstream.
    assert r.exit_code == 3 and r.status == "failure"

def test_timeout_maps_to_timeout(tmp_path):
    r = RunCommandTool(["python"], [], 1, 65536).run(
        {"command":"python -c \"import time;time.sleep(5)\""}, _ctx(tmp_path))
    assert r.category == "TIMEOUT"
