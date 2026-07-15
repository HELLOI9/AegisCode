"""tests/service/test_demo_api.py — HTTP layer over DemoRunManager (Task 4).

Covers: GET /demos (listing), POST /demos/{id}/run + GET /demos/runs/{id}
(status/acceptance polling) for the sync demo scenarios, error mapping
(400 for unknown demo id, 404 for unknown run id), the demo3 interactive
approval flow reusing the EXISTING /tasks/{id}/approvals and
/approvals/{id}/decision endpoints (no new approval routes), idempotent
double-decide, and a basic redaction check (no absolute tmp paths or
secret-like strings leaking into run/events responses).

All polling is bounded (hard monotonic deadline) so a regressed async path
can never hang the suite.
"""
from __future__ import annotations

import json
import re
import time

import pytest
from fastapi.testclient import TestClient

from aegiscode.demo.service import DemoRunManager
from aegiscode.service.api import build_app


def _make_client(tmp_path, sync=False):
    mgr = DemoRunManager(
        allowed_base=str(tmp_path),
        db_path=str(tmp_path / "demo.db"),
        sync=sync,
    )
    app = build_app(mgr.service, demo_manager=mgr)
    client = TestClient(app)
    return client, mgr


def _poll(fn, until, cap_sec=10.0, interval=0.05):
    """Poll fn() until until(result) is truthy or cap_sec elapses.

    Bounded by a hard monotonic deadline so a regressed async path can never
    hang the suite. Returns the last observed result either way; callers
    must inspect it and fail explicitly if the target state was not reached.
    """
    deadline = time.monotonic() + cap_sec
    result = fn()
    while not until(result):
        if time.monotonic() > deadline:
            return result
        time.sleep(interval)
        result = fn()
    return result


def test_list_demos_returns_three_scenarios(tmp_path):
    client, _mgr = _make_client(tmp_path)
    r = client.get("/demos")
    assert r.status_code == 200
    items = r.json()
    assert [d["id"] for d in items] == [
        "dangerous-action-denial",
        "feedback-driven-repair",
        "approval-binding-invalidation",
    ]
    for item in items:
        assert set(item.keys()) == {
            "id",
            "title",
            "description",
            "learning_objective",
            "interactive_approval",
        }


def test_demos_not_mounted_when_no_manager(tmp_path):
    """Without demo_manager, /demos* routes must not exist (existing behavior)."""
    from aegiscode.service.app_service import ApplicationService
    from aegiscode.config.schema import AegisConfig, Workspace
    from aegiscode.persistence.db import open_db

    conn = open_db(str(tmp_path / "plain.db"))
    config = AegisConfig(workspace=Workspace(root=str(tmp_path), allowed_base=str(tmp_path)))
    # A no-op harness_factory: this test never starts a task, it only asserts the
    # /demos* routes are absent when build_app gets no demo_manager.
    svc = ApplicationService(
        db=conn,
        db_path=str(tmp_path / "plain.db"),
        config=config,
        harness_factory=lambda **kwargs: None,
    )
    app = build_app(svc)
    client = TestClient(app)

    r = client.get("/demos")
    assert r.status_code == 404
    r2 = client.post("/demos/dangerous-action-denial/run")
    assert r2.status_code == 404


def test_run_dangerous_action_denial_all_acceptance_pass(tmp_path):
    client, _mgr = _make_client(tmp_path, sync=True)
    r = client.post("/demos/dangerous-action-denial/run")
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    assert isinstance(run_id, str) and run_id

    result = _poll(
        lambda: client.get(f"/demos/runs/{run_id}").json(),
        until=lambda row: row.get("done") is True,
        cap_sec=10.0,
    )
    if not result.get("done"):
        pytest.fail(f"demo run never finished within 10s: {result}")

    by_key = {c["key"]: c["passed"] for c in result["acceptance"]}
    assert by_key == {
        "denied": True,
        "no_exec": True,
        "rule_id": True,
        "feedback": True,
    }


def test_run_unknown_demo_id_returns_400(tmp_path):
    client, _mgr = _make_client(tmp_path)
    r = client.post("/demos/nope/run")
    assert r.status_code == 400


def test_get_run_unknown_id_returns_404(tmp_path):
    client, _mgr = _make_client(tmp_path)
    r = client.get("/demos/runs/nonexistent")
    assert r.status_code == 404


