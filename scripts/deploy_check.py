#!/usr/bin/env python3
"""AegisCode deployment verification script.

Usage:
    python scripts/deploy_check.py <DEPLOY_URL>

Checks:
1. /healthz returns 200 with expected fields
2. Response does not contain sensitive data
3. WebUI root (/) is accessible
4. All checks pass → exit 0; any failure → exit 1
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error


SENSITIVE_PATTERNS = [
    "api_key", "secret", "password", "token",
    "/home/", "/root/", "/etc/", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
]


def check_healthz(base_url: str) -> tuple[bool, str]:
    """Verify /healthz returns 200 with correct payload."""
    url = base_url.rstrip("/") + "/healthz"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return False, f"/healthz returned {resp.status}"
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return False, f"/healthz failed: {e}"

    if data.get("status") != "ok":
        return False, f"/healthz status field is {data.get('status')!r}, expected 'ok'"
    if data.get("service") != "aegiscode":
        return False, f"/healthz service field is {data.get('service')!r}"
    return True, f"/healthz OK: {json.dumps(data)}"


def check_no_secrets(base_url: str) -> tuple[bool, str]:
    """Verify /healthz response doesn't leak sensitive info."""
    url = base_url.rstrip("/") + "/healthz"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode().lower()
    except (urllib.error.URLError, OSError) as e:
        return False, f"Cannot fetch /healthz for secret check: {e}"

    for pattern in SENSITIVE_PATTERNS:
        if pattern.lower() in text:
            return False, f"/healthz response contains sensitive pattern: {pattern}"
    return True, "/healthz contains no sensitive patterns"


_EXPECTED_DEMO_IDS = {
    "dangerous-action-denial",
    "feedback-driven-repair",
    "approval-binding-invalidation",
}


def check_demos_listed(base_url: str) -> tuple[bool, str]:
    """Verify GET /demos lists the three preset MockLLM demos.

    Non-destructive: only reads the demo catalog (does NOT start any run, so it
    never mutates shared state or runs the interactive demo③). A deployment
    without the demo panel (or in standard mode) will not expose /demos.
    """
    url = base_url.rstrip("/") + "/demos"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return False, f"/demos returned {resp.status}"
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        return False, f"/demos failed: {e}"

    ids = {d.get("id") for d in data} if isinstance(data, list) else set()
    missing = _EXPECTED_DEMO_IDS - ids
    if missing:
        return False, f"/demos missing expected demos: {sorted(missing)}"
    return True, f"/demos lists all three preset demos: {sorted(_EXPECTED_DEMO_IDS)}"


def _is_demo_mode(base_url: str) -> bool:
    """Best-effort read of the deployment mode from /healthz (default False)."""
    url = base_url.rstrip("/") + "/healthz"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False
    return data.get("mode") == "demo"


def check_webui(base_url: str) -> tuple[bool, str]:
    """Verify the WebUI root is accessible."""
    url = base_url.rstrip("/") + "/"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return False, f"WebUI root returned {resp.status}"
            body = resp.read().decode()
    except (urllib.error.URLError, OSError) as e:
        return False, f"WebUI root failed: {e}"

    if "AegisCode" not in body:
        return False, "WebUI root does not contain 'AegisCode'"
    return True, "WebUI root OK"


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].startswith("http"):
        print("Usage: deploy_check.py <DEPLOY_URL>", file=sys.stderr)
        print("Error: DEPLOY_URL not provided or invalid", file=sys.stderr)
        return 1

    base_url = sys.argv[1]
    print(f"Checking deployment: {base_url}")
    print("-" * 50)

    checks = [
        check_healthz,
        check_no_secrets,
        check_webui,
    ]

    # In Demo Mode the deployment must also expose the preset-demo catalog.
    # Detect the mode from /healthz so a standard (non-demo) deployment — which
    # does not mount /demos — is not failed by this check.
    if _is_demo_mode(base_url):
        checks.append(check_demos_listed)

    all_pass = True
    for check_fn in checks:
        ok, msg = check_fn(base_url)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {msg}")
        if not ok:
            all_pass = False

    print("-" * 50)
    if all_pass:
        print("All checks passed.")
        return 0
    else:
        print("Some checks FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
