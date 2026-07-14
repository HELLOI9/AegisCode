import sqlite3, pathlib

def open_db(path: str) -> sqlite3.Connection:
    """Open (and initialize) the AegisCode sqlite database.

    check_same_thread=False: sync FastAPI endpoints run in Starlette's
    threadpool, so this connection is accessed from worker threads that
    differ from the one that created it. Do NOT "clean this up" — removing
    the flag breaks the API with a "SQLite objects created in a thread can
    only be used in that same thread" error. It is safe here because we use
    WAL + autocommit (isolation_level=None) and access is effectively
    serialized under single-user localhost use. Background task threads open
    their OWN connection (see ApplicationService._run_in_thread) and never
    share this one.

    busy_timeout=5000: in async mode the background harness thread writes
    audit_events continuously while the main-thread connection may write an
    approval decision (decide() -> UPDATE approval_requests). WAL allows many
    readers but only ONE writer; without a busy timeout a colliding write
    raises SQLITE_BUSY immediately and would silently drop the approval
    decision (leaving the row PENDING until the resolver fail-closes). A 5s
    busy_timeout makes the second writer wait for the (sub-millisecond) write
    lock instead of erroring — correctness fix for the serve/approval path.
    """
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    sql = pathlib.Path(__file__).with_name("schema.sql").read_text()
    conn.executescript(sql)
    return conn