def test_run_endpoint_ignores_client_supplied_body(tmp_path):
    """POST /demos/{id}/run must not let the client control workspace/script/etc."""
    client, _mgr = _make_client(tmp_path, sync=True)
    r = client.post(
        "/demos/dangerous-action-denial/run",
        json={"workspace": "/etc", "script": ["rm -rf /"], "command": "evil"},
    )
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    result = _poll(
        lambda: client.get(f"/demos/runs/{run_id}").json(),
        until=lambda row: row.get("done") is True,
        cap_sec=10.0,
    )
    if not result.get("done"):
        pytest.fail(f"demo run never finished within 10s: {result}")
    by_key = {c["key"]: c["passed"] for c in result["acceptance"]}
    assert by_key["denied"] is True


def _normalize_event_type(raw: str) -> str:
    return raw.rsplit(".", 1)[-1]


def test_demo3_interactive_approval_flow_over_http(tmp_path):
    """Demo3 (approval-binding-invalidation) driven fully over HTTP.

    Confirms: (a) a genuine async pause happens (PENDING approval visible,
    no TOOL_EXECUTED event yet), (b) the existing /approvals/{id}/decision
    endpoint drives the resume, (c) idempotent re-decide does not crash or
    regress state, and (d) final acceptance is all-passed.
    """
    client, mgr = _make_client(tmp_path, sync=False)

    r = client.post("/demos/approval-binding-invalidation/run")
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    approvals = _poll(
        lambda: client.get(f"/tasks/{run_id}/approvals").json(),
        until=lambda rows: any(a["state"] == "PENDING" for a in rows),
        cap_sec=10.0,
    )
    pending = [a for a in approvals if a["state"] == "PENDING"]
    if not pending:
        pytest.fail("no PENDING approval appeared over HTTP within 10s (async pause did not happen)")
    approval_id = pending[0]["approval_id"]

    # Before deciding: the write must not have executed yet.
    events = client.get(f"/tasks/{run_id}/events").json()
    executed_types = {
        _normalize_event_type(row["event_type"])
        for row in events
        if isinstance(row, dict) and "event_type" in row
    }
    assert "TOOL_EXECUTED" not in executed_types, (
        "a TOOL_EXECUTED event occurred before the approval was decided; "
        "the write executed pre-approval"
    )

    # Also confirm the run isn't already done.
    pre_decision_run = client.get(f"/demos/runs/{run_id}").json()
    assert pre_decision_run["done"] is False

    d = client.post(f"/approvals/{approval_id}/decision", json={"approved": True})
    assert d.status_code == 200

    result = _poll(
        lambda: client.get(f"/demos/runs/{run_id}").json(),
        until=lambda row: row.get("done") is True,
        cap_sec=10.0,
    )
    if not result.get("done"):
        pytest.fail(f"demo3 run never finished within 10s: {result}")

    by_key = {c["key"]: c["passed"] for c in result["acceptance"]}
    assert by_key == {
        "approved": True,
        "superseded": True,
        "flow": True,
    }

    # Idempotency: deciding again must not crash and must not regress state.
    d2 = client.post(f"/approvals/{approval_id}/decision", json={"approved": True})
    assert d2.status_code == 200

    result2 = client.get(f"/demos/runs/{run_id}").json()
    assert result2["done"] is True
    by_key2 = {c["key"]: c["passed"] for c in result2["acceptance"]}
    assert by_key2 == by_key


_SECRET_PATTERN = re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+")


def test_run_and_events_responses_do_not_leak_paths_or_secrets(tmp_path):
    client, _mgr = _make_client(tmp_path, sync=True)
    r = client.post("/demos/feedback-driven-repair/run")
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    result = _poll(
        lambda: client.get(f"/demos/runs/{run_id}").json(),
        until=lambda row: row.get("done") is True,
        cap_sec=10.0,
    )
    if not result.get("done"):
        pytest.fail(f"demo run never finished within 10s: {result}")

    events = client.get(f"/tasks/{run_id}/events").json()

    run_text = json.dumps(result)
    events_text = json.dumps(events)

    for text, label in ((run_text, "run"), (events_text, "events")):
        assert str(tmp_path) not in text, f"{label} response leaked the absolute tmp_path"
        assert "/etc/" not in text, f"{label} response leaked a suspicious absolute path"
        assert not _SECRET_PATTERN.search(text), f"{label} response leaked a secret-like string"
