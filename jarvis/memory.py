"""Memoria a lungo termine semantica: fatti in SQLite con embedding."""
import json
import time

from . import embeddings
from .db import db


def remember(text: str) -> int:
    emb = embeddings.embed([text])[0]
    with db() as con:
        return con.execute(
            "INSERT INTO facts (text, created, emb, emb_kind) VALUES (?, ?, ?, ?)",
            (text, time.time(), json.dumps(emb), embeddings.KIND),
        ).lastrowid


def forget(fact_id: int) -> bool:
    with db() as con:
        return con.execute("DELETE FROM facts WHERE id = ?", (fact_id,)).rowcount > 0


def _ensure_embeddings(con, rows):
    stale = [r for r in rows if r[3] != embeddings.KIND or not r[2]]
    if stale:
        for r, e in zip(stale, embeddings.embed([r[1] for r in stale])):
            con.execute("UPDATE facts SET emb=?, emb_kind=? WHERE id=?", (json.dumps(e), embeddings.KIND, r[0]))
    con.commit()
    return con.execute("SELECT id, text, emb FROM facts").fetchall() if stale else [(r[0], r[1], r[2]) for r in rows]


def recall(query: str = "", limit: int = 20) -> list[dict]:
    with db() as con:
        if not query:
            rows = con.execute("SELECT id, text FROM facts ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
            return [{"id": r[0], "text": r[1]} for r in rows]
        rows = con.execute("SELECT id, text, emb, emb_kind FROM facts").fetchall()
        rows = _ensure_embeddings(con, rows)
    q = embeddings.embed([query])[0]
    words = [w for w in query.lower().split() if len(w) > 3]
    scored = []
    for fid, text, emb in rows:
        s = embeddings.cosine(q, json.loads(emb))
        s += 0.3 * any(w in text.lower() for w in words)  # bonus per corrispondenza letterale
        if s >= embeddings.THRESHOLD:
            scored.append((s, fid, text))
    scored.sort(reverse=True)
    return [{"id": fid, "text": text} for _, fid, text in scored[:limit]]
