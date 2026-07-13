# tests/governance/test_path_fence.py
import os
from aegiscode.governance.path_fence import check_path

def test_symlink_escape_denied(tmp_path):
    root = tmp_path / "ws"; root.mkdir()
    (root / "evil").symlink_to("/etc/passwd")
    assert check_path("evil", str(root), []).allowed is False

def test_parent_traversal_denied(tmp_path):
    root = tmp_path / "ws"; root.mkdir()
    assert check_path("../../etc/passwd", str(root), []).allowed is False

def test_new_file_in_workspace_allowed(tmp_path):
    root = tmp_path / "ws"; root.mkdir()
    assert check_path("src/new.py", str(root), []).allowed is True

def test_sensitive_file_denied(tmp_path):
    root = tmp_path / "ws"; root.mkdir(); (root/".env").write_text("K=v")
    assert check_path(".env", str(root), [".env","*.pem"]).allowed is False

def test_absolute_inside_allowed(tmp_path):
    root = tmp_path / "ws"; root.mkdir(); (root/"a.py").write_text("x")
    assert check_path(str(root/"a.py"), str(root), []).allowed is True
