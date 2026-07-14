# tests/governance/test_approval.py
import pytest
from aegiscode.governance.approval import (ApprovalStore, ApprovalState, fingerprint,
                                           validate_resume, SupersededError)
from aegiscode.protocol.action import Action

def test_fingerprint_stable_and_sensitive():
    a1 = Action(tool="run_command", arguments={"command":"pip install x"})
    a2 = Action(tool="run_command", arguments={"command":"pip install y"})
    assert fingerprint(a1) == fingerprint(a1)
    assert fingerprint(a1) != fingerprint(a2)

def test_decide_transitions():
    s = ApprovalStore()
    req = s.create("t1", 2, {"tool":"x"}, "fp", "R", "reason", "risk")
    s.decide(req.approval_id, True)
    assert s.get(req.approval_id).state == ApprovalState.APPROVED

def test_superseded_when_action_changes():
    a1 = Action(tool="run_command", arguments={"command":"pip install x"})
    a2 = Action(tool="run_command", arguments={"command":"pip install evil"})
    with pytest.raises(SupersededError):
        validate_resume(fingerprint(a1), a2)

def test_remember_same_fingerprint():
    s = ApprovalStore(); s.remember("t1","fp1")
    assert s.check_remembered("t1","fp1") is True
    assert s.check_remembered("t1","other") is False
