"""Dati per i riquadri della pagina di Jarvis (impegni di oggi, mail non lette, messaggi WhatsApp): solo numeri e il prossimo impegno,
con una memoria breve per non interrogare ogni volta calendario, posta e WhatsApp. Niente di tutto questo viene salvato."""
import time
from datetime import datetime

import httpx

from . import agenda, config, meteo, posta, whatsapp

_cache: dict[str, tuple[float, object]] = {}


def _con_cache(chiave: str, durata: float, f):
    t, v = _cache.get(chiave, (0.0, None))
    if time.time() - t < durata:
        return v
    try:
        v = f()
    except Exception:
        v = None
    _cache[chiave] = (time.time(), v)
    return v


def _agenda():
    if not config.ENABLE_AGENDA:
        return None
    adesso = datetime.now(agenda.tz())
    ev = []
    for url in (config.CALENDARIO_PERSONALE_ICS, config.CALENDARIO_LAVORO_ICS):
        if url:
            ev += agenda.eventi(url, adesso.date())
    prossimi = sorted((e for e in ev if not e["tutto_giorno"] and (e["fine"] or e["inizio"]) >= adesso), key=lambda e: e["inizio"])
    p = prossimi[0] if prossimi else None
    return {"n": len(ev), "prossimo": {"ora": p["inizio"].strftime("%H:%M"), "titolo": p["titolo"][:50]} if p else None}


def _mail():
    if not config.ENABLE_POSTA:
        return None
    out = {}
    for c in posta._configurati():
        m = posta._imap(c)
        try:
            m.select("INBOX", readonly=True)
            out[c] = len(m.uid("search", None, "UNSEEN")[1][0].split())
        finally:
            m.logout()
    return out or None


def _whatsapp():
    if not config.ENABLE_WHATSAPP_LEGGI:
        return None
    st = whatsapp._stato()  # non accende l'helper: se non c'e', niente numeri
    if not st or not st.get("connesso"):
        return None
    chat = httpx.get(whatsapp.HELPER_URL + "/chat", headers=whatsapp._chiave(), timeout=5).json().get("chat", [])
    return {"chat": len(chat), "messaggi": sum(c["non_lette"] for c in chat)}


def dati() -> dict:
    return {"agenda": _con_cache("agenda", 600, _agenda), "mail": _con_cache("mail", 300, _mail), "whatsapp": _con_cache("whatsapp", 20, _whatsapp), "meteo": _con_cache("meteo", 1800, meteo.oggi)}


def azzera(chiave: str):
    _cache.pop(chiave, None)
