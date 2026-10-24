"""Appunti veloci a voce: 'segna che devo ordinare i cavi', 'aggiungi latte alla lista della spesa', 'cosa c'e' nella lista della spesa'.
Liste semplici in memoria/appunti.json (solo sul PC, scrivibili e cancellabili solo da Andrea a voce): niente ora, niente promemoria. Nei registri solo 'APPUNTI: aggiunto/tolto', mai il testo."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from . import logs

FILE = Path(__file__).parent.parent / "memoria" / "appunti.json"
_lock = threading.Lock()
PREDEFINITA = "da fare"


class AppuntiError(Exception):
    pass


def _norma_lista(nome: str) -> str:
    n = re.sub(r"^(?:la\s+)?(?:lista\s+)?(?:della|delle|dei|del|di|da)\s+", "", (nome or "").strip().lower())
    n = n.strip(" .!?'\"")
    return {"": PREDEFINITA, "spesa": "spesa", "cose da fare": PREDEFINITA, "fare": PREDEFINITA, "appunti": PREDEFINITA}.get(n, n[:30] or PREDEFINITA)


def _carica() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {}
    except (OSError, ValueError):
        return {}


def _salva(d: dict):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def aggiungi(testo: str, lista: str = "") -> str:
    testo = re.sub(r"\s+", " ", (testo or "").strip(" .,;"))[:200]
    if not testo:
        raise AppuntiError("Dimmi cosa devo segnare.")
    nome = _norma_lista(lista)
    with _lock:
        d = _carica()
        voci = d.setdefault(nome, [])
        if testo.lower() in (v.lower() for v in voci):
            return f"C'era gia' nella lista {nome}."
        voci.append(testo)
        d[nome] = voci[-100:]
        _salva(d)
    logs.log_route("APPUNTI: aggiunto")
    return f"Segnato nella lista {nome}: {testo}."


def leggi(lista: str = "") -> str:
    with _lock:
        d = _carica()
    nome = _norma_lista(lista) if lista else None
    if nome:
        voci = d.get(nome, [])
        return f"Nella lista {nome}: " + "; ".join(voci) + "." if voci else f"La lista {nome} e' vuota."
    pieni = {k: v for k, v in d.items() if v}
    if not pieni:
        return "Non hai appunti segnati."
    return " ".join(f"{k}: " + "; ".join(v) + "." for k, v in pieni.items())


def togli(testo: str, lista: str = "") -> str:
    """Toglie la voce che contiene le parole dette (o 'tutto' per svuotare la lista)."""
    nome = _norma_lista(lista)
    chiave = (testo or "").strip().lower()
    with _lock:
        d = _carica()
        voci = d.get(nome, [])
        if chiave in ("tutto", "tutta la lista", "svuota"):
            d[nome] = []
            n = len(voci)
        else:
            resto = [v for v in voci if chiave not in v.lower()]
            n = len(voci) - len(resto)
            d[nome] = resto
        _salva(d)
    if n:
        logs.log_route("APPUNTI: tolto")
    return f"Tolte {n} voci dalla lista {nome}." if n else f"Non trovo '{testo}' nella lista {nome}."


# frasi dette a voce, riconosciute senza far ragionare il cervello
_AGGIUNGI_LISTA = re.compile(r"^\W*(?:(?:per favore|puoi|potresti)\W+)?(?:aggiungi|metti|segna|scrivi)\s+(.+?)\s+(?:alla|nella|sulla|in)\s+(lista(?:\s+(?:della|delle|dei|del|di|da)\s+[\w ]+?)?|spesa)\W*$", re.IGNORECASE)
_SEGNA = re.compile(r"^\W*(?:(?:per favore|puoi|potresti)\W+)?(?:segna|appunta|annota|scrivi)(?:mi)?\s+(?:che\s+)?(.+?)\W*$", re.IGNORECASE)
_LEGGI = re.compile(r"^\W*(?:cosa|che cosa|che)\s+(?:c'?\s*(?:e'|è)|ho)\s+(?:nella|sulla|in)\s+(lista[\w ]*|spesa)\W*$|^\W*(?:leggi|dimmi|mostrami)(?:mi)?\s+(?:la\s+)?(lista[\w ]*|appunti|spesa)\W*$|^\W*(?:cosa|che cosa)\s+(?:devo\s+(?:comprare|fare)|ho\s+segnato)\W*$", re.IGNORECASE)


def comando_veloce(testo: str) -> str | None:
    t = (testo or "").strip()
    if len(t) > 160:
        return None
    try:
        m = _AGGIUNGI_LISTA.match(t)
        if m:
            return aggiungi(m.group(1), m.group(2))
        if re.match(r"^\W*(?:cosa|che cosa)\s+devo\s+comprare", t, re.IGNORECASE):
            return leggi("spesa")
        m = _LEGGI.match(t)
        if m:
            return leggi(next((g for g in m.groups() if g), ""))
        m = _SEGNA.match(t)
        if m and not re.search(r"\b(?:promemoria|ricordami|domani|stasera|dopodomani)\b|\balle\s+\d|\btra\s+\d", m.group(1), re.IGNORECASE):
            return aggiungi(m.group(1))
    except AppuntiError as e:
        return str(e)
    return None
