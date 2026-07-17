# aegiscode/tools/command_tool.py
import subprocess
import shlex
from aegiscode.tools.result import ToolResult


class RunCommandTool:
    name = "run_command"
    description = "Run an allowlisted shell command (shell=False, argv, cwd locked to workspace)."
    parameters = {"command": {"type": "string", "required": True, "note": "command string; lexed + allowlist + rule governed"}}

    def __init__(self, allowlist, rules, timeout_sec, output_max_bytes):
        self.allowlist = allowlist
        self.rules = rules
        self.timeout = timeout_sec
        self.max_bytes = output_max_bytes

    def run(self, arguments, ctx):
        argv = shlex.split(arguments["command"])
        try:
            p = subprocess.run(
                argv,
                shell=False,
                cwd=ctx.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool=self.name,
                status="failure",
                category="TIMEOUT",
                summary="command timed out",
            )
        combined = p.stdout + p.stderr
        truncated = len(combined) > self.max_bytes
        out = combined[: self.max_bytes]
        status = "success" if p.returncode == 0 else "failure"
        return ToolResult(
            tool=self.name,
            status=status,
            category=None if status == "success" else "TOOL_ERROR",
            summary=f"exit {p.returncode}",
            detail_for_llm=out,
            exit_code=p.returncode,
            truncated=truncated,
        )
