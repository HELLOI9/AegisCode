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
