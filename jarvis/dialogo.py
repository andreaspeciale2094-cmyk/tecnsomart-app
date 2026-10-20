"""Una conversazione con Jarvis da un canale diverso dalla pagina (Telegram, ascolto in stanza): una richiesta alla volta."""
import threading

from . import brain, logs, sessions

_lock = threading.Lock()


def rispondi(sid: str, testo: str) -> str:
    with _lock:
        history, before = sessions.start_request(sid, testo)
        try:
            reply, _ = brain.think(history, summary=sessions.summaries.get(sid, ""))
        except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
            del history[before:]
            return logs.handle(e)
        sessions.compact_in_background(sid)
        return reply
