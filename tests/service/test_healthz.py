"""Tests for the /healthz health-check endpoint."""
import pytest
from fastapi.testclient import TestClient

from tests.helpers import make_api_client


@pytest.fixture()
def client(tmp_path):
    return make_api_client(tmp_path, scripted=['{"tool":"finish","args":{}}'])


def test_healthz_returns_200(client):
    """GET /healthz returns 200 with expected payload."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "aegiscode"


def test_healthz_does_not_leak_secrets(client):
    """Response must not contain env vars, paths, or key material."""
    resp = client.get("/healthz")
    text = resp.text.lower()
    for sensitive in ("api_key", "secret", "/home/", "/root/", "password"):
        assert sensitive not in text


def test_healthz_has_mode_field(client):
    """Response includes a mode field indicating current deployment mode."""
    resp = client.get("/healthz")
    data = resp.json()
    assert "mode" in data
