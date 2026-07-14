"""tests/service/test_workspace_fence.py — server-side workspace-base fence (TDD).

Security gap (acceptance §八): POST /tasks accepts a caller-supplied `workspace`
that becomes ctx.workspace_root with NO server-side validation. Because the path
fence anchors to workspace_root, an attacker who sets workspace="/" turns the
unauthenticated API into arbitrary host write/exec.

Fix: the service validates the requested workspace is INSIDE a configured allowed
base (realpath + commonpath, symlink-safe & prefix-collision-safe). Requests for a
workspace outside the base are rejected (ValueError at the service, HTTP 400 at the
API) and NO task is created.

These tests are written FIRST and must FAIL before the fix is implemented.
"""
from __future__ import annotations

import os

import pytest

from aegiscode.service.app_service import WorkspaceNotAllowedError
from tests.helpers import make_api_client, make_service


SCRIPTED_FINISH = ['{"tool":"finish","arguments":{}}']


def _task_count(svc) -> int:
    """Count rows in the tasks table via the service's main connection."""
    return svc._db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]


# ---------------------------------------------------------------------------
# Service layer: create_task rejects workspaces outside the allowed base
# ---------------------------------------------------------------------------

def test_create_task_rejects_root_workspace(tmp_path):
    """workspace='/' is outside the allowed base (tmp_path) -> rejected, no task."""
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    before = _task_count(svc)
    with pytest.raises(WorkspaceNotAllowedError):
        svc.create_task("/", "own the host")
    assert _task_count(svc) == before  # NO task row created


def test_create_task_rejects_etc(tmp_path):
    """workspace='/etc' is outside the allowed base -> rejected, no task."""
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    before = _task_count(svc)
    with pytest.raises(WorkspaceNotAllowedError):
        svc.create_task("/etc", "read secrets")
    assert _task_count(svc) == before


def test_create_task_rejects_relative_traversal(tmp_path):
    """A non-absolute traversal path ('../..') is rejected (fail closed)."""
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    before = _task_count(svc)
    with pytest.raises(WorkspaceNotAllowedError):
        svc.create_task("../..", "traverse out")
    assert _task_count(svc) == before


def test_create_task_rejects_symlink_escape(tmp_path):
    """A symlink INSIDE the base that points OUTSIDE must be caught by realpath."""
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    # tmp_path/link -> tmp_path.parent (a directory outside the base).
    link = tmp_path / "escape_link"
    link.symlink_to(tmp_path.parent, target_is_directory=True)
    before = _task_count(svc)
    with pytest.raises(WorkspaceNotAllowedError):
        svc.create_task(str(link), "symlink escape")
    assert _task_count(svc) == before


def test_create_task_rejects_sibling_prefix_trap(tmp_path):
    """base '/x/ws' must NOT accept requested '/x/ws-evil' (commonpath, not prefix)."""
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    # Sibling of the base sharing a string prefix but a different path segment.
    evil = str(tmp_path) + "-evil"
    os.makedirs(evil, exist_ok=True)
    try:
        before = _task_count(svc)
        with pytest.raises(WorkspaceNotAllowedError):
            svc.create_task(evil, "sibling prefix trap")
        assert _task_count(svc) == before
    finally:
        os.rmdir(evil)


# ---------------------------------------------------------------------------
# Non-regression: workspaces INSIDE the allowed base are accepted
# ---------------------------------------------------------------------------

def test_create_task_accepts_base_itself(tmp_path):
    """workspace == allowed base (the configured root) is accepted and runs."""
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    tid = svc.create_task(str(tmp_path), "noop at base")
    assert svc.get_task(tid)["state"] == "COMPLETED"


def test_create_task_accepts_subdir_of_base(tmp_path):
    """A subdirectory of the allowed base is accepted and runs."""
    sub = tmp_path / "project"
    sub.mkdir()
    svc = make_service(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True, sync=True)
    tid = svc.create_task(str(sub), "noop in subdir")
    assert svc.get_task(tid)["state"] == "COMPLETED"


# ---------------------------------------------------------------------------
# API boundary: POST /tasks maps the rejection to HTTP 400, no task created
# ---------------------------------------------------------------------------

def test_api_post_tasks_rejects_root_with_400(tmp_path):
    """POST /tasks with workspace='/' -> 400 and NO task created."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    r = client.post("/tasks", json={"workspace": "/", "description": "own the host"})
    assert r.status_code == 400
    assert "task_id" not in r.json()


def test_api_post_tasks_rejects_etc_with_400(tmp_path):
    """POST /tasks with workspace='/etc' -> 400 (outside base)."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    r = client.post("/tasks", json={"workspace": "/etc", "description": "read secrets"})
    assert r.status_code == 400


def test_api_post_tasks_accepts_base(tmp_path):
    """Non-regression: POST /tasks with workspace inside the base -> 200."""
    client = make_api_client(tmp_path, scripted=SCRIPTED_FINISH, final_ok=True)
    r = client.post("/tasks", json={"workspace": str(tmp_path), "description": "ok"})
    assert r.status_code == 200
    assert "task_id" in r.json()
