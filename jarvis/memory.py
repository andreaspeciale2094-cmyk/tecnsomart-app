"""Memoria a lungo termine semantica: fatti in SQLite con embedding."""
import json
import re
import time

from . import embeddings, logs
from .db import db

FORGET_HOOKS: list = []  # funzioni chiamate quando qualcosa viene dimenticato (es. svuotare i riassunti)


def notify_forgotten(what: str) -> None:
    logs.log_memory(f"dimenticato: {what}")
    for hook in FORGET_HOOKS:
        try:
            hook()
        except Exception:
            pass


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower().replace("\u2019", "'")).strip()


def remember(text: str) -> int:
    emb = embeddings.embed([text])[0]
    with db() as con:
        for fid, old, old_emb, kind in con.execute("SELECT id, text, emb, emb_kind FROM facts").fetchall():
            if _norm(old) == _norm(text) or (kind == embeddings.KIND and old_emb and embeddings.cosine(emb, json.loads(old_emb)) >= 0.9):
                return fid  # gia' saputo: non duplicare
        return con.execute(
            "INSERT INTO facts (text, created, emb, emb_kind) VALUES (?, ?, ?, ?)",
            (text, time.time(), json.dumps(emb), embeddings.KIND),
        ).lastrowid


def forget(fact_id: int) -> bool:
    with db() as con:
        done = con.execute("DELETE FROM facts WHERE id = ?", (fact_id,)).rowcount > 0
    if done:
        notify_forgotten(f"ricordo dell'archivio n. {fact_id}")
    return done


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
