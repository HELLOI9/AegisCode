#!/usr/bin/env python3
"""Deterministic CI secret-scan gate (self-written; §A.4C spirit).

Scans ONLY the shipped production surface -- every ``*.py`` under
``aegiscode/`` and ``demos/`` -- reusing the project's own credential
scanner (``aegiscode.credentials.scanner``) so the CI gate shares the exact
regexes used for redaction. Tests (``tests/``) and repo-root docs are out of
scope: they intentionally contain fake keys for the scanner's own unit tests.

A small, explicit ALLOWLIST carries known false positives. Today it holds a
single entry: ``aegiscode/service/assembly.py:43``, where the line
``key = credential_store.get_key()`` trips the ``(?i)(KEY|...)=<16+ chars>``
pattern on the *identifier* ``credential_store`` -- not a real secret.

Exit code 1 if any non-allowlisted finding remains, else 0. Importable so the
gate can be unit-tested without a subprocess.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the repo root importable when run as `python scripts/ci_secret_scan.py`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aegiscode.credentials.scanner import Finding, scan_paths, scan_text  # noqa: E402

# Directories that ship in the runtime image / package (the surface a leak
# would actually expose). Scanning `tests/` here would flood the gate with the
# scanner's own intentional fixtures.
SHIPPED_DIRS = ("aegiscode", "demos")

# Known false positives: (path_suffix, line_no). Keep this list SHORT and
# justify every entry -- it is the one place the gate can be silenced.
ALLOWLIST: list[tuple[str, int]] = [
    # `key = credential_store.get_key()` -- the KEY=... regex matches the
    # 16-char identifier `credential_store`, not a secret. Verified by reading
    # aegiscode/service/assembly.py.
    ("aegiscode/service/assembly.py", 43),
]


def _is_allowlisted(finding: Finding) -> bool:
    path = str(finding.path).replace("\\", "/")
    return any(
        path.endswith(suffix) and finding.line_no == line_no
        for suffix, line_no in ALLOWLIST
    )


def shipped_py_files() -> list[Path]:
    files: list[Path] = []
    for d in SHIPPED_DIRS:
        files.extend(sorted((REPO_ROOT / d).rglob("*.py")))
    return files


def remaining_findings() -> list[Finding]:
    """Findings on the shipped surface after removing allowlisted FPs."""
    findings = scan_paths(shipped_py_files())
    return [f for f in findings if not _is_allowlisted(f)]


def main(argv: list[str] | None = None) -> int:
    remaining = remaining_findings()
    if remaining:
        print(f"SECRET SCAN FAILED: {len(remaining)} finding(s) on shipped surface:")
        for f in remaining:
            print(f"  {f.path}:{f.line_no}  <-  {f.pattern}")
        return 1
    print(
        f"SECRET SCAN OK: scanned {len(shipped_py_files())} shipped file(s); "
        f"0 findings (allowlist: {len(ALLOWLIST)} known FP)."
    )
    return 0


# Re-export so tests can prove the mechanism still fires on a planted key.
__all__ = ["Finding", "main", "remaining_findings", "scan_text", "shipped_py_files"]


if __name__ == "__main__":
    sys.exit(main())
