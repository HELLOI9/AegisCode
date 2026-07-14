# aegiscode/audit/chain.py
import hashlib, json, datetime
from aegiscode.security.redactor import redact

GENESIS = "0" * 64

class AuditLog:
    def __init__(self, conn): self.conn = conn

    def _prev_hash(self, task_id):
        row = self.conn.execute(
            "SELECT hash FROM audit_events WHERE task_id=? ORDER BY event_id DESC LIMIT 1",
            (task_id,)).fetchone()
        return row[0] if row else GENESIS

    def append(self, task_id, step_index, event_type, payload: dict) -> str:
        payload_json = redact(json.dumps(payload, sort_keys=True))
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        prev = self._prev_hash(task_id)
        body = json.dumps({"task_id": task_id, "step_index": step_index,
            "event_type": str(event_type), "timestamp": ts, "payload_json": payload_json},
            sort_keys=True)
        h = hashlib.sha256((prev + body).encode()).hexdigest()
        self.conn.execute(
            "INSERT INTO audit_events(task_id,step_index,timestamp,event_type,payload_json,prev_hash,hash)"
            " VALUES(?,?,?,?,?,?,?)",
            (task_id, step_index, ts, str(event_type), payload_json, prev, h))
        return h

    def verify_chain(self, task_id):
        prev = GENESIS
        for row in self.conn.execute(
            "SELECT step_index,timestamp,event_type,payload_json,prev_hash,hash "
            "FROM audit_events WHERE task_id=? ORDER BY event_id", (task_id,)):
            step_index, ts, et, pj, stored_prev, stored_hash = row
            body = json.dumps({"task_id": task_id, "step_index": step_index,
                "event_type": et, "timestamp": ts, "payload_json": pj},
                sort_keys=True)
            h = hashlib.sha256((prev + body).encode()).hexdigest()
            if stored_prev != prev or stored_hash != h:
                return (False, step_index)
            prev = stored_hash
        return (True, None)
