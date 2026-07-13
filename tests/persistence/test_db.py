# tests/persistence/test_db.py
from aegiscode.persistence.db import open_db

def test_all_six_tables_exist(tmp_path):
    conn = open_db(str(tmp_path / "aegis.sqlite"))
    got = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"tasks","steps","approval_requests",
            "audit_events","memories","task_snapshots"} <= got

def test_wal_mode(tmp_path):
    conn = open_db(str(tmp_path / "aegis.sqlite"))
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
