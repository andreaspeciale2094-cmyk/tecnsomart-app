"""Risposte immediate, senza far ragionare il cervello: domande semplici a cui basta un dato gia' pronto (ora, data, meteo, mail e WhatsApp nuovi, impegni, treno)
e promemoria detti a voce. Se la frase non e' una di queste ritorna None e si va avanti come sempre. Nessun testo privato nei registri."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, logs

_GIORNI = ["lunedi'", "martedi'", "mercoledi'", "giovedi'", "venerdi'", "sabato", "domenica"]
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _adesso() -> datetime:
    return datetime.now(ZoneInfo(config.FUSO))


def _dati_pannello() -> dict:
    from . import pannello
    return pannello.dati() or {}


def _ora(_):
    return f"Sono le {_adesso().strftime('%H:%M')}."


def _data(_):
    a = _adesso()
    return f"Oggi e' {_GIORNI[a.weekday()]} {a.day} {_MESI[a.month - 1]}."


def _meteo(t: str):
    from . import meteo
    if re.search(r"\bdomani\b", t):
        f = meteo.frase_domani()
        return f or "Non riesco a sapere il meteo adesso."
    m = meteo.oggi()
    if not m:
        return "Non riesco a sapere il meteo adesso."
    frase = f"A {m['citta']} ora {m['temp']} gradi, {m['cond']}; oggi tra {m['min']} e {m['max']}"
    return frase + (f", pioggia {m['pioggia']}%." if m["pioggia"] >= 30 else ".")


def _mail(_):
    p = _dati_pannello().get("mail")
    if not p:
        return None
    tot = sum(p.values())
    return "Non hai mail non lette." if not tot else f"Hai {tot} mail non lette: " + ", ".join(f"{k} {n}" for k, n in p.items() if n) + "."


def _whatsapp(_):
    w = _dati_pannello().get("whatsapp")
    if w is None:
        return None
    return "Nessun messaggio WhatsApp nuovo." if not w["messaggi"] else f"{w['messaggi']} messaggi WhatsApp da {w['chat']} chat."


def _impegni(t: str):
    if re.search(r"\bdomani\b", t):
        from . import agenda
        ev = []
        for url in (config.CALENDARIO_PERSONALE_ICS, config.CALENDARIO_LAVORO_ICS):
            if url:
                ev += agenda.eventi(url, (_adesso() + timedelta(days=1)).date())
        ev.sort(key=lambda e: (e["tutto_giorno"], e["inizio"]))
        if not ev:
            return "Domani non hai impegni."
        primo = next((e for e in ev if not e["tutto_giorno"]), None)
        return f"Domani hai {len(ev)} impegn{'o' if len(ev) == 1 else 'i'}" + (f", il primo alle {primo['inizio'].strftime('%H:%M')}: {primo['titolo']}." if primo else f": {ev[0]['titolo']}.")
    ag = _dati_pannello().get("agenda")
    if ag is None:
        return None
    if not ag["n"]:
        return "Oggi non hai impegni."
    s = f"Oggi hai {ag['n']} impegn{'o' if ag['n'] == 1 else 'i'}"
    return s + (f", il prossimo alle {ag['prossimo']['ora']}: {ag['prossimo']['titolo']}." if ag.get("prossimo") else ", per oggi non ce ne sono altri.")


def _treno(_):
    from . import treni
    return treni.stato()


_REGOLE = [
    (re.compile(r"\bche\s+ore\s+sono\b|\bche\s+ora\s+(?:e'|è)(?=\W|$)|\bdimmi\s+l'?ora\b", re.I), _ora, None),
    (re.compile(r"\bche\s+giorno\s+(?:e'|è)(?=\W|$)|\bche\s+data\s+(?:e'|è)(?=\W|$)|\bquanti\s+ne\s+abbiamo\b", re.I), _data, None),
    (re.compile(r"\bche\s+tempo\s+fa\b|\bcom'?\s*(?:e'|è)\s+il\s+tempo\b|\bpiove\b|\bombrello\b|\bmeteo\b|\bquanti\s+gradi\b", re.I), _meteo, "meteo"),
    (re.compile(r"\b(?:ho|ci\s+sono|ci\s+sono\s+delle?)\s+(?:nuove\s+)?(?:mail|e-?mail|email|posta)\b|\bquante\s+(?:mail|email)\b", re.I), _mail, "mail"),
    (re.compile(r"\b(?:ho|ci\s+sono)\s+(?:nuovi\s+)?messaggi\b|\bquanti\s+messaggi\b|\bmessaggi\s+whatsapp\s+nuovi\b|\bho\s+(?:messaggi|whatsapp)\b", re.I), _whatsapp, "whatsapp"),
    (re.compile(r"\b(?:che|quali)\s+impegni\s+ho\b|\bcosa\s+ho\s+(?:oggi|domani)\b|\bprossimo\s+impegno\b|\bho\s+impegni\b", re.I), _impegni, "impegni"),
    (re.compile(r"\bcom'?\s*(?:e'|è)\s+il\s+mio\s+treno\b|\bil\s+mio\s+treno\s+(?:e'|è)(?=\W|$)|\bil\s+treno\s+(?:e'|è)\s+(?:in\s+orario|in\s+ritardo|cancellato)\b", re.I), _treno, "treni"),
]
_NON_ADESSO = re.compile(r"\b(?:ieri|settimana|mese|prossima|scorsa)\b", re.I)


def promemoria_a_voce(testo: str) -> str | None:
    """'ricordami alle 17 di chiamare Marco', 'ricordami tra 20 minuti di ...', 'ricordami domani alle 9 di ...'. Il promemoria e' una cosa piccola e annullabile (si toglie a voce)."""
    from . import promemoria
    t = testo.strip()
    if not re.match(r"^\W*(?:(?:per favore|puoi|potresti)\W+)?ricordami\b", t, re.I) or len(t) > 200:
        return None
    t = re.sub(r"^\W*(?:(?:per favore|puoi|potresti)\W+)?ricordami\s*", "", t, flags=re.I)
    giorno = ""
    m = re.match(r"(domani|dopodomani)\s+", t, re.I)
    if m:
        giorno = "domani" if m.group(1).lower() == "domani" else ""
        t = t[m.end():]
        if m.group(1).lower() == "dopodomani":
            return None  # si fa col cervello
    try:
        m = re.match(r"tra\s+(\d+|un|una|mezz'ora)\s*(minuti|minuto|ore|ora|mezz'ora)?\s+(?:di\s+|che\s+)?(.+)$", t, re.I)
        if m:
            n, unita, cosa = m.group(1).lower(), (m.group(2) or "").lower(), m.group(3)
            minuti = 30 if "mezz" in n or "mezz" in unita else (int(n) if n.isdigit() else 1) * (60 if unita.startswith("or") else 1)
            return promemoria.crea(cosa, tra_minuti=minuti)
        m = re.match(r"(?:alle|alle\s+ore)\s+(\d{1,2})(?:[:.](\d{2}))?\s+(?:di\s+|che\s+)?(.+)$", t, re.I)
        if m:
            return promemoria.crea(m.group(3), ora=f"{int(m.group(1)):02d}:{m.group(2) or '00'}", giorno=giorno)
        m = re.match(r"(?:di\s+)?(.+?)\s+(?:alle|alle\s+ore)\s+(\d{1,2})(?:[:.](\d{2}))?$", t, re.I)
        if m:
            return promemoria.crea(m.group(1), ora=f"{int(m.group(2)):02d}:{m.group(3) or '00'}", giorno=giorno)
        m = re.match(r"(?:di\s+)?(.+?)\s+tra\s+(\d+)\s*(minuti|minuto|ore|ora)$", t, re.I)
        if m:
            return promemoria.crea(m.group(1), tra_minuti=int(m.group(2)) * (60 if m.group(3).lower().startswith("or") else 1))
    except promemoria.PromemoriaError as e:
        return str(e)
    return None


def rispondi(testo: str) -> str | None:
    """La risposta immediata se la frase e' una di queste, altrimenti None."""
    t = (testo or "").strip()
    if not t or len(t) > 90:
        return promemoria_a_voce(t) if t and len(t) <= 200 and config.ENABLE_PROMEMORIA else None
    if config.ENABLE_PROMEMORIA:
        r = promemoria_a_voce(t)
        if r:
            return r
    if _NON_ADESSO.search(t):
        return None
    for regola, fn, flag in _REGOLE:
        if regola.search(t):
            if flag == "treni" and not config.ENABLE_TRENI:
                return None
            try:
                r = fn(t)
            except Exception as e:
                logs.log_error(e, "risposta veloce")
                return None
            if r:
                logs.log_route("VELOCE: risposta senza cervello (" + (flag or fn.__name__.strip("_")) + ")")
                return r
            return None
    return None
