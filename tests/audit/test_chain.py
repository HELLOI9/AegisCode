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

def test_tamper_hash_mutation_detected(tmp_path):
    conn = open_db(str(tmp_path / "a.db"))
    log = AuditLog(conn)
    for i in range(3):
        log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    # mutate the stored hash of the middle row, leave payload intact
    conn.execute("UPDATE audit_events SET hash='deadbeef' WHERE task_id='t1' AND step_index=1")
    ok, bad = log.verify_chain("t1")
    assert ok is False and bad == 1

def test_tamper_row_deletion_detected(tmp_path):
    conn = open_db(str(tmp_path / "a.db"))
    log = AuditLog(conn)
    for i in range(3):
        log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    conn.execute("DELETE FROM audit_events WHERE task_id='t1' AND step_index=1")
    ok, bad = log.verify_chain("t1")
    assert ok is False   # deletion breaks the running prev-hash chain

def test_intact_chain_after_appends_verifies(tmp_path):
    conn = open_db(str(tmp_path / "a.db"))
    log = AuditLog(conn)
    for i in range(5):
        log.append("t1", i, EventType.FEEDBACK, {"i": i})
    assert log.verify_chain("t1") == (True, None)

def test_tail_truncation_detected_with_expected_count(tmp_path):
    conn = open_db(str(tmp_path / "a.db"))
    log = AuditLog(conn)
    for i in range(3):
        log.append("t1", i, EventType.TOOL_EXECUTED, {"i": i})
    # delete the LAST row — prefix stays valid, so plain verify can't catch it:
    conn.execute("DELETE FROM audit_events WHERE task_id='t1' AND step_index=2")
    assert log.verify_chain("t1") == (True, None)          # plain chain still 'intact' (documented limitation)
    ok, _ = log.verify_chain("t1", expected_count=3)        # but count anchor catches truncation
    assert ok is False
