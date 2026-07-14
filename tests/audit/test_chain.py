# tests/audit/test_chain.py
from aegiscode.persistence.db import open_db
from aegiscode.audit.chain import AuditLog
from aegiscode.audit.events import EventType

def test_chain_verifies(tmp_path):
    conn = open_db(str(tmp_path/"a.sqlite"))
    log = AuditLog(conn)
    for i in range(3):
        log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    assert log.verify_chain("t1") == (True, None)

def test_tamper_detected(tmp_path):
    conn = open_db(str(tmp_path/"a.sqlite"))
    log = AuditLog(conn);
    for i in range(3): log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    conn.execute("UPDATE audit_events SET payload_json='{\"i\":99}' WHERE step_index=1")
    ok, bad = log.verify_chain("t1")
    assert ok is False and bad == 1

def test_payload_redacted(tmp_path):
    conn = open_db(str(tmp_path/"a.sqlite"))
    log = AuditLog(conn)
    log.append("t1", 0, EventType.TOOL_EXECUTED, {"out":"token=sk-abcdef1234567890abcdef1234567890"})
    row = conn.execute("SELECT payload_json FROM audit_events").fetchone()[0]
    assert "sk-abcdef" not in row
