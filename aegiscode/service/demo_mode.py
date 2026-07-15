"""aegiscode/service/demo_mode.py — Demo Mode support for public deployment.

When AEGIS_DEMO_MODE=1, the service runs in a restricted sandbox:
- Only the built-in demo project can be used as workspace
- Each task gets an ephemeral copy (cleaned up on completion/failure)
- Tighter limits (max_steps, timeouts)
- No real LLM required (MockLLM)
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def is_demo_mode() -> bool:
    """Return True if the service is running in demo mode."""
    return os.environ.get("AEGIS_DEMO_MODE") == "1"


def _demo_project_source() -> Path:
    """Path to the bundled demo project template."""
    return Path(__file__).parent.parent.parent / "examples" / "demo-project"


def create_demo_workspace() -> str:
    """Create a temporary copy of the demo project for one task.

    Returns the path to the temporary directory. Caller is responsible
    for cleanup via cleanup_demo_workspace().
    """
    src = _demo_project_source()
    if not src.is_dir():
        raise RuntimeError(f"Demo project template not found: {src}")
    tmp = tempfile.mkdtemp(prefix="aegis_demo_")
    shutil.copytree(src, tmp, dirs_exist_ok=True)
    return tmp


def cleanup_demo_workspace(path: str) -> None:
    """Remove an ephemeral demo workspace. Safe to call with non-existent path."""
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def validate_demo_request(workspace: str) -> None:
    """In demo mode, reject any workspace that isn't the sentinel 'demo'.

    Raises ValueError if the workspace is not acceptable in demo mode.
    """
    if not is_demo_mode():
        return
    # In demo mode, only the literal "demo" sentinel is accepted.
    # The API layer replaces it with an ephemeral copy.
    if workspace != "demo":
        raise ValueError(
            "In demo mode, workspace must be 'demo' "
            "(arbitrary paths are not permitted)"
        )
