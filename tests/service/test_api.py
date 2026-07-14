"""tests/service/test_api.py — FastAPI REST layer tests (TDD).

Tests all 8 endpoints in SPEC §13 M13:
  POST /tasks
  GET  /tasks/{id}
  GET  /tasks/{id}/events?since=N
  GET  /tasks/{id}/approvals
  POST /approvals/{id}/decision
  POST /tasks/{id}/cancel
  GET  /tasks/{id}/audit
  GET  /credentials/status

Security: /credentials/status MUST return only masked status, never plaintext key.
"""
from __future__ import annotations

import sqlite3

from tests.helpers import make_api_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPTED_FINISH = ['{"tool":"finish","arguments":{}}']


# ---------------------------------------------------------------------------
# Endpoint: POST /tasks
# ---------------------------------------------------------------------------

def test_create_task_returns_id(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    r = client.post("/tasks", json={"workspace": str(tmp_path), "description": "noop"})
    assert r.status_code == 200
    assert "task_id" in r.json()


def test_create_task_missing_field_returns_422(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    # Missing "description"
    r = client.post("/tasks", json={"workspace": str(tmp_path)})
    assert r.status_code == 422


def test_create_task_id_is_string(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    r = client.post("/tasks", json={"workspace": str(tmp_path), "description": "test"})
    assert isinstance(r.json()["task_id"], str)
    assert len(r.json()["task_id"]) > 0


# ---------------------------------------------------------------------------
# Endpoint: GET /tasks/{id}
# ---------------------------------------------------------------------------

def test_get_task_returns_state(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "t"}).json()["task_id"]
    r = client.get(f"/tasks/{tid}")
    assert r.status_code == 200
    body = r.json()
    assert "state" in body
    assert body["state"] in ("RUNNING", "COMPLETED", "FAILED", "CANCELLED")


def test_get_task_not_found_returns_404(tmp_path):
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/tasks/nonexistent-task-id")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Endpoint: GET /tasks/{id}/events?since=N
# ---------------------------------------------------------------------------

def test_events_endpoint_returns_list(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "n"}).json()["task_id"]
    r = client.get(f"/tasks/{tid}/events?since=0")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_events_endpoint_default_since(tmp_path):
    """since param defaults to 0 if omitted."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "n"}).json()["task_id"]
    r = client.get(f"/tasks/{tid}/events")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_events_since_filters(tmp_path):
    """Events with since=large_number returns empty or fewer results."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "n"}).json()["task_id"]
    all_events = client.get(f"/tasks/{tid}/events?since=0").json()
    filtered = client.get(f"/tasks/{tid}/events?since=999999").json()
    assert len(filtered) <= len(all_events)


# ---------------------------------------------------------------------------
# Endpoint: GET /tasks/{id}/approvals
# ---------------------------------------------------------------------------

def test_approvals_endpoint_returns_list(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "a"}).json()["task_id"]
    r = client.get(f"/tasks/{tid}/approvals")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Endpoint: POST /approvals/{id}/decision
# ---------------------------------------------------------------------------

def test_decision_endpoint_approve(tmp_path):
    """POST /approvals/{id}/decision returns 200 for any id."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    # decide() is a no-op when approval not in _approval_events; should still 200
    r = client.post("/approvals/fake-approval-id/decision", json={"approved": True})
    assert r.status_code == 200


def test_decision_endpoint_reject(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    r = client.post("/approvals/fake-approval-id/decision", json={"approved": False})
    assert r.status_code == 200


def test_decision_endpoint_missing_field_returns_422(tmp_path):
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.post("/approvals/some-id/decision", json={})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Endpoint: POST /tasks/{id}/cancel
# ---------------------------------------------------------------------------

def test_cancel_endpoint_returns_200(tmp_path):
    """POST /tasks/{id}/cancel triggers cancellation; returns 200."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "c"}).json()["task_id"]
    r = client.post(f"/tasks/{tid}/cancel")
    assert r.status_code == 200


