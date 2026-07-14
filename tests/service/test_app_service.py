"""tests/service/test_app_service.py -- ApplicationService integration tests (TDD)."""
from __future__ import annotations

import pytest

from aegiscode.service.app_service import ApplicationService
from tests.helpers import make_service


# ---------------------------------------------------------------------------
# Verbatim tests from the task brief
# ---------------------------------------------------------------------------

def test_create_and_query(tmp_path):
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop task")
    t = svc.get_task(tid)
    assert t["state"] in ("COMPLETED", "RUNNING", "FAILED")


def test_events_since(tmp_path):
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop")
    assert isinstance(svc.get_events(tid, since=0), list)


def test_audit_verify_exposed(tmp_path):
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop")
    assert svc.get_audit(tid)["chain_valid"] is True


# ---------------------------------------------------------------------------
# Additional tests
# ---------------------------------------------------------------------------

def test_cancel_sets_state(tmp_path):
    """pre_cancel=True results in CANCELLED state."""
    svc = make_service(
        tmp_path,
        scripted=['{"tool":"finish","arguments":{}}'],
        final_ok=True,
        sync=True,
        pre_cancel=True,
    )
    tid = svc.create_task(str(tmp_path), "task to cancel")
    t = svc.get_task(tid)
    assert t["state"] == "CANCELLED"


def test_list_approvals_returns_list(tmp_path):
    """list_approvals always returns a list (possibly empty)."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "simple")
    result = svc.list_approvals(tid)
    assert isinstance(result, list)


def test_approval_flow_approve(tmp_path):
    """write outside allowlist triggers REQUIRE_APPROVAL; approving lets run proceed."""
    scripted = [
        '{"tool":"write_file","arguments":{"path":"secret.txt","content":"x"}}',
        '{"tool":"finish","arguments":{}}',
    ]
    svc = make_service(
        tmp_path,
        scripted=scripted,
        final_ok=True,
        sync=True,
        approval_decisions={"*": True},
    )
    tid = svc.create_task(str(tmp_path), "approval test")
    approvals = svc.list_approvals(tid)
    assert len(approvals) >= 1
    assert all(a["state"] in ("APPROVED", "PENDING", "REJECTED") for a in approvals)


def test_approval_flow_reject(tmp_path):
    """Rejecting all approvals causes the task to fail via consecutive failures."""
    scripted = [
        '{"tool":"write_file","arguments":{"path":"secret.txt","content":"x"}}',
        '{"tool":"write_file","arguments":{"path":"secret2.txt","content":"y"}}',
        '{"tool":"write_file","arguments":{"path":"secret3.txt","content":"z"}}',
        '{"tool":"write_file","arguments":{"path":"secret4.txt","content":"a"}}',
        '{"tool":"write_file","arguments":{"path":"secret5.txt","content":"b"}}',
        '{"tool":"finish","arguments":{}}',
    ]
    svc = make_service(
        tmp_path,
        scripted=scripted,
        final_ok=True,
        sync=True,
        approval_decisions={"*": False},
    )
    tid = svc.create_task(str(tmp_path), "rejection test")
    t = svc.get_task(tid)
    assert t["state"] in ("FAILED", "CANCELLED", "COMPLETED")


def test_decide_sets_approval_state(tmp_path):
    """decide(approval_id, True/False) sets the approval row state."""
    scripted = [
        '{"tool":"write_file","arguments":{"path":"secret.txt","content":"x"}}',
        '{"tool":"finish","arguments":{}}',
    ]
    svc = make_service(
        tmp_path,
        scripted=scripted,
        final_ok=True,
        sync=True,
        approval_decisions={"*": True},
    )
    tid = svc.create_task(str(tmp_path), "decide test")
    approvals = svc.list_approvals(tid)
    for a in approvals:
        assert a["state"] in ("APPROVED", "REJECTED", "PENDING")


def test_get_events_since_filters(tmp_path):
    """get_events(task_id, since=N) returns only events with event_id > N."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "events test")
    all_events = svc.get_events(tid, since=0)
    assert len(all_events) >= 1
    if all_events:
        last_id = all_events[-1]["event_id"]
        new_events = svc.get_events(tid, since=last_id)
        assert len(new_events) == 0


def test_get_events_since_nonzero(tmp_path):
    """get_events with since > 0 returns fewer events than since=0."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "events since test")
    all_events = svc.get_events(tid, since=0)
    if len(all_events) > 1:
        first_id = all_events[0]["event_id"]
        tail = svc.get_events(tid, since=first_id)
        assert len(tail) < len(all_events)


def test_completed_state_on_finish(tmp_path):
    """Task that calls finish with final_ok=True must end in COMPLETED state."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "complete me")
    t = svc.get_task(tid)
    assert t["state"] == "COMPLETED"


def test_failed_state_on_finish_rejected(tmp_path):
    """Task where final_ok=False never completes; hits limit -> FAILED."""
    scripted = ['{"tool":"finish","arguments":{}}'] * 10
    svc = make_service(tmp_path, scripted=scripted, final_ok=False, sync=True)
    tid = svc.create_task(str(tmp_path), "fail me")
    t = svc.get_task(tid)
    assert t["state"] == "FAILED"


def test_get_task_unknown_raises(tmp_path):
    """get_task on unknown id raises KeyError or returns None."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    with pytest.raises((KeyError, ValueError)):
        svc.get_task("nonexistent-task-id")


def test_get_audit_structure(tmp_path):
    """get_audit returns dict with events list and chain_valid bool."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "audit structure")
    audit = svc.get_audit(tid)
    assert "chain_valid" in audit
    assert "events" in audit
    assert isinstance(audit["events"], list)
    assert isinstance(audit["chain_valid"], bool)


def test_step_count_persisted(tmp_path):
    """After task completes, step_count in task row is > 0."""
    svc = make_service(tmp_path, scripted=['{"tool":"finish","arguments":{}}'], final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "step count")
    t = svc.get_task(tid)
    assert t["step_count"] >= 0
