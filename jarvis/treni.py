"""Treni di Andrea (Gaggiano -> Vigevano): "il mio treno e' in orario, in ritardo o soppresso?".
Fonte NON ufficiale: i dati pubblici di ViaggiaTreno (per Trenord sono parziali). I treni abituali stanno in memoria/treni.json (solo sul PC);
se la fonte non risponde o non conosce il treno, Jarvis lo dice senza inventare. Niente dati personali: solo stazioni e orari dei treni."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from . import config, logs

FILE = Path(__file__).parent.parent / "memoria" / "treni.json"
BASE = "http://www.viaggiatreno.it/infomobilitamobile/resteasy/viaggiatreno"
PREDEFINITO = {"partenza": "Gaggiano", "direzione": ["VIGEVANO", "MORTARA"], "treni": {"apertura": "07:48", "chiusura": "13:18"}}
_cache: dict[str, tuple[float, object]] = {}


class TreniError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _impostazioni() -> dict:
    try:
        if FILE.exists():
            return {**PREDEFINITO, **json.loads(FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        pass
    return dict(PREDEFINITO)


def _get(percorso: str, durata: float = 0.0):
    if durata and percorso in _cache and time.time() - _cache[percorso][0] < durata:
        return _cache[percorso][1]
    try:
        r = httpx.get(BASE + percorso, timeout=15, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
        r.raise_for_status()
        dati = r.text
    except httpx.HTTPError:
        raise TreniError("Non riesco a leggere i dati dei treni adesso: controlla internet o riprova tra poco. Puoi guardare l'app Trenord.")
    _cache[percorso] = (time.time(), dati)
    return dati


def codice_stazione(nome: str) -> tuple[str, str]:
    """(nome, codice) della stazione dal nome."""
    testo = _get("/autocompletaStazione/" + quote(nome), durata=86400)
    for riga in str(testo).splitlines():
        if "|" in riga:
            n, c = riga.split("|", 1)
            if nome.lower() in n.lower():
                return n.strip().title(), c.strip()
    raise TreniError(f"Non trovo la stazione '{nome}' nei dati dei treni.")


def _data_per_api(q: datetime) -> str:
    # esempio atteso dal servizio: "Fri Oct 23 2026 07:30:00 GMT+0200"
    giorni, mesi = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    off = q.strftime("%z") or "+0000"
    return quote(f"{giorni[q.weekday()]} {mesi[q.month - 1]} {q.day:02d} {q.year} {q:%H:%M:%S} GMT{off}")


def partenze(codice: str, quando: datetime) -> list[dict]:
    testo = _get(f"/partenze/{codice}/{_data_per_api(quando)}", durata=45)
    try:
        dati = json.loads(testo)
    except ValueError:
        raise TreniError("I dati dei treni sono arrivati in un formato che non capisco: il servizio potrebbe essere cambiato.")
    return dati if isinstance(dati, list) else []


def _ora_partenza(t: dict) -> str:
    ora = str(t.get("compOrarioPartenza") or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", ora):
        return ora.zfill(5)
    ms = t.get("orarioPartenza")
    if isinstance(ms, (int, float)) and ms > 0:
        return datetime.fromtimestamp(ms / 1000, ZoneInfo(config.FUSO)).strftime("%H:%M")
    return ""


def _frase(t: dict, ora_attesa: str) -> str:
    n = t.get("numeroTreno") or "?"
    dest = str(t.get("destinazione") or "").title()
    ritardo = int(t.get("ritardo") or 0)
    binario = str(t.get("binarioEffettivoPartenzaDescrizione") or t.get("binarioProgrammatoPartenzaDescrizione") or "").strip()
    soppresso = int(t.get("provvedimento") or 0) == 1
    base = f"Il treno delle {ora_attesa} per {dest} (n. {n})"
    if soppresso:
        return base + " risulta SOPPRESSO."
    if ritardo >= 3:
        return base + f" ha {ritardo} minuti di ritardo" + (f", binario {binario}." if binario else ".")
    return base + " risulta in orario" + (f", binario {binario}." if binario else ".")


def stato(ora: str = "", turno: str = "") -> str:
    imp = _impostazioni()
    adesso = datetime.now(ZoneInfo(config.FUSO))
    if not ora:
        treni = imp["treni"]
        if turno and turno.lower() in treni:
            ora = treni[turno.lower()]
        else:  # il prossimo dei treni abituali di oggi
            futuri = sorted(o for o in treni.values() if o >= adesso.strftime("%H:%M"))
            if not futuri:
                raise TreniError("I tuoi treni di oggi sono gia' passati. Dimmi quale orario vuoi controllare.")
            ora = futuri[0]
    ora = ora.replace(".", ":").zfill(5)
    nome, codice = codice_stazione(imp["partenza"])
    h, m = (int(x) for x in ora.split(":"))
    quando = adesso.replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(minutes=10)
    elenco = partenze(codice, quando)
    parole = [p.upper() for p in imp["direzione"]]
    candidati = [t for t in elenco if _ora_partenza(t) == ora]
    giusti = [t for t in candidati if any(p in str(t.get("destinazione", "")).upper() for p in parole)] or candidati
    logs.log_route(f"TRENI: controllo delle {ora} da {nome}: {len(elenco)} partenze lette, {len(giusti)} corrispondenti")
    if not giusti:
        vicini = sorted((t for t in elenco if any(p in str(t.get("destinazione", "")).upper() for p in parole)), key=_ora_partenza)[:3]
        extra = (" Nelle vicinanze vedo: " + "; ".join(f"{_ora_partenza(t)} per {str(t.get('destinazione','')).title()}" for t in vicini) + ".") if vicini else ""
        return f"Non vedo il treno delle {ora} tra le partenze di {nome}: potrebbe non essere ancora tracciato oppure soppresso.{extra} Controlla anche l'app Trenord."
    return _frase(giusti[0], ora)
