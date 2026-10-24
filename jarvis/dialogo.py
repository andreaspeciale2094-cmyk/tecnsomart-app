"""Una conversazione con Jarvis da un canale diverso dalla pagina (Telegram, ascolto in stanza): una richiesta alla volta."""
import threading

from . import brain, fase, logs, sessions

_lock = threading.Lock()
strumento = {"nome": ""}   # cosa sta controllando Jarvis adesso (serve a dire la frase d'attesa giusta, es. 'Controllo il treno.')


def _veloce(testo: str):
    """Risposte immediate (ora, meteo, mail, impegni, treno, appunti, promemoria) senza far ragionare il cervello."""
    try:
        from . import appunti, veloci
        return appunti.comando_veloce(testo) or veloci.rispondi(testo)
    except Exception as e:
        logs.log_error(e, "dialogo veloce")
        return None


def rispondi(sid: str, testo: str) -> str:
    r = _veloce(testo)
    if r:
        return r
    with _lock:
        history, before = sessions.start_request(sid, testo)
        fase.imposta("capisco")
        try:
            reply, _ = brain.think(history, summary=sessions.summaries.get(sid, ""))
        except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
            del history[before:]
            return logs.handle(e)
        sessions.compact_in_background(sid)
        return reply


def rispondi_stream(sid: str, testo: str):
    """Come rispondi, ma a pezzi: produce il testo man mano che Claude (o Groq) lo scrive, cosi' la voce parte alla prima frase."""
    r = _veloce(testo)
    if r:
        yield r
        return
    with _lock:
        history, before = sessions.start_request(sid, testo)
        try:
            fase.imposta("capisco")
            strumento["nome"] = ""
            for ev in brain.think_stream(history, summary=sessions.summaries.get(sid, "")):
                if ev["type"] == "tool":
                    strumento["nome"] = str(ev.get("name", ""))
                if ev["type"] == "text" and ev.get("delta"):
                    fase.imposta("rispondo")
                    yield ev["delta"]
        except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
            del history[before:]
            yield logs.handle(e)
            return
        sessions.compact_in_background(sid)
