"""Scrittura sul calendario Google, SOLO dopo il 'Si' di Andrea sulla scheda. Un piccolo programma Apps Script nel suo account (docs/apps_script_calendario.gs) puo'
soltanto creare appuntamenti (mai cancellare o cambiare). L'indirizzo con la chiave segreta sta in memoria/calendario_url.txt (solo sul PC, mai su GitHub).
Nei registri solo 'appuntamento aggiunto', mai titolo, persona o luogo."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from . import logs

URL_FILE = {  # due account Google separati: un collegamento ciascuno
    "personale": Path(__file__).parent.parent / "memoria" / "calendario_url.txt",
    "lavoro": Path(__file__).parent.parent / "memoria" / "calendario_lavoro_url.txt",
}


class CalendarioError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _indirizzo(cal: str = "personale") -> str:
    f = URL_FILE.get(cal, URL_FILE["personale"])
    try:
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return os.getenv("CALENDARIO_LAVORO_SCRITTURA_URL" if cal == "lavoro" else "CALENDARIO_SCRITTURA_URL", "").strip()


def configurato(cal: str = "personale") -> bool:
    return bool(_indirizzo(cal))


def _chiama(azione: str, titolo: str, inizio: str, fine: str, luogo: str = "", cal: str = "personale") -> dict:
    url = _indirizzo(cal)
    if not url:
        raise CalendarioError(f"Il collegamento per scrivere sul calendario {cal} non c'e' ancora.")
    try:
        r = httpx.get(url, params={"azione": azione, "titolo": titolo, "inizio": inizio, "fine": fine, "luogo": luogo, "cal": cal}, follow_redirects=True, timeout=30)
        r.raise_for_status()
        d = r.json()
    except (httpx.HTTPError, ValueError):
        raise CalendarioError("Non riesco a parlare con il calendario Google adesso: riprova tra poco.")
    if not d.get("ok"):
        raise CalendarioError("Il calendario ha rifiutato la richiesta: " + str(d.get("errore", "controlla il collegamento"))[:80])
    return d


def controlla(titolo: str, inizio: str, fine: str, cal: str = "personale") -> dict:
    """{'conflitti': [{'titolo','inizio'}], 'gia_presente': bool}. inizio/fine nel formato 2026-10-29T15:00 (ora italiana)."""
    d = _chiama("controlla", titolo, inizio, fine, cal=cal)
    return {"conflitti": d.get("conflitti", []), "gia_presente": bool(d.get("gia_presente"))}


def crea(titolo: str, inizio: str, fine: str, luogo: str = "", cal: str = "personale") -> str:
    d = _chiama("crea", titolo, inizio, fine, luogo, cal)
    logs.log_route("CALENDARIO: appuntamento aggiunto" if d.get("creato") else "CALENDARIO: appuntamento gia' presente")
    return "C'era gia', non l'ho duplicato." if d.get("gia_presente") else "Fatto, e' sul calendario."
