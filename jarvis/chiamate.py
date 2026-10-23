"""Telefonate: Jarvis fa PARTIRE la chiamata dal PC (con il programma Windows che usa il telefono, "Collegamento al telefono"/Phone Link),
ma solo dopo il si' di Andrea, a persone della rubrica, una chiamata alla volta. Non risponde e non parla al posto suo.
Numeri e nomi solo in RAM e nella rubrica sul PC (mai nei registri)."""
from __future__ import annotations

import os
import sys
import time
import uuid

import httpx

from . import config, logs, posta, whatsapp

_pronte: dict[str, dict] = {}


class ChiamataError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def prepara(chi: str) -> str:
    try:
        nome, numero, in_rubrica = whatsapp._trova(chi)
    except whatsapp.WhatsAppError as e:
        raise ChiamataError(str(e))
    for k in [k for k, v in _pronte.items() if time.time() - v["t"] > 600]:
        _pronte.pop(k, None)  # le chiamate preparate scadono dopo 10 minuti
    cid = uuid.uuid4().hex[:6]
    _pronte[cid] = {"nome": nome, "numero": numero, "turno": posta.turno(), "t": time.time()}
    cifre = numero[-10:] if len(numero) > 10 else numero
    return (f"CHIAMATA {cid} a {nome} (numero che finisce per {cifre[-4:]}), non ancora avviata. "
            "Chiedi ad Andrea: 'Chiamo {nome}?'. Solo dopo il suo si' in un messaggio successivo usa chiama_avvia.").replace("{nome}", nome)


def avvia(cid: str) -> str:
    p = _pronte.get(cid)
    if not p:
        raise ChiamataError("Non trovo quella chiamata: preparala di nuovo.")
    if p["turno"] == posta.turno():
        raise ChiamataError("Prima Andrea deve sentire a chi chiami e dirti di si': aspetta il suo si'.")
    if time.time() - p["t"] > 600:
        _pronte.pop(cid, None)
        raise ChiamataError("La chiamata e' scaduta: preparala di nuovo.")
    if config.TELEFONO_URL:  # la chiamata la fa il telefono, senza finestre sul PC
        try:
            parametri = {"numero": "+" + p["numero"]}  # il telefono compone il numero con il prefisso internazionale
            if config.TELEFONO_CHIAVE:
                parametri["chiave"] = config.TELEFONO_CHIAVE
            r = httpx.get(config.TELEFONO_URL, params=parametri, timeout=8)
        except httpx.HTTPError:
            raise ChiamataError("Non raggiungo il telefono: controlla che sia acceso, con Tailscale e MacroDroid attivi.")
        if r.status_code >= 400:
            raise ChiamataError("Il telefono ha risposto con un errore: controlla la regola in MacroDroid.")
        del _pronte[cid]
        logs.log_azione("CHIAMATA avviata dal telefono (numero non salvato)")
        return f"Ho mandato al telefono il comando di chiamare {p['nome']}. Non dire 'sta squillando': non lo sai."
    if sys.platform != "win32":
        raise ChiamataError("Le chiamate si avviano solo dal PC Windows di Andrea.")
    try:
        os.startfile("tel:+" + p["numero"])  # type: ignore[attr-defined]  # il programma del telefono di Windows
    except OSError:
        raise ChiamataError("Windows non ha un programma per le telefonate: apri 'Collegamento al telefono' (Phone Link), collega il telefono e riprova.")
    del _pronte[cid]
    logs.log_azione("CHIAMATA avviata dal PC (numero non salvato)")
    return (f"Ho avviato la chiamata a {p['nome']}. Se si e' fermata sul tastierino, Andrea deve premere il tasto verde. "
            "Non dire 'sta squillando': non lo sai.")
