"""Memoria a lungo termine: fatti persistenti in SQLite."""
import sqlite3
import time
from . import config


def _db():
    con = sqlite3.connect(config.DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY, text TEXT NOT NULL, created REAL NOT NULL)"
    )
    return con


def remember(text: str) -> int:
    with _db() as con:
        return con.execute("INSERT INTO facts (text, created) VALUES (?, ?)", (text, time.time())).lastrowid


def forget(fact_id: int) -> bool:
    with _db() as con:
        return con.execute("DELETE FROM facts WHERE id = ?", (fact_id,)).rowcount > 0


def recall(query: str = "", limit: int = 20) -> list[dict]:
    with _db() as con:
        if query:
            words = [w for w in query.lower().split() if len(w) > 2] or [query.lower()]
            clause = " OR ".join("LOWER(text) LIKE ?" for _ in words)
            rows = con.execute(
                f"SELECT id, text FROM facts WHERE {clause} ORDER BY created DESC LIMIT ?",
                [f"%{w}%" for w in words] + [limit],
            ).fetchall()
        else:
            rows = con.execute("SELECT id, text FROM facts ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "text": r[1]} for r in rows]
