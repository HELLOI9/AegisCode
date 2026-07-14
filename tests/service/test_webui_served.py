"""tests/service/test_webui_served.py — WebUI static-serving tests (TDD, Task 28).

The FastAPI app must serve a native single-page WebUI at GET / and expose the
app.js and style.css assets. These tests assert the app is wired to serve the
HTML shell and its two assets, and that the JS carries the polling logic that
drives the event stream.

Asset mounting contract (must stay consistent with index.html references):
  GET /            -> index.html (HTML shell)
  GET /app.js      -> app.js     (vanilla JS, no imports)
  GET /style.css   -> style.css  (stylesheet)
"""
from __future__ import annotations

from tests.helpers import make_api_client


def test_root_serves_html(tmp_path):
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_root_html_references_assets(tmp_path):
    """The served HTML shell must reference the SAME asset paths the app serves."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "app.js" in body
    assert "style.css" in body


def test_app_js_served_with_polling_logic(tmp_path):
    """app.js must be served (200) and contain the polling logic."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/app.js")
    assert r.status_code == 200
    body = r.text
    # Polling drives the event stream by event_id watermark via ?since=.
    assert "/events" in body
    assert "since" in body
    # Must consume the task/approval/audit endpoints too.
    assert "/tasks" in body
    assert "/decision" in body
    assert "/audit" in body


def test_style_css_served(tmp_path):
    """style.css must be served with 200 and be a non-empty stylesheet."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/style.css")
    assert r.status_code == 200
    assert len(r.text.strip()) > 0


def test_app_js_content_type_is_javascript(tmp_path):
    """app.js should be served with a JavaScript content type, not HTML."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("content-type", "").lower()


def test_existing_endpoints_still_work(tmp_path):
    """Mounting the WebUI must not break the existing REST endpoints."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    # A known JSON endpoint must keep returning JSON, not the HTML shell.
    r = client.get("/credentials/status")
    assert r.status_code == 200
    assert "masked" in r.json()
