"""Pulizia di fine giornata: Jarvis tiene solo le cose che durano e riparte leggero.
Alle 00:00 (se Jarvis e' acceso) e quando Jarvis si chiude: per ogni conversazione estrae i fatti permanenti (come la compattazione:
niente password, conti, dati dei negozi, dei ragazzi, della banca, mail o WhatsApp), li aggiunge all'archivio (mai cancella ricordi
esistenti) e segna la conversazione da svuotare al PROSSIMO messaggio di Andrea (cosi' non si tocca mai una risposta in corso).
Stato in memoria/pulizia.json (solo la data dell'ultima pulizia). Nel registro: solo numeri."""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, logs, memory, sessions, summarize

STATO = Path(__file__).parent.parent / "memoria" / "pulizia.json"
MIN_MESSAGGI = 4  # sotto questa soglia non c'e' niente da tenere
_lock = threading.Lock()


def _oggi() -> str:
    return datetime.now(ZoneInfo(config.FUSO)).date().isoformat()


def _ultima() -> str:
    try:
        return json.loads(STATO.read_text(encoding="utf-8")).get("ultima", "")
    except (OSError, ValueError):
        return ""


def _segna(giorno: str):
    try:
        STATO.parent.mkdir(parents=True, exist_ok=True)
        STATO.write_text(json.dumps({"ultima": giorno}), encoding="utf-8")
    except OSError:
        pass


def pulisci(svuota: bool = True) -> str:
    """Estrae i fatti dalle conversazioni e, se svuota, le segna da svuotare al prossimo messaggio."""
    with _lock:
        conv = {sid: sessions.text_turns(list(sessions.get(sid))) for sid in list(sessions.histories)}
        prev = dict(sessions.summaries)
        fatti = salvate = 0
        for sid, turni in conv.items():
            if len(turni) < MIN_MESSAGGI:
                continue
            try:
                _, estratti = summarize.compact(turni, prev.get(sid, ""))
            except Exception as e:  # una conversazione non riuscita non blocca le altre
                logs.log_route(f"Pulizia: riassunto non riuscito ({type(e).__name__})")
                continue
            fatti += len(estratti)
            salvate += 1
            for f in estratti:
                memory.remember(f)
        if svuota:
            sessions.svuota_al_prossimo_messaggio(list(sessions.histories))
        logs.log_memory(f"pulizia di fine giornata: {salvate} conversazioni lette, {fatti} fatti passati all'archivio")
        return (f"Pulizia fatta: ho letto {salvate} conversazioni e ho tenuto {fatti} cose che durano."
                + (" Domani riparto leggero." if svuota else ""))


def _ciclo():
    while True:
        time.sleep(60)
        try:
            ora = datetime.now(ZoneInfo(config.FUSO))
            if ora.hour == 0 and ora.minute < 10 and _ultima() != ora.date().isoformat():
                _segna(ora.date().isoformat())
                pulisci()
        except Exception as e:  # la pulizia non deve mai disturbare Jarvis
            logs.log_route(f"Pulizia fallita ({type(e).__name__})")


def avvia():
    if config.ENABLE_PULIZIA:
        threading.Thread(target=_ciclo, daemon=True).start()


def alla_chiusura():
    """Quando Jarvis si chiude le conversazioni (solo in RAM) andrebbero perse: prima si salva quello che dura."""
    if config.ENABLE_PULIZIA:
        try:
            pulisci(svuota=False)
        except Exception as e:
            logs.log_route(f"Pulizia alla chiusura fallita ({type(e).__name__})")
