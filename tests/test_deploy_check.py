"""Tests for scripts/deploy_check.py core logic."""
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "scripts")
from deploy_check import (
    check_demos_listed,
    check_healthz,
    check_no_secrets,
    check_webui,
    main,
)


class FakeResponse:
    """Minimal urllib response mock."""
    def __init__(self, status, body):
        self.status = status
        self._body = body.encode() if isinstance(body, str) else body
    def read(self):
        return self._body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        pass


def _mock_urlopen(body, status=200):
    """Return a context-manager patch for urllib.request.urlopen."""
    return patch(
        "deploy_check.urllib.request.urlopen",
        return_value=FakeResponse(status, body),
    )


def test_check_healthz_pass():
    body = '{"status":"ok","service":"aegiscode","mode":"demo"}'
    with _mock_urlopen(body):
        ok, msg = check_healthz("http://test")
    assert ok
    assert "/healthz OK" in msg


def test_check_healthz_wrong_status_field():
    body = '{"status":"error","service":"aegiscode"}'
    with _mock_urlopen(body):
        ok, msg = check_healthz("http://test")
    assert not ok
    assert "status field" in msg


def test_check_healthz_non_200():
    with _mock_urlopen("", status=500):
        ok, msg = check_healthz("http://test")
    assert not ok


def test_check_no_secrets_clean():
    body = '{"status":"ok","service":"aegiscode","mode":"demo"}'
    with _mock_urlopen(body):
        ok, msg = check_no_secrets("http://test")
    assert ok


def test_check_no_secrets_leak():
    body = '{"status":"ok","api_key":"sk-123"}'
    with _mock_urlopen(body):
        ok, msg = check_no_secrets("http://test")
    assert not ok
    assert "sensitive" in msg


def test_check_webui_pass():
    body = "<html><title>AegisCode Local Panel</title></html>"
    with _mock_urlopen(body):
        ok, msg = check_webui("http://test")
    assert ok


def test_check_webui_missing_marker():
    body = "<html><title>Something else</title></html>"
    with _mock_urlopen(body):
        ok, msg = check_webui("http://test")
    assert not ok


def test_check_demos_listed_pass():
    body = (
        '[{"id":"dangerous-action-denial"},'
        '{"id":"feedback-driven-repair"},'
        '{"id":"approval-binding-invalidation"}]'
    )
    with _mock_urlopen(body):
        ok, msg = check_demos_listed("http://test")
    assert ok is True


def test_check_demos_listed_missing_one():
    body = '[{"id":"dangerous-action-denial"},{"id":"feedback-driven-repair"}]'
    with _mock_urlopen(body):
        ok, msg = check_demos_listed("http://test")
    assert ok is False


def test_check_demos_listed_non_200():
    with _mock_urlopen("[]", status=404):
        ok, msg = check_demos_listed("http://test")
    assert ok is False


def test_main_no_url():
    with patch("sys.argv", ["deploy_check.py"]):
        assert main() == 1


def test_main_all_pass():
    body_healthz = '{"status":"ok","service":"aegiscode","mode":"demo"}'
    body_webui = "<html>AegisCode</html>"
    body_demos = (
        '[{"id":"dangerous-action-denial"},'
        '{"id":"feedback-driven-repair"},'
        '{"id":"approval-binding-invalidation"}]'
    )

    def fake_open(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "healthz" in url:
            return FakeResponse(200, body_healthz)
        if url.rstrip("/").endswith("/demos"):
            return FakeResponse(200, body_demos)
        return FakeResponse(200, body_webui)

    with patch("deploy_check.urllib.request.urlopen", side_effect=fake_open):
        with patch("sys.argv", ["deploy_check.py", "http://test"]):
            assert main() == 0
