"""Memory store: write-with-redaction and filtered retrieval."""
import uuid
import json
import datetime

from aegiscode.credentials.scanner import scan_text


class MemoryStore:
    def __init__(self, conn):
        self.conn = conn

    def write(self, project_id, type, key, value, tags, source, confirmed=None):
        """Insert a memory row. Returns memory_id or None if value/key/tags contains a secret."""
        if scan_text(value) or scan_text(key) or scan_text(" ".join(tags or [])):
            return None

        if source == "agent":
            confirmed = False
        elif confirmed is None:
            confirmed = True

        mid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO memories(memory_id,project_id,type,key,value,tags_json,source,"
            "confirmed,created_at,last_used_at,use_count) VALUES(?,?,?,?,?,?,?,?,?,?,0)",
            (mid, project_id, type, key, value, json.dumps(tags), source,
             1 if confirmed else 0, now, now),
        )
        return mid

    def retrieve(self, project_id, query=None, top_k=8, type=None):  # noqa: A002
        """Retrieve memories filtered by project_id + optional keyword/type, ordered by last_used_at DESC."""
        sql = (
            "SELECT memory_id,project_id,type,key,value,tags_json,source,confirmed,use_count "
            "FROM memories WHERE project_id=?"
        )
        params = [project_id]
        if query:
            sql += " AND (key LIKE ? OR value LIKE ? OR tags_json LIKE ?)"
            params += [f"%{query}%"] * 3
        if type is not None:
            sql += " AND type=?"
            params.append(type)
        sql += " ORDER BY last_used_at DESC LIMIT ?"
        params.append(top_k)

        cols = ["memory_id", "project_id", "type", "key", "value",
                "tags_json", "source", "confirmed", "use_count"]
        rows = [dict(zip(cols, r)) for r in self.conn.execute(sql, params)]

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for r in rows:
            self.conn.execute(
                "UPDATE memories SET use_count=use_count+1, last_used_at=? WHERE memory_id=?",
                (now, r["memory_id"]),
            )
        return rows

    @staticmethod
    def is_governance_usable(row) -> bool:
        """Agent-sourced memory is never a governance basis."""
        return row["source"] != "agent"
