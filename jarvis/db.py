import sqlite3
from . import config


def db() -> sqlite3.Connection:
    con = sqlite3.connect(config.DB_PATH)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, text TEXT NOT NULL, created REAL NOT NULL, emb TEXT, emb_kind TEXT);
        CREATE TABLE IF NOT EXISTS inbox (id INTEGER PRIMARY KEY, title TEXT, body TEXT, created REAL, read INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, name TEXT, prompt TEXT, at TEXT, every_min INTEGER, last_run REAL, active INTEGER DEFAULT 1);
        """
    )
    cols = {r[1] for r in con.execute("PRAGMA table_info(facts)")}
    for col in ("emb", "emb_kind"):  # migrazione da versioni precedenti
        if col not in cols:
            con.execute(f"ALTER TABLE facts ADD COLUMN {col} TEXT")
    return con
