# tests/security/test_redactor.py
from aegiscode.security.redactor import redact

def test_redacts_openai_key():
    assert "sk-abcdef1234567890abcdef1234567890" not in redact("token=sk-abcdef1234567890abcdef1234567890")

def test_redacts_anthropic_key():
    out = redact("KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXX")
    assert "sk-ant-" not in out

def test_redacts_aws_key():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("AWS AKIAIOSFODNN7EXAMPLE done")

def test_rewrites_workspace_absolute_paths():
    out = redact("failed at /workspace/src/foo.py:12", workspace_root="/workspace")
    assert "/workspace" not in out
    assert "src/foo.py" in out

def test_no_change_when_clean():
    assert redact("hello world") == "hello world"

def test_redacts_generic_keyvalue_secret():
    # value matches no sk-/AKIA family, so only the KEY=/TOKEN= generic pattern can catch it
    out = redact("TOKEN=abcdefghijklmnop1234567890")
    assert "abcdefghijklmnop1234567890" not in out

def test_generic_pattern_case_insensitive():
    out = redact("password = ZYXWVUTSRQ0987654321")
    assert "ZYXWVUTSRQ0987654321" not in out

def test_workspace_sibling_prefix_not_mangled():
    out = redact("/workspace-backup/src/foo.py", workspace_root="/workspace")
    assert out == "/workspace-backup/src/foo.py"   # sibling dir must be untouched

def test_workspace_bare_root_stripped():
    out = redact("at /workspace done", workspace_root="/workspace")
    assert "/workspace" not in out

def test_redacts_openai_project_key():
    # Modern dominant format: sk-proj-... contains hyphens, so the old
    # sk-[A-Za-z0-9]{20,} pattern missed it. Use a BARE context (no KEY=
    # prefix) so only the sk- family pattern can catch it -- this is the
    # defense-in-depth case where a key leaks into an error message.
    key = "sk-proj-1a2B3c4D_5e6F-7g8H9i0JklmnopQRs"
    assert key not in redact(f"invalid credential {key} rejected")

def test_redacts_openai_svcacct_key():
    key = "sk-svcacct-abc123DEF456ghi789_JKL-012mno"
    assert key not in redact(f"used {key} for auth")

def test_still_redacts_legacy_openai_key():
    key = "sk-abcdef1234567890abcdef1234567890"
    assert key not in redact(f"saw {key} in output")

def test_still_redacts_anthropic_key():
    out = redact("KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXX")
    assert "sk-ant-" not in out

def test_short_sk_token_not_over_redacted():
    # A bare/short sk- fragment in ordinary text must NOT be redacted.
    assert redact("sk-short") == "sk-short"
    assert redact("please run the task-list-view") == "please run the task-list-view"
