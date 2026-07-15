"""RED-first tests for DemoRunManager (aegiscode/demo/service.py).

DemoRunManager runs each shared demo scenario (aegiscode/demo/scenarios.py)
through the REAL HarnessCore + MockLLM + governance + approval state machine +
audit chain, in an isolated per-run temp workspace under `allowed_base`, with
idempotent cleanup on terminal state.

For determinism these tests construct the manager with `sync=True` (and, for
the approval-binding scenario, an injected `sync_decision_fn` mirroring
tests/helpers.py::make_service) so start_run() runs the harness inline and
get_run() reads a fully-settled result with no polling/timing involved. The
async (sync=False) production default is exercised by Task 4's HTTP layer.
"""
from __future__ import annotations

import inspect
import os

import pytest

from aegiscode.demo.scenarios import UnknownScenarioError
from aegiscode.demo.service import DemoRunManager


def _make_manager(tmp_path, sync=True, sync_decision_fn=None):
    allowed_base = tmp_path / "base"
    allowed_base.mkdir()
    db_path = str(tmp_path / "svc.db")
    return DemoRunManager(
        str(allowed_base), db_path, sync=sync, sync_decision_fn=sync_decision_fn
    )


class TestDenialRun:
    def test_denial_run_zero_exec_and_deny(self, tmp_path):
        mgr = _make_manager(tmp_path)
        run_id = mgr.start_run("dangerous-action-denial")
        result = mgr.get_run(run_id)

        assert result["scenario_id"] == "dangerous-action-denial"
        assert result["done"] is True
        assert result["state"] != "COMPLETED"

        by_key = {c["key"]: c["passed"] for c in result["acceptance"]}
        assert by_key["denied"] is True
        assert by_key["no_exec"] is True
        assert by_key["rule_id"] is True
        assert by_key["feedback"] is True
        assert all(result_ for result_ in by_key.values())


class TestFeedbackRun:
    def test_feedback_run_completes(self, tmp_path):
        mgr = _make_manager(tmp_path)
        run_id = mgr.start_run("feedback-driven-repair")
        result = mgr.get_run(run_id)

        assert result["done"] is True
        assert result["state"] == "COMPLETED"

        by_key = {c["key"]: c["passed"] for c in result["acceptance"]}
        assert by_key["completed"] is True
        assert by_key["test_failure"] is True
        assert by_key["tools_ran"] is True


class TestIsolation:
    def test_isolation(self, tmp_path):
        mgr = _make_manager(tmp_path)

        run1 = mgr.start_run("dangerous-action-denial")
        ws1 = mgr._run_meta[run1]["workspace"]
        run2 = mgr.start_run("dangerous-action-denial")
        ws2 = mgr._run_meta[run2]["workspace"]

        assert run1 != run2
        assert ws1 != ws2

        r1 = mgr.get_run(run1)
        r2 = mgr.get_run(run2)

        # Both must complete their deny cleanly -- proves the MockLLM cursor
        # was NOT shared between the two runs (a shared cursor would exhaust
        # after the first run and the second would hit LLM_ERROR / fail the
        # denied/no_exec conditions).
        assert r1["done"] is True and r2["done"] is True
        assert all(c["passed"] for c in r1["acceptance"])
        assert all(c["passed"] for c in r2["acceptance"])


class TestCleanup:
    def test_cleanup(self, tmp_path):
        mgr = _make_manager(tmp_path)
        run_id = mgr.start_run("dangerous-action-denial")
        ws = mgr._run_meta[run_id]["workspace"]
        assert os.path.isdir(ws)

        result = mgr.get_run(run_id)
        assert result["done"] is True
        assert not os.path.exists(ws)

        # idempotent: calling get_run again after cleanup must not raise
        result2 = mgr.get_run(run_id)
        assert result2["done"] is True


class TestUnknownScenario:
    def test_unknown_scenario_rejected(self, tmp_path):
        mgr = _make_manager(tmp_path)
        with pytest.raises(UnknownScenarioError):
            mgr.start_run("evil")


class TestNoArbitraryWorkspace:
    def test_no_arbitrary_workspace(self):
        sig = inspect.signature(DemoRunManager.start_run)
        params = [p for p in sig.parameters if p != "self"]
        assert params == ["scenario_id"]


class TestApprovalBinding:
    def test_approval_binding_supersede(self, tmp_path):
        mgr = _make_manager(
            tmp_path, sync=True, sync_decision_fn=lambda approval_id: True
        )
        run_id = mgr.start_run("approval-binding-invalidation")
        result = mgr.get_run(run_id)

        assert result["done"] is True

        import json

        # Real AuditLog rows store event_type as str(EventType.X), i.e.
        # "EventType.APPROVAL_DECIDED" (see aegiscode/demo/service.py's
        # _normalize_event_type docstring for why) -- accept either the
        # qualified or plain form here rather than depending on internals.
        states = set()
        for row in mgr.service.get_events(run_id, 0):
            event_type = row["event_type"]
            if isinstance(event_type, str) and event_type.rsplit(".", 1)[-1] == "APPROVAL_DECIDED":
                payload = json.loads(row["payload_json"])
                state = payload.get("state")
                if state:
                    states.add(state)

        assert "APPROVED" in states
        assert "SUPERSEDED" in states

