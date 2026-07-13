# tests/tools/test_file_tools.py
from types import SimpleNamespace
from aegiscode.tools.file_tools import ReadFileTool, WriteFileTool, SearchTextTool, ListFilesTool

def _ctx(tmp_path):
    return SimpleNamespace(resolve=lambda p: str(tmp_path / p),
                           write_max_bytes=1_000_000, snapshot=lambda p: None)

def test_write_then_read(tmp_path):
    ctx = _ctx(tmp_path)
    WriteFileTool().run({"path":"a.py","content":"X=1\n"}, ctx)
    r = ReadFileTool().run({"path":"a.py"}, ctx)
    assert "X=1" in r.detail_for_llm and r.status == "success"

def test_write_rejects_oversize(tmp_path):
    ctx = _ctx(tmp_path); ctx.write_max_bytes = 2
    r = WriteFileTool().run({"path":"a.py","content":"toolong"}, ctx)
    assert r.status == "error"

def test_binary_read_skipped(tmp_path):
    (tmp_path/"b.bin").write_bytes(b"\x00\x01\x02\xff")
    r = ReadFileTool().run({"path":"b.bin"}, _ctx(tmp_path))
    assert "binary" in r.summary.lower()

def test_search_finds_match(tmp_path):
    ctx = _ctx(tmp_path)
    WriteFileTool().run({"path":"a.py","content":"needle here\n"}, ctx)
    r = SearchTextTool().run({"query":"needle"}, ctx)
    assert "a.py" in r.detail_for_llm

def test_list_files_returns_entries(tmp_path):
    ctx = _ctx(tmp_path)
    WriteFileTool().run({"path":"a.py","content":"x"}, ctx)
    WriteFileTool().run({"path":"b.py","content":"y"}, ctx)
    r = ListFilesTool().run({"path":"."}, ctx)
    assert r.status == "success" and "a.py" in r.detail_for_llm and "b.py" in r.detail_for_llm

def test_read_missing_file_returns_tool_error(tmp_path):
    r = ReadFileTool().run({"path":"nope.py"}, _ctx(tmp_path))
    assert r.status == "error" and r.category == "TOOL_ERROR"
