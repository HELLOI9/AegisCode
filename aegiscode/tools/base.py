from typing import Protocol
from aegiscode.tools.result import ToolResult

class Tool(Protocol):
    name: str
    description: str
    parameters: dict
    def run(self, arguments: dict, ctx) -> ToolResult: ...
