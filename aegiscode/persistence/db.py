import sqlite3, pathlib

def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    sql = pathlib.Path(__file__).with_name("schema.sql").read_text()
    conn.executescript(sql)
    return conn
