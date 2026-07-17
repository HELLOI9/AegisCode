# aegiscode/tools/run_tests_tool.py
import subprocess, shlex
from aegiscode.tools.result import ToolResult

class RunTestsTool:
    name = "run_tests"
    description = "Run the project's configured test command (the objective feedback sensor)."
    parameters = {}  # takes no arguments; uses configured test_command
    def __init__(self, test_command, timeout_sec, output_max_bytes):
        self.cmd, self.timeout, self.max_bytes = test_command, timeout_sec, output_max_bytes
    def run(self, arguments, ctx):
        try:
            p = subprocess.run(shlex.split(self.cmd), shell=False, cwd=ctx.workspace_root,
                               capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(tool=self.name, status="failure", category="TIMEOUT", summary="tests timed out")
        out = (p.stdout + p.stderr)[: self.max_bytes]
        return ToolResult(tool=self.name, status="success" if p.returncode==0 else "failure",
                          summary=f"tests exit {p.returncode}", detail_for_llm=out, exit_code=p.returncode)
