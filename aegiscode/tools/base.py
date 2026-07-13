from typing import Protocol
from aegiscode.tools.result import ToolResult

class Tool(Protocol):
    name: str
    def run(self, arguments: dict, ctx) -> ToolResult: ...
