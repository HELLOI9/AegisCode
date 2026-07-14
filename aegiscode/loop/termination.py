# aegiscode/loop/termination.py
from dataclasses import dataclass
from enum import Enum

class TerminationReason(str, Enum):
    COMPLETED="COMPLETED"; FINISH_REJECTED="FINISH_REJECTED"; MAX_STEPS="MAX_STEPS"
    CONSECUTIVE_FAILURES="CONSECUTIVE_FAILURES"; NO_PROGRESS="NO_PROGRESS"
    INVALID_ACTION_LIMIT="INVALID_ACTION_LIMIT"; LLM_ERROR="LLM_ERROR"
    INTERNAL_ERROR="INTERNAL_ERROR"; CANCELLED="CANCELLED"

@dataclass
class LoopCounters:
    step: int; consecutive_failures: int; invalid_actions: int; no_progress_hits: int

def decide_termination(c: LoopCounters, limits: dict):
    if c.invalid_actions >= limits["action_retry_limit"]:
        return TerminationReason.INVALID_ACTION_LIMIT
    if c.consecutive_failures >= limits["max_consecutive_failures"]:
        return TerminationReason.CONSECUTIVE_FAILURES
    if c.no_progress_hits >= limits["no_progress_repeat_limit"]:
        return TerminationReason.NO_PROGRESS
    if c.step >= limits["max_steps"]:
        return TerminationReason.MAX_STEPS
    return None
