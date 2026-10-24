"""Il Milan con il calendario vero: football-data.org (gratuito, serve una chiave personale in .env come FOOTBALL_DATA_KEY).
Prima della partita (circa un'ora) e a partita finita Jarvis avvisa; a richiesta dice quando gioca e com'e' finita. Senza chiave resta l'agente che legge i titoli dei giornali.
I dati stanno solo in RAM; nei registri mai nomi di squadre o punteggi."""
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from . import config

SQUADRA = 98  # AC Milan su football-data.org
_cache = {"t": 0.0, "dati": None}


def attivo() -> bool:
    return bool(config.FOOTBALL_DATA_KEY)


def _giorno(utc: str) -> datetime:
    return datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ZoneInfo(config.FUSO))


def partite(max_eta: float = 600) -> list[dict]:
    """Le partite del Milan da 3 giorni fa a 21 giorni avanti (cache in RAM). Alza un errore se la chiave non va o internet manca."""
    if not attivo():
        raise RuntimeError("manca FOOTBALL_DATA_KEY")
    if _cache["dati"] is not None and time.time() - _cache["t"] < max_eta:
        return _cache["dati"]
    oggi = datetime.now(ZoneInfo(config.FUSO)).date()
    r = httpx.get(f"https://api.football-data.org/v4/teams/{SQUADRA}/matches", timeout=12, headers={"X-Auth-Token": config.FOOTBALL_DATA_KEY},
                  params={"dateFrom": (oggi - timedelta(days=3)).isoformat(), "dateTo": (oggi + timedelta(days=21)).isoformat()})
    r.raise_for_status()
    out = []
    for m in r.json().get("matches", []):
        ft = (m.get("score") or {}).get("fullTime") or {}
        out.append({"id": m["id"], "quando": _giorno(m["utcDate"]), "stato": m.get("status", ""), "coppa": (m.get("competition") or {}).get("name", ""),
                    "casa": (m.get("homeTeam") or {}).get("shortName") or (m.get("homeTeam") or {}).get("name", ""), "ospite": (m.get("awayTeam") or {}).get("shortName") or (m.get("awayTeam") or {}).get("name", ""),
                    "gol_casa": ft.get("home"), "gol_ospite": ft.get("away"), "milan_in_casa": (m.get("homeTeam") or {}).get("id") == SQUADRA})
    out.sort(key=lambda x: x["quando"])
    _cache.update(t=time.time(), dati=out)
    return out


def _avversario(p: dict) -> str:
    return p["ospite"] if p["milan_in_casa"] else p["casa"]


def frase_prima(p: dict) -> str:
    return f"Milan {'contro' if p['milan_in_casa'] else 'a'} {_avversario(p)}, {p['coppa'] or 'partita'}, alle {p['quando']:%H:%M}."


def frase_dopo(p: dict) -> str:
    g, o = (p["gol_casa"], p["gol_ospite"]) if p["milan_in_casa"] else (p["gol_ospite"], p["gol_casa"])
    if g is None or o is None:
        return f"Finita Milan {_avversario(p)}."
    esito = "vince" if g > o else "perde" if g < o else "pareggia"
    return f"Finita: il Milan {esito} con {_avversario(p)}, {g} a {o}."


def prossime() -> str:
    """Per 'quando gioca il Milan' e 'com'e' finita'."""
    try:
        pp = partite()
    except Exception as e:
        return "Non riesco a leggere il calendario del Milan (" + ("manca la chiave" if "chiave" in str(e) else type(e).__name__) + ")."
    ora = datetime.now(ZoneInfo(config.FUSO))
    finite = [p for p in pp if p["stato"] == "FINISHED"]
    in_corso = [p for p in pp if p["stato"] in ("IN_PLAY", "PAUSED", "LIVE")]
    prossime_ = [p for p in pp if p["stato"] not in ("FINISHED", "CANCELLED", "POSTPONED", "IN_PLAY", "PAUSED", "LIVE") and p["quando"] + timedelta(hours=3) > ora]
    righe = []
    for p in in_corso:
        g, o = (p["gol_casa"], p["gol_ospite"]) if p["milan_in_casa"] else (p["gol_ospite"], p["gol_casa"])
        righe.append(f"IN CORSO: Milan con {_avversario(p)}, {g if g is not None else 0} a {o if o is not None else 0} (dati ufficiali con qualche minuto di ritardo; i marcatori non ci sono: per quelli cerca su internet con la ricerca web).")
    if finite:
        righe.append("Ultima: " + frase_dopo(finite[-1]) + f" ({finite[-1]['quando']:%d/%m})")
    for p in prossime_[:3]:
        righe.append(f"{p['quando']:%d/%m %H:%M}: " + frase_prima(p))
    return "\n".join(righe) or "Non vedo partite del Milan nelle prossime settimane."
