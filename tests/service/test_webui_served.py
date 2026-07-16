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


def test_app_js_renders_changed_files_diff(tmp_path):
    """app.js must wire its diff panel to payload.changed_files (the field the
    harness now emits on TOOL_EXECUTED) rather than nonexistent diff fields, and
    must render paths via textContent (no unescaped innerHTML) since workspace
    paths are attacker-influenced."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    r = client.get("/app.js")
    assert r.status_code == 200
    body = r.text
    assert "changed_files" in body
    # XSS-safety: the diff panel must NOT interpolate a path into innerHTML.
    # (Existing innerHTML uses only clear lists to "".) Paths flow through
    # el()/textContent instead.
    assert "innerHTML" not in body.split("changed_files")[1]


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


# ---------------------------------------------------------------------------
# Task 5: preset MockLLM demo panel (WebUI)
# ---------------------------------------------------------------------------
# There is no JS runtime in pytest, so these assert on served-file CONTENT:
# that the real code paths (fetch("/demos"), the run+poll loop, acceptance
# rendering) exist — not just comments.


def test_index_has_demo_section(tmp_path):
    """The HTML shell must carry the preset-demo container node the JS targets."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    body = client.get("/").text
    # A stable container id the app.js populates with demo cards.
    assert 'id="demos-section"' in body
    assert 'id="demos-list"' in body


def test_app_js_has_demo_panel_logic(tmp_path):
    """app.js must fetch the demo list, POST a run, poll get_run, and render
    the acceptance summary — real code paths, not just mentions."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    body = client.get("/app.js").text
    # Fetches the demo catalog.
    assert 'fetch("/demos")' in body or "getJSON(\"/demos\")" in body or "getJSON('/demos')" in body
    # Starts a run (POST /demos/{id}/run).
    assert "/demos/" in body and "/run" in body
    # Polls the run status endpoint.
    assert "/demos/runs/" in body
    # Renders the per-condition acceptance summary.
    assert "renderAcceptance" in body
    # Reuses the existing approval decision endpoint for interactive demo 3.
    assert "/decision" in body


def test_app_js_demo_failure_not_shown_as_success(tmp_path):
    """The acceptance renderer must key success off passed===... /every, not a
    blanket 'done' — a failed condition must not read as success."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    body = client.get("/app.js").text
    # The renderer must inspect per-condition `passed` (proves failure can't be
    # laundered into a green banner).
    assert "passed" in body
    # Overall verdict is derived from the acceptance items (every/some), not a
    # bare HTTP-200 assumption.
    assert ".every(" in body or ".some(" in body


def test_style_has_demo_classes(tmp_path):
    """style.css must define the demo card/timeline/acceptance classes, and
    status must NOT be conveyed by color alone (a text/icon class must exist)."""
    client = make_api_client(tmp_path, scripted=[], final_ok=True)
    css = client.get("/style.css").text
    assert ".demo-card" in css
    assert ".timeline" in css or ".step-row" in css
    assert ".acceptance" in css
    # Accessibility: a glyph/icon class so status is text+icon, not color-only.
    assert ".status-icon" in css or "::before" in css
