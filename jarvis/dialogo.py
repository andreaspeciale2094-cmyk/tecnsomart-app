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


def rispondi_stream(sid: str, testo: str):
    """Come rispondi, ma a pezzi: produce il testo man mano che Claude (o Groq) lo scrive, cosi' la voce parte alla prima frase."""
    with _lock:
        history, before = sessions.start_request(sid, testo)
        try:
            for ev in brain.think_stream(history, summary=sessions.summaries.get(sid, "")):
                if ev["type"] == "text" and ev.get("delta"):
                    yield ev["delta"]
        except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
            del history[before:]
            yield logs.handle(e)
            return
        sessions.compact_in_background(sid)
