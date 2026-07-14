# tests/credentials/test_backend_perms.py
"""I1/I2: the JSON credential file and its parent dir must be created with
restrictive permissions, with no world/group-readable window.

The umask is pinned to 0o022 (a common permissive default) so the pre-fix
behavior is deterministic: open(path,"w") would create the file 0o644 and
os.makedirs would create the dir 0o755.
"""
import os
import stat

from aegiscode.credentials.backend import build_credential_store


def test_credentials_file_created_0600_no_world_readable_window(tmp_path, monkeypatch):
    """The file must be CREATED restricted (0600), not created permissively and
    then chmod-ed. We neutralize the post-hoc os.chmod so the test observes the
    mode the file is created with — the transient window I1 is about. Under the
    pre-fix code (open(path,"w")) this is 0o644 under umask 022 → RED."""
    monkeypatch.setattr(os, "chmod", lambda *a, **k: None)
    old = os.umask(0o022)
    try:
        home = tmp_path / "aegis_home"
        cs = build_credential_store(env={"AEGIS_HOME": str(home)})
        cs.set_key("sk-secret-value")
        path = home / "credentials.json"
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, f"expected 0o600 at creation, got {oct(mode)}"
    finally:
        os.umask(old)


def test_credentials_dir_is_0700(tmp_path):
    old = os.umask(0o022)
    try:
        home = tmp_path / "aegis_home"
        cs = build_credential_store(env={"AEGIS_HOME": str(home)})
        cs.set_key("sk-secret-value")
        mode = stat.S_IMODE(os.stat(home).st_mode)
        assert mode == 0o700, f"expected 0o700, got {oct(mode)}"
    finally:
        os.umask(old)
