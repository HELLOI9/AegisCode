from pydantic import BaseModel
from typing import Any

class ToolResult(BaseModel):
    tool: str
    status: str                       # success|failure|denied|error
    summary: str
    category: str | None = None
    detail_for_llm: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    truncated: bool = False
    artifacts: dict[str, Any] = {}
