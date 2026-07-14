# tests/memory/test_store.py
from aegiscode.persistence.db import open_db
from aegiscode.memory.store import MemoryStore

def _store(tmp_path): return MemoryStore(open_db(str(tmp_path/"m.sqlite")))

def test_refuses_secret_value(tmp_path):
    s = _store(tmp_path)
    mid = s.write("p1","PROJECT_CONVENTION","k","token=sk-abcdef1234567890abcdef1234567890",[],"user")
    assert mid is None

def test_write_and_retrieve_by_keyword(tmp_path):
    s = _store(tmp_path)
    s.write("p1","PROJECT_CONVENTION","style","use 4-space indent",["style"],"user")
    hits = s.retrieve("p1", query="indent", top_k=8)
    assert hits and "indent" in hits[0]["value"]

def test_agent_memory_not_governance_usable(tmp_path):
    s = _store(tmp_path)
    s.write("p1","DECISION","guess","maybe use redis",[],"agent")
    row = s.retrieve("p1", query="redis")[0]
    assert row["source"] == "agent" and row["confirmed"] == 0
    assert s.is_governance_usable(row) is False

def test_topk_limit(tmp_path):
    s = _store(tmp_path)
    for i in range(12): s.write("p1","CODEBASE_FACT",f"k{i}",f"v{i}",[],"system")
    assert len(s.retrieve("p1", top_k=8)) == 8

def test_retrieve_is_project_scoped(tmp_path):
    s = _store(tmp_path)
    s.write("p1", "PROJECT_CONVENTION", "k1", "alpha value", [], "user")
    s.write("p2", "PROJECT_CONVENTION", "k2", "beta value", [], "user")
    p1 = s.retrieve("p1")
    p2 = s.retrieve("p2")
    assert len(p1) == 1 and all("alpha" in r["value"] for r in p1)
    assert len(p2) == 1 and all("beta" in r["value"] for r in p2)
    # keyword search must also not cross projects:
    assert s.retrieve("p1", query="beta") == []
