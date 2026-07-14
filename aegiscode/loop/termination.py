# aegiscode/loop/termination.py
from dataclasses import dataclass
from enum import Enum

class TerminationReason(str, Enum):
    COMPLETED="COMPLETED"; FINISH_REJECTED="FINISH_REJECTED"; MAX_STEPS="MAX_STEPS"
    CONSECUTIVE_FAILURES="CONSECUTIVE_FAILURES"; NO_PROGRESS="NO_PROGRESS"
    INVALID_ACTION_LIMIT="INVALID_ACTION_LIMIT"; LLM_ERROR="LLM_ERROR"
    INTERNAL_ERROR="INTERNAL_ERROR"; CANCELLED="CANCELLED"; TIMEOUT="TIMEOUT"

@dataclass
class LoopCounters:
    step: int; consecutive_failures: int; invalid_actions: int; no_progress_hits: int

def decide_termination(
    c: LoopCounters, limits: dict, elapsed_sec: float = 0.0
) -> TerminationReason | None:
    # Wall-clock timeout is a HARD external bound: it is checked FIRST so it stops
    # the loop regardless of any counter state (acceptance §一 requires "timeout").
    # Kept pure — elapsed_sec is injected by the caller (the harness reads a
    # monotonic clock) so this stays deterministic and unit-testable. When
    # wall_clock_timeout_sec is absent/None the check is skipped (back-compat for
    # callers that omit the key — timeout never fires spuriously).
    timeout_limit = limits.get("wall_clock_timeout_sec")
    if timeout_limit is not None and elapsed_sec >= timeout_limit:
        return TerminationReason.TIMEOUT
    if c.invalid_actions >= limits["action_retry_limit"]:
        return TerminationReason.INVALID_ACTION_LIMIT
    if c.consecutive_failures >= limits["max_consecutive_failures"]:
        return TerminationReason.CONSECUTIVE_FAILURES
    if c.no_progress_hits >= limits["no_progress_repeat_limit"]:
        return TerminationReason.NO_PROGRESS
    if c.step >= limits["max_steps"]:
        return TerminationReason.MAX_STEPS
    return None
