# tests/loop/test_termination.py
from aegiscode.loop.termination import decide_termination, LoopCounters, TerminationReason

LIM = {"max_steps":25,"max_consecutive_failures":5,"no_progress_repeat_limit":3,"action_retry_limit":3}

def test_none_when_healthy():
    assert decide_termination(LoopCounters(1,0,0,0), LIM) is None

def test_max_steps():
    assert decide_termination(LoopCounters(25,0,0,0), LIM) == TerminationReason.MAX_STEPS

def test_consecutive_failures():
    assert decide_termination(LoopCounters(3,5,0,0), LIM) == TerminationReason.CONSECUTIVE_FAILURES

def test_no_progress():
    assert decide_termination(LoopCounters(3,0,0,3), LIM) == TerminationReason.NO_PROGRESS

def test_invalid_action_limit():
    assert decide_termination(LoopCounters(3,0,3,0), LIM) == TerminationReason.INVALID_ACTION_LIMIT

def test_nine_reasons_defined():
    assert len(list(TerminationReason)) == 9
