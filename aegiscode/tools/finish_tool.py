# aegiscode/tools/finish_tool.py
from aegiscode.tools.result import ToolResult

class FinishTool:
    name = "finish"
    description = "Declare the task complete. Only accepted after pytest objectively passes (final verifier re-runs it)."
    parameters = {}
    def run(self, arguments, ctx):
        return ToolResult(tool="finish", status="success",
                          summary="agent requested finish", artifacts={"finish": True})
