from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.result import ToolResult

class Dummy:
    name = "dummy"
    def run(self, arguments, ctx):
        return ToolResult(tool="dummy", status="success", summary="ok")

def test_register_and_get():
    r = ToolRegistry(); r.register(Dummy())
    assert r.get("dummy").name == "dummy"
    assert "dummy" in r.names()

def test_unknown_returns_none():
    assert ToolRegistry().get("nope") is None

def test_toolresult_defaults():
    tr = ToolResult(tool="t", status="success", summary="s")
    assert tr.truncated is False and tr.category is None

import pytest
from pydantic import ValidationError

def test_bad_status_rejected():
    with pytest.raises(ValidationError):
        ToolResult(tool="t", status="succes", summary="s")   # typo of "success"

def test_bad_category_rejected():
    with pytest.raises(ValidationError):
        ToolResult(tool="t", status="failure", summary="s", category="NOT_A_CATEGORY")
