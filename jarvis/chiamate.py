"""Telefonate: Jarvis fa PARTIRE la chiamata dal PC (con il programma Windows che usa il telefono, "Collegamento al telefono"/Phone Link),
ma solo dopo il si' di Andrea, a persone della rubrica, una chiamata alla volta. Non risponde e non parla al posto suo.
Numeri e nomi solo in RAM e nella rubrica sul PC (mai nei registri)."""
from __future__ import annotations

import os
import re
import sys
import time
import uuid

import httpx

from . import config, logs, posta, whatsapp

_pronte: dict[str, dict] = {}


class ChiamataError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


class ChiamataAmbigua(ChiamataError):
    """Piu' persone in rubrica con quel nome: `nomi` sono le voci tra cui scegliere."""

    def __init__(self, nomi: list[str]):
        self.nomi = nomi
        super().__init__("Ci sono piu' persone con quel nome: " + "; ".join(parlabile(n) for n in nomi) + ". Quale?")


_STOP = {"il", "la", "lo", "l", "di", "del", "della", "da", "a", "quello", "quella", "e", "per", "favore", "piacere"}


def _parole(testo: str) -> list[str]:
    return [p for p in re.findall(r"[\wàèéìòù]+", testo.lower()) if p not in _STOP]


def parlabile(chiave: str) -> str:
    """'Marco Rossi (lavoro)' -> 'Marco Rossi, lavoro' (cosi' la voce non legge le parentesi)."""
    return re.sub(r"\s*\(([^)]*)\)", r", \1", chiave).strip(" ,")


def candidati(chi: str) -> list[str]:
    """Le voci della rubrica che corrispondono a quel che hai detto: ignora le parentesi se il nome e' uguale, accetta nomi parziali,
    e in generale tutte le parole dette devono comparire nella voce (anche quelle tra parentesi, tipo 'lavoro')."""
    try:
        rubrica = whatsapp._carica()
    except whatsapp.WhatsAppError as e:
        raise ChiamataError(str(e))
    n = " ".join(_parole(chi))
    if not n:
        return []
    senza = lambda k: " ".join(_parole(re.sub(r"\([^)]*\)", "", k)))
    esatti = [k for k in rubrica if senza(k) == n or " ".join(_parole(k)) == n]
    if esatti:
        return esatti
    dette = set(n.split())
    return [k for k in rubrica if dette <= set(_parole(k))]


def prepara_veloce(chi: str, chiave: str | None = None) -> tuple[str, str]:
    """(id, nome) della chiamata preparata, senza avviarla. `chiave` = voce esatta della rubrica (dopo aver scelto tra piu' persone)."""
    if chiave is None and re.search(r"\d{6,}", re.sub(r"[\s.\-]", "", chi)):
        try:  # un numero detto a voce
            nome, numero, _ = whatsapp._trova(chi)
        except whatsapp.WhatsAppError as e:
            raise ChiamataError(str(e))
    else:
        if chiave is None:
            trovati = candidati(chi)
            if not trovati:
                raise ChiamataError(f"Non trovo '{chi.strip()}' nella rubrica. Dimmi il numero e lo salvo.")
            if len(trovati) > 1:
                raise ChiamataAmbigua(trovati)
            chiave = trovati[0]
        try:
            nome, numero = chiave, whatsapp._carica()[chiave]
        except (KeyError, whatsapp.WhatsAppError):
            raise ChiamataError("Non trovo piu' quella voce in rubrica.")
    for k in [k for k, v in _pronte.items() if time.time() - v["t"] > 600]:
        _pronte.pop(k, None)  # le chiamate preparate scadono dopo 10 minuti
    cid = uuid.uuid4().hex[:6]
    _pronte[cid] = {"nome": nome, "numero": numero, "turno": posta.turno(), "t": time.time()}
    logs.log_route("CHIAMATA: preparata (in attesa del si')")
    return cid, nome


def prepara(chi: str) -> str:
    cid, nome = prepara_veloce(chi)
    numero = _pronte[cid]["numero"]
    nome = parlabile(nome)
    cifre = numero[-10:] if len(numero) > 10 else numero
    return (f"CHIAMATA {cid} a {nome} (numero che finisce per {cifre[-4:]}), non ancora avviata. "
            "Chiedi ad Andrea: 'Chiamo {nome}?'. Solo dopo il suo si' in un messaggio successivo usa chiama_avvia.").replace("{nome}", nome)


def avvia(cid: str, da_voce: bool = False) -> str:
    """da_voce=True solo dal percorso veloce dell'ascolto in stanza, che ha chiesto 'Chiamo X?' e ha sentito il si' di Andrea in una frase SUCCESSIVA."""
    p = _pronte.get(cid)
    if not p:
        raise ChiamataError("Non trovo quella chiamata: preparala di nuovo.")
    if p["turno"] == posta.turno() and not da_voce:
        raise ChiamataError("Prima Andrea deve sentire a chi chiami e dirti di si': aspetta il suo si'.")
    if time.time() - p["t"] > 600:
        _pronte.pop(cid, None)
        raise ChiamataError("La chiamata e' scaduta: preparala di nuovo.")
    logs.log_route(f"CHIAMATA: invio al telefono ({'indirizzo del telefono impostato' if config.TELEFONO_URL else 'NESSUN indirizzo del telefono: uso il programma di Windows'}; numero di {len(p['numero'])} cifre che inizia per {p['numero'][:2]})")
    if config.TELEFONO_URL:  # la chiamata la fa il telefono, senza finestre sul PC
        try:
            parametri = {"numero": "+" + p["numero"]}  # il telefono compone il numero con il prefisso internazionale
            if config.TELEFONO_CHIAVE:
                parametri["chiave"] = config.TELEFONO_CHIAVE
            r = httpx.get(config.TELEFONO_URL, params=parametri, timeout=8)
        except httpx.HTTPError as e:
            logs.log_route(f"CHIAMATA: telefono non raggiungibile ({type(e).__name__})")
            raise ChiamataError("Non raggiungo il telefono: controlla che sia acceso, con Tailscale e MacroDroid attivi.")
        logs.log_route(f"CHIAMATA: il telefono ha risposto {r.status_code}")
        if r.status_code >= 400:
            raise ChiamataError("Il telefono ha risposto con un errore: controlla la regola in MacroDroid.")
        del _pronte[cid]
        logs.log_azione("CHIAMATA avviata dal telefono (numero non salvato)")
        return f"Ho mandato al telefono il comando di chiamare {parlabile(p['nome'])}. Non dire 'sta squillando': non lo sai."
    if sys.platform != "win32":
        raise ChiamataError("Le chiamate si avviano solo dal PC Windows di Andrea.")
    try:
        os.startfile("tel:+" + p["numero"])  # type: ignore[attr-defined]  # il programma del telefono di Windows
    except OSError:
        raise ChiamataError("Windows non ha un programma per le telefonate: apri 'Collegamento al telefono' (Phone Link), collega il telefono e riprova.")
    del _pronte[cid]
    logs.log_azione("CHIAMATA avviata dal PC (numero non salvato)")
    return (f"Ho avviato la chiamata a {parlabile(p['nome'])}. Se si e' fermata sul tastierino, Andrea deve premere il tasto verde. "
            "Non dire 'sta squillando': non lo sai.")
