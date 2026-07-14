# aegiscode/tools/finish_tool.py
from aegiscode.tools.result import ToolResult

class FinishTool:
    name = "finish"
    def run(self, arguments, ctx):
        return ToolResult(tool="finish", status="success",
                          summary="agent requested finish", artifacts={"finish": True})
