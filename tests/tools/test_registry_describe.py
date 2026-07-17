from aegiscode.tools.registry import ToolRegistry
from aegiscode.tools.file_tools import WriteFileTool, ReadFileTool

def test_describe_lists_registered_tools_with_params():
    reg = ToolRegistry()
    reg.register(WriteFileTool())
    reg.register(ReadFileTool())
    out = reg.describe()
    assert "write_file" in out and "read_file" in out
    assert WriteFileTool.description in out
    assert "path" in out and "content" in out
    assert "required" in out  # required-field markers rendered

def test_describe_omits_unregistered_tools():
    reg = ToolRegistry()
    reg.register(ReadFileTool())  # write_file NOT registered
    out = reg.describe()
    assert "read_file" in out
    assert "write_file" not in out

def test_describe_is_deterministic():
    reg = ToolRegistry()
    reg.register(WriteFileTool())
    reg.register(ReadFileTool())
    assert reg.describe() == reg.describe()
