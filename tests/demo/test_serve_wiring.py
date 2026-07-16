"""tests/demo/test_serve_wiring.py — demo-aware `serve` assembly.

In demo mode (AEGIS_DEMO_MODE=1) the served FastAPI app must mount the demo
endpoints (GET /demos etc.) backed by a DemoRunManager, so a public visitor can
run the preset MockLLM demos. In standard mode the demo routes must NOT be
mounted (behavior unchanged). The CLI factors this into a testable
`build_serve_app(cfg, store, db_path)` so we can assert the wiring without
binding a socket.
"""
from __future__ import annotations

import tempfile

from fastapi.testclient import TestClient

from aegiscode.cli import build_serve_app
from aegiscode.config.schema import AegisConfig, Workspace
from aegiscode.credentials.store import CredentialStore


class _NullBackend:
    def get_password(self, service, user):
        return None

    def set_password(self, service, user, value):
        pass

    def delete_password(self, service, user):
        pass


def _cfg(tmp_path):
    return AegisConfig(
        workspace=Workspace(root=str(tmp_path), allowed_base=str(tmp_path)),
    )


def _mock_cfg(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.llm.provider = "mock"
    return cfg


def test_demo_mode_serve_mounts_demos(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGIS_DEMO_MODE", "1")
    store = CredentialStore(backend=_NullBackend())
    app = build_serve_app(_mock_cfg(tmp_path), store, str(tmp_path / "aegis.db"))
    client = TestClient(app)
    r = client.get("/demos")
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()]
    assert ids == [
        "dangerous-action-denial",
        "feedback-driven-repair",
        "approval-binding-invalidation",
    ]


def test_standard_mode_serve_does_not_mount_demos(tmp_path, monkeypatch):
    monkeypatch.delenv("AEGIS_DEMO_MODE", raising=False)
    store = CredentialStore(backend=_NullBackend())
    app = build_serve_app(_mock_cfg(tmp_path), store, str(tmp_path / "aegis.db"))
    client = TestClient(app)
    # Demo routes are absent in standard mode → 404.
    assert client.get("/demos").status_code == 404
    # But the app is still a working panel (a known endpoint responds).
    assert client.get("/healthz").status_code == 200


def test_manual_task_on_unregistered_workspace_terminates(tmp_path):
    """A create_task on a workspace the manager never registered via start_run
    (e.g. a manual POST /tasks in demo mode with an ephemeral demo workspace)
    must reach a TERMINAL state, not crash the run thread and hang in RUNNING.
    The demo-aware harness_factory falls back to a keyless MockLLM → LLM_ERROR.
    """
    from aegiscode.demo.service import DemoRunManager

    mgr = DemoRunManager(
        allowed_base=str(tmp_path), db_path=str(tmp_path / "m.db"), sync=True
    )
    ws = tempfile.mkdtemp(dir=str(tmp_path))  # never passed through start_run
    tid = mgr.service.create_task(ws, description="manual")
    state = mgr.service.get_task(tid)["state"]
    assert state in ("FAILED", "COMPLETED", "CANCELLED"), (
        f"unregistered-workspace run left task in {state!r} (thread likely crashed)"
    )
