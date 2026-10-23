"""Sincronizza la rubrica di Jarvis con i contatti Google di Andrea (sola lettura).
Un piccolo programma Apps Script nel suo account (docs/apps_script_rubrica.gs) li da' a Jarvis; l'indirizzo con la chiave segreta sta in
memoria/rubrica_url.txt (solo sul PC, mai su GitHub). Nomi e numeri restano in memoria/rubrica_google.json: nei registri solo quanti sono."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import httpx

from . import config, logs, whatsapp

URL_FILE = Path(__file__).parent.parent / "memoria" / "rubrica_url.txt"
OGNI_ORE = 3
_stato = {"ultima": 0.0, "n": 0, "errore": ""}
_lock = threading.Lock()


class RubricaError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _indirizzo() -> str:
    try:
        if URL_FILE.exists():
            return URL_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return os.getenv("RUBRICA_URL", "").strip()


def configurata() -> bool:
    return bool(_indirizzo())


def sincronizza() -> str:
    url = _indirizzo()
    if not url:
        raise RubricaError("La sincronizzazione dei contatti non e' ancora configurata.")
    with _lock:
        try:
            r = httpx.get(url, timeout=45, follow_redirects=True)
            dati = r.json()
        except (httpx.HTTPError, ValueError):
            raise RubricaError("Non riesco a leggere i contatti da Google: controlla internet e l'indirizzo in memoria\\rubrica_url.txt.")
        if not isinstance(dati, dict) or dati.get("errore") or "contatti" not in dati:
            raise RubricaError("Google ha rifiutato la richiesta: la chiave dell'indirizzo non corrisponde a quella del programma.")
        google: dict[str, str] = {}
        for c in dati["contatti"]:
            nome = " ".join(str(c.get("nome", "")).split())[:40]
            scelto = None
            for n in c.get("numeri", []):
                try:
                    v = whatsapp._numero(str(n))
                except whatsapp.WhatsAppError:
                    continue
                if scelto is None or (v.startswith("393") and not scelto.startswith("393")):
                    scelto = v
            if nome and scelto:
                google[nome] = scelto
        if not google:
            raise RubricaError("Google non ha mandato nessun contatto con numero: non cambio la rubrica.")
        whatsapp.RUBRICA_GOOGLE.parent.mkdir(parents=True, exist_ok=True)
        tmp = whatsapp.RUBRICA_GOOGLE.with_suffix(".tmp")
        tmp.write_text(json.dumps(google, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(whatsapp.RUBRICA_GOOGLE)
        _stato.update(ultima=time.time(), n=len(google), errore="")
        logs.log_route(f"RUBRICA: sincronizzata con Google ({len(google)} contatti)")
        return f"Rubrica aggiornata: {len(google)} contatti con numero."


def _ciclo():
    while True:
        try:
            sincronizza()
        except RubricaError as e:
            if _stato["errore"] != str(e):  # un errore uguale si scrive una volta sola
                _stato["errore"] = str(e)
                logs.log_route("RUBRICA: " + str(e)[:100])
        except Exception as e:
            logs.log_error(e, "rubrica_sync")
        time.sleep(OGNI_ORE * 3600)


def avvia():
    if configurata():
        threading.Thread(target=_ciclo, daemon=True).start()