def test_cancel_nonexistent_task_still_200(tmp_path):
    """cancel() for unknown id must not crash (cancel flag simply absent)."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.post("/tasks/unknown-task-id/cancel")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Endpoint: GET /tasks/{id}/audit
# ---------------------------------------------------------------------------

def test_audit_endpoint_returns_chain_valid(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "audit"}).json()["task_id"]
    r = client.get(f"/tasks/{tid}/audit")
    assert r.status_code == 200
    body = r.json()
    assert "chain_valid" in body
    assert isinstance(body["chain_valid"], bool)


def test_audit_endpoint_contains_events(tmp_path):
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    tid = client.post("/tasks", json={"workspace": str(tmp_path), "description": "audit"}).json()["task_id"]
    r = client.get(f"/tasks/{tid}/audit")
    assert "events" in r.json()
    assert isinstance(r.json()["events"], list)


def test_audit_not_found_returns_404(tmp_path):
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/tasks/no-such-task/audit")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Endpoint: GET /credentials/status
# ---------------------------------------------------------------------------

def test_credentials_status_masked(tmp_path):
    """Response MUST contain 'masked' key; MUST NOT contain 'plaintext' key."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/credentials/status")
    body = r.json()
    assert r.status_code == 200
    assert "masked" in body
    assert "plaintext" not in body


def test_credentials_status_no_raw_key_leak(tmp_path):
    """Response body must never include a raw/full API key string.

    We set a fake key in the store and verify it does not appear verbatim
    in the response body.
    """
    from fastapi.testclient import TestClient
    from aegiscode.credentials.store import CredentialStore
    from aegiscode.service.api import build_app
    from tests.helpers import make_service

    class FakeKeyring:
        """Returns a known fake key for testing."""
        def get_password(self, service, user):
            return "sk-PLAINTEXT_FAKE_KEY_12345_ABCDEF"
        def set_password(self, service, user, value):
            pass
        def delete_password(self, service, user):
            pass

    svc = make_service(tmp_path, scripted=[], final_ok=True, sync=True)
    cred_store = CredentialStore(backend=FakeKeyring())
    app = build_app(svc, credential_store=cred_store)

    with TestClient(app) as client:
        r = client.get("/credentials/status")
        body_text = r.text
        assert "PLAINTEXT_FAKE_KEY_12345_ABCDEF" not in body_text
        assert "sk-PLAINTEXT_FAKE_KEY_12345_ABCDEF" not in body_text


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

def test_unexpected_service_error_returns_generic_500(tmp_path):
    """A non-KeyError service exception must become a generic 500 with body
    {"detail":"internal error"} and NO Python traceback text leaked."""
    from fastapi.testclient import TestClient
    from aegiscode.service.api import build_app
    from tests.helpers import make_service

    svc = make_service(tmp_path, scripted=[], final_ok=True, sync=True)

    # Force the underlying service call to raise a non-HTTPException.
    def _boom(task_id):
        raise sqlite3.OperationalError("SECRET_DB_PATH=/home/jwdeng/leak.db")

    svc.get_task = _boom
    app = build_app(svc)

    # raise_server_exceptions=False so TestClient returns the 500 response
    # instead of re-raising the exception into the test.
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/tasks/any-id")
        assert r.status_code == 500
        assert r.json() == {"detail": "internal error"}
        # No traceback / internal detail leaked into the response body.
        assert "Traceback" not in r.text
        assert "OperationalError" not in r.text
        assert "SECRET_DB_PATH" not in r.text


def test_credentials_status_unconfigured(tmp_path):
    """When no key is set, returns configured=False and masked=None."""
    from fastapi.testclient import TestClient
    from aegiscode.credentials.store import CredentialStore
    from aegiscode.service.api import build_app
    from tests.helpers import make_service

    class EmptyKeyring:
        def get_password(self, service, user):
            return None
        def set_password(self, service, user, value):
            pass
        def delete_password(self, service, user):
            pass

    svc = make_service(tmp_path, scripted=[], final_ok=True, sync=True)
    cred_store = CredentialStore(backend=EmptyKeyring())
    app = build_app(svc, credential_store=cred_store)

    with TestClient(app) as client:
        r = client.get("/credentials/status")
        assert r.status_code == 200
        body = r.json()
        assert body["configured"] is False
        assert body["masked"] is None


def test_credentials_status_no_credential_store(tmp_path):
    """When no credential_store is passed, endpoint still returns 200 with masked key."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/credentials/status")
    assert r.status_code == 200
    assert "masked" in r.json()
