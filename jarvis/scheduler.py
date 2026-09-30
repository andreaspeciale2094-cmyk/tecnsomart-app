"""Proattivita': attivita' pianificate (briefing, promemoria), agenti in background e casella notifiche."""
import threading
import time
from datetime import datetime

from . import config
from .db import db

BRIEFING_PROMPT = (
    "Prepara il briefing mattutino per l'utente: saluto, data, eventi del calendario di oggi, mail non lette "
    "importanti, promemoria dai ricordi e, se conosci la sua citta', il meteo. Sii breve e naturale, da leggere ad alta voce."
)


def add_inbox(title: str, body: str):
    with db() as con:
        con.execute("INSERT INTO inbox (title, body, created) VALUES (?, ?, ?)", (title, body, time.time()))


def get_inbox(unread_only=True) -> list[dict]:
    with db() as con:
        q = "SELECT id, title, body, created FROM inbox" + (" WHERE read=0" if unread_only else "") + " ORDER BY id DESC LIMIT 50"
        return [{"id": r[0], "title": r[1], "body": r[2], "created": r[3]} for r in con.execute(q)]


def mark_read(ids: list[int]):
    with db() as con:
        con.executemany("UPDATE inbox SET read=1 WHERE id=?", [(i,) for i in ids])


def run_unattended(title: str, prompt: str):
    """Esegue un prompt senza utente presente e mette il risultato nella casella notifiche."""
    from . import brain  # import tardivo: brain -> tools -> scheduler

    try:
        reply, _ = brain.think([{"role": "user", "content": prompt}], unattended=True)
    except Exception as e:
        reply = f"Attivita' fallita: {e}"
    add_inbox(title, reply)


def start_background_agent(goal: str) -> str:
    threading.Thread(target=run_unattended, args=(f"Agente: {goal[:60]}", goal), daemon=True).start()
    return "Agente avviato: il risultato arrivera' tra le notifiche."


def add_job(name: str, prompt: str, at: str = "", every_min: int = 0) -> int:
    with db() as con:
        return con.execute(
            "INSERT INTO jobs (name, prompt, at, every_min, last_run) VALUES (?,?,?,?,?)",
            (name, prompt, at or None, every_min or None, time.time() if every_min else None),
        ).lastrowid


def list_jobs() -> list[dict]:
    with db() as con:
        return [
            {"id": r[0], "name": r[1], "at": r[2], "every_min": r[3], "prompt": r[4]}
            for r in con.execute("SELECT id, name, at, every_min, prompt FROM jobs WHERE active=1")
        ]


def cancel_job(job_id: int) -> bool:
    with db() as con:
        return con.execute("UPDATE jobs SET active=0 WHERE id=?", (job_id,)).rowcount > 0


def _due(job, now: datetime) -> bool:
    _, _, _, at, every, last = job
    if every:
        return time.time() - (last or 0) >= every * 60
    if at:
        h, m = map(int, at.split(":"))
        slot = now.replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
        return now.timestamp() >= slot and (last or 0) < slot
    return False


def _tick():
    now = datetime.now()
    with db() as con:
        jobs = con.execute("SELECT id, name, prompt, at, every_min, last_run FROM jobs WHERE active=1").fetchall()
        for j in jobs:
            if _due(j, now):
                con.execute("UPDATE jobs SET last_run=? WHERE id=?", (time.time(), j[0]))
                con.commit()
                threading.Thread(target=run_unattended, args=(j[1], j[2]), daemon=True).start()


def start():
    if config.BRIEFING_TIME and not any(j["name"] == "Briefing mattutino" for j in list_jobs()):
        add_job("Briefing mattutino", BRIEFING_PROMPT, at=config.BRIEFING_TIME)

    def loop():
        while True:
            try:
                _tick()
            except Exception:
                pass
            time.sleep(30)

    threading.Thread(target=loop, daemon=True).start()
