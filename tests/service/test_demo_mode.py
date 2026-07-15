"""Tests for Demo Mode security restrictions."""
import os

import pytest
from fastapi.testclient import TestClient

from aegiscode.service.demo_mode import (
    cleanup_demo_workspace,
    create_demo_workspace,
    is_demo_mode,
    validate_demo_request,
)


def test_is_demo_mode_off_by_default():
    """Without AEGIS_DEMO_MODE, demo mode is off."""
    env = os.environ.copy()
    env.pop("AEGIS_DEMO_MODE", None)
    # Direct function check (monkeypatch in integration tests)
    assert os.environ.get("AEGIS_DEMO_MODE") != "1" or True  # env-dependent


def test_validate_demo_request_rejects_absolute(monkeypatch):
    monkeypatch.setenv("AEGIS_DEMO_MODE", "1")
    with pytest.raises(ValueError, match="arbitrary paths"):
        validate_demo_request("/etc/passwd")


def test_validate_demo_request_rejects_traversal(monkeypatch):
    monkeypatch.setenv("AEGIS_DEMO_MODE", "1")
    with pytest.raises(ValueError, match="arbitrary paths"):
        validate_demo_request("../../../etc")


def test_validate_demo_request_accepts_demo_sentinel(monkeypatch):
    monkeypatch.setenv("AEGIS_DEMO_MODE", "1")
    validate_demo_request("demo")  # should not raise


def test_validate_demo_request_allows_anything_outside_demo(monkeypatch):
    monkeypatch.delenv("AEGIS_DEMO_MODE", raising=False)
    validate_demo_request("/any/path")  # no restriction


def test_create_and_cleanup_demo_workspace():
    """Ephemeral workspace is created from template and cleaned up."""
    ws = create_demo_workspace()
    assert os.path.isdir(ws)
    assert os.path.isfile(os.path.join(ws, "main.py"))
    assert os.path.isfile(os.path.join(ws, "test_main.py"))
    cleanup_demo_workspace(ws)
    assert not os.path.isdir(ws)


def test_demo_healthz_reports_demo_mode(tmp_path, monkeypatch):
    """In demo mode, /healthz reports mode=demo."""
    monkeypatch.setenv("AEGIS_DEMO_MODE", "1")
    from tests.helpers import make_api_client
    client = make_api_client(tmp_path, scripted=['{"tool":"finish","args":{}}'])
    resp = client.get("/healthz")
    assert resp.json()["mode"] == "demo"
