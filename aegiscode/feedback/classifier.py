from collections import deque

def classify(tr) -> str | None:
    if tr.category in {"POLICY_DENIED", "INVALID_ACTION", "TIMEOUT", "TOOL_ERROR",
                       "APPROVAL_REJECTED", "INTERNAL_ERROR", "NO_PROGRESS"}:
        return tr.category
    if tr.tool == "run_tests" and tr.status == "failure":
        return "TEST_FAILURE"
    if tr.status in {"failure", "error"}:
        return "TOOL_ERROR"
    return None  # success -> no failure category

class ProgressTracker:
    def __init__(self, window=3): self._recent = deque(maxlen=window)
    def seen(self, fp: str) -> bool:
        hit = fp in self._recent
        self._recent.append(fp)
        return hit
