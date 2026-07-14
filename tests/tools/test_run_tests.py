# tests/tools/test_run_tests.py
from types import SimpleNamespace
from aegiscode.tools.run_tests_tool import RunTestsTool
from aegiscode.tools.finish_tool import FinishTool

def test_runs_fixed_command(tmp_path):
    (tmp_path/"test_ok.py").write_text("def test_ok():\n    assert True\n")
    r = RunTestsTool("pytest -q", 30, 65536).run({}, SimpleNamespace(workspace_root=str(tmp_path)))
    assert r.exit_code == 0

def test_finish_flag():
    r = FinishTool().run({}, SimpleNamespace())
    assert r.artifacts.get("finish") is True
