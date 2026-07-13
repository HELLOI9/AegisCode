from typing import Any, Literal
from pydantic import BaseModel

class ToolResult(BaseModel):
    tool: str
    status: Literal["success", "failure", "denied", "error"]
    summary: str
    category: Literal[
        "TEST_FAILURE", "TOOL_ERROR", "POLICY_DENIED", "APPROVAL_REJECTED",
        "INVALID_ACTION", "TIMEOUT", "NO_PROGRESS", "INTERNAL_ERROR",
    ] | None = None
    detail_for_llm: str = ""
    exit_code: int | None = None
    duration_ms: int = 0
    truncated: bool = False
    artifacts: dict[str, Any] = {}
