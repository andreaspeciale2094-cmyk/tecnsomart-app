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

from . import config, logs, trenord

FILE = Path(__file__).parent.parent / "memoria" / "treni.json"
BASE = "http://www.viaggiatreno.it/infomobilitamobile/resteasy/viaggiatreno"
PREDEFINITO = {"partenza": "Gaggiano", "direzione": ["ALBAIRATE", "VIGEVANO", "MORTARA"], "treni": {"apertura": "07:48", "chiusura": "13:18"}}
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


def _unisci(nome: str, codice: str, quando: datetime) -> list[dict]:
    """Partenze da Trenord (il sito ufficiale, solo se si guarda l'ora presente: mostra le prossime) piu' quelle di ViaggiaTreno per gli orari che Trenord non ha."""
    adesso = datetime.now(ZoneInfo(config.FUSO))
    out: list[dict] = []
    if abs((quando - adesso).total_seconds()) < 3 * 3600:
        try:
            out = trenord.partenze(nome)
        except trenord.TrenordError as e:
            logs.log_route("TRENI: Trenord non letto (" + str(e)[:60] + ")")
    try:
        vt = partenze(codice, quando)
    except TreniError:
        if not out:
            raise
        vt = []
    visti = {_ora_partenza(t) for t in out}
    return out + [t for t in vt if _ora_partenza(t) not in visti]


def _ora_partenza(t: dict) -> str:
    ora = str(t.get("compOrarioPartenza") or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", ora):
        return ora.zfill(5)
    ms = t.get("orarioPartenza")
    if isinstance(ms, (int, float)) and ms > 0:
        return datetime.fromtimestamp(ms / 1000, ZoneInfo(config.FUSO)).strftime("%H:%M")
    return ""


def _provv(t: dict) -> str:
    """'' se regolare, altrimenti CANCELLATO / CANCELLATO IN PARTE / DEVIATO."""
    try:
        p = int(t.get("provvedimento") or 0)
    except (TypeError, ValueError):
        p = 0
    return {1: "CANCELLATO", 2: "CANCELLATO IN PARTE", 3: "DEVIATO"}.get(p, "")


def _frase(t: dict, ora_attesa: str) -> str:
    n = t.get("numeroTreno") or "?"
    dest = str(t.get("destinazione") or "").title()
    ritardo = int(t.get("ritardo") or 0)
    binario = str(t.get("binarioEffettivoPartenzaDescrizione") or t.get("binarioProgrammatoPartenzaDescrizione") or "").strip()
    provv = _provv(t)
    base = f"Il treno delle {ora_attesa} per {dest} (n. {n})"
    if provv:
        return base + f" risulta {provv}."
    if ritardo >= 3:
        return base + f" ha {ritardo} minuti di ritardo" + (f", binario {binario}." if binario else ".")
    return base + " risulta in orario" + (f", binario {binario}." if binario else ".")


def _etichetta(t: dict) -> str:
    ritardo = int(t.get("ritardo") or 0)
    stato = _provv(t) or (f"{ritardo} min di ritardo" if ritardo >= 3 else "in orario")
    return f"{_ora_partenza(t)} per {str(t.get('destinazione','')).title()} (n. {t.get('numeroTreno') or '?'}): {stato}"


def stato(ora: str = "", turno: str = "", stazione: str = "", direzione: str = "", numero: str = "") -> str:
    """Stato di un treno qualunque: per orario (ora), per numero del treno, oppure i prossimi da una stazione (anche verso una direzione).
    Senza niente: i treni abituali di Andrea (apertura/chiusura) dalla sua stazione."""
    imp = _impostazioni()
    adesso = datetime.now(ZoneInfo(config.FUSO))
    sua = not stazione or stazione.strip().lower() == str(imp["partenza"]).lower()
    nome, codice = codice_stazione(stazione.strip() if stazione.strip() else imp["partenza"])
    parole = [p.strip().upper() for p in (direzione.replace(",", " ").split() if direzione.strip() else (imp["direzione"] if sua and not numero else []))]
    verso = lambda t: not parole or any(p in str(t.get("destinazione", "")).upper() for p in parole)

    if not ora and turno and sua and turno.lower() in imp["treni"]:
        ora = imp["treni"][turno.lower()]
    if not ora and not numero and not direzione and sua:  # nessuna richiesta precisa: il prossimo dei treni abituali di oggi
        futuri = sorted(o for o in imp["treni"].values() if o >= adesso.strftime("%H:%M"))
        if futuri:
            ora = futuri[0]
    if ora:
        ora = ora.replace(".", ":").zfill(5)
        h, m = (int(x) for x in ora.split(":"))
        quando = adesso.replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(minutes=10)
        elenco = _unisci(nome, codice, quando)
        candidati = [t for t in elenco if _ora_partenza(t) == ora]
        giusti = [t for t in candidati if verso(t)] or candidati
        logs.log_route(f"TRENI: controllo delle {ora} da {nome}: {len(elenco)} partenze lette, {len(giusti)} corrispondenti")
        if giusti:
            return _frase(giusti[0], ora)
        vicini = sorted((t for t in elenco if verso(t)), key=_ora_partenza)[:3]
        extra = (" Nelle vicinanze vedo: " + "; ".join(_etichetta(t) for t in vicini) + ".") if vicini else ""
        return f"Non vedo il treno delle {ora} tra le partenze di {nome}: potrebbe non essere ancora tracciato oppure cancellato.{extra} Controlla anche l'app Trenord."
    elenco = _unisci(nome, codice, adesso)
    logs.log_route(f"TRENI: prossime partenze da {nome}: {len(elenco)} lette")
    if numero:
        trovati = [t for t in elenco if str(t.get("numeroTreno")) == str(numero).strip()]
        return ("Treno " + _etichetta(trovati[0]) + f" da {nome}.") if trovati else f"Il treno {numero} non risulta tra le prossime partenze di {nome}."
    prossimi = sorted((t for t in elenco if verso(t)), key=_ora_partenza)[:4]
    if not prossimi:
        return f"Non vedo partenze da {nome}" + (f" verso {direzione}" if direzione else "") + " nei dati: controlla l'app Trenord."
    return f"Prossime da {nome}" + (f" verso {direzione}" if direzione else "") + ": " + "; ".join(_etichetta(t) for t in prossimi) + "."


def fascia(da: str, a: str, giorno: str = "", stazione: str = "", direzione: str = "") -> str:
    """Treni in partenza da una stazione tra due orari (anche domani). Il servizio da' le partenze di circa un'ora e mezza, quindi si chiede a passi."""
    imp = _impostazioni()
    fuso = ZoneInfo(config.FUSO)
    oggi = datetime.now(fuso)
    base = oggi + timedelta(days=1) if giorno.strip().lower() in ("domani", "tomorrow") else oggi
    nome, codice = codice_stazione(stazione.strip() or imp["partenza"])
    sua = not stazione.strip() or stazione.strip().lower() == str(imp["partenza"]).lower()
    parole = [p.strip().upper() for p in (direzione.replace(",", " ").split() if direzione.strip() else (imp["direzione"] if sua else []))]
    h1, m1 = (int(x) for x in da.replace(".", ":").split(":")) if da else (oggi.hour, oggi.minute)
    h2, m2 = (int(x) for x in a.replace(".", ":").split(":")) if a else (min(h1 + 3, 23), m1)
    inizio = base.replace(hour=h1, minute=m1, second=0, microsecond=0)
    fine = base.replace(hour=h2, minute=m2, second=0, microsecond=0)
    trovati: dict[str, dict] = {}
    q = inizio
    while q <= fine + timedelta(minutes=45):
        try:
            lista = _unisci(nome, codice, q)
        except TreniError:
            lista = []
        for t in lista:
            o = _ora_partenza(t)
            if o and f"{h1:02d}:{m1:02d}" <= o <= f"{h2:02d}:{m2:02d}":
                trovati[f"{t.get('numeroTreno')}-{o}"] = t
        q += timedelta(minutes=60)
    giusti = sorted((t for t in trovati.values() if not parole or any(p in str(t.get("destinazione", "")).upper() for p in parole)), key=_ora_partenza)
    logs.log_route(f"TRENI: fascia {h1:02d}:{m1:02d}-{h2:02d}:{m2:02d} da {nome}: {len(trovati)} partenze lette, {len(giusti)} mostrate")
    quando = "domani" if base.date() != oggi.date() else "oggi"
    if not giusti:
        extra = " Gli orari di domani il servizio spesso non li ha ancora." if quando == "domani" else ""
        return f"Non vedo partenze da {nome} tra le {da or 'adesso'} e le {a} ({quando}) nei dati.{extra} Non vuol dire che non ci siano treni: controlla l'orario sull'app Trenord."
    canc = sum(1 for t in giusti if _provv(t))
    testa = f"{canc} cancellat{'o' if canc == 1 else 'i'}. " if canc else "Nessun treno cancellato. "
    return f"Da {nome}, {quando}, tra le {h1:02d}:{m1:02d} e le {h2:02d}:{m2:02d}: " + testa + "; ".join(_etichetta(t) for t in giusti[:12]) + "."


FILE_TURNO = Path(__file__).parent.parent / "memoria" / "turno.json"


def imposta_turno(turno: str, giorno: str = "") -> str:
    """Segna che turno fa Andrea (apertura/chiusura/riposo) per oggi o domani. Il vigile controlla solo il treno di quel turno."""
    turno = turno.strip().lower()
    if turno not in ("apertura", "chiusura", "riposo"):
        raise TreniError("Il turno puo' essere apertura, chiusura o riposo.")
    oggi = datetime.now(ZoneInfo(config.FUSO)).date()
    d = oggi + timedelta(days=1) if giorno.strip().lower() in ("domani", "tomorrow") else oggi
    try:
        dati = json.loads(FILE_TURNO.read_text(encoding="utf-8")) if FILE_TURNO.exists() else {}
    except (OSError, ValueError):
        dati = {}
    dati = {k: v for k, v in dati.items() if k >= oggi.isoformat()}  # via i giorni passati
    dati[d.isoformat()] = turno
    FILE_TURNO.parent.mkdir(parents=True, exist_ok=True)
    FILE_TURNO.write_text(json.dumps(dati), encoding="utf-8")
    return f"Segnato: {'domani' if d != oggi else 'oggi'} {turno}."


def turno_del_giorno(giorno=None) -> str:
    """'apertura' / 'chiusura' / 'riposo' se Andrea l'ha detto per quel giorno, altrimenti ''."""
    giorno = giorno or datetime.now(ZoneInfo(config.FUSO)).date()
    try:
        return str(json.loads(FILE_TURNO.read_text(encoding="utf-8")).get(giorno.isoformat(), "")) if FILE_TURNO.exists() else ""
    except (OSError, ValueError):
        return ""


def controllo_turno(turno: str) -> dict | None:
    """Per il vigile: stato del treno abituale del turno. {'ora', 'stato': orario|ritardo|cancellato|non_visto, 'ritardo', 'frase'} o None se non ci sono treni per quel turno."""
    imp = _impostazioni()
    ora = imp["treni"].get(turno)
    if not ora:
        return None
    adesso = datetime.now(ZoneInfo(config.FUSO))
    h, m = (int(x) for x in ora.split(":"))
    nome, codice = codice_stazione(imp["partenza"])
    elenco = _unisci(nome, codice, adesso)
    cand = [t for t in elenco if _ora_partenza(t) == ora]
    parole = [p.upper() for p in imp["direzione"]]
    t = next((t for t in cand if not parole or any(p in str(t.get("destinazione", "")).upper() for p in parole)), cand[0] if cand else None)
    if t is None:
        return {"ora": ora, "stato": "non_visto", "ritardo": 0, "frase": f"Il treno delle {ora} non lo vedo nei dati: controlla l'app Trenord."}
    ritardo = int(t.get("ritardo") or 0)
    provv = _provv(t)
    if provv:
        return {"ora": ora, "stato": "cancellato" if provv.startswith("CANCELLATO") and "PARTE" not in provv else "ritardo", "ritardo": ritardo, "frase": f"Attenzione: il treno delle {ora} risulta {provv}."}
    if ritardo >= 3:
        return {"ora": ora, "stato": "ritardo", "ritardo": ritardo, "frase": f"Il treno delle {ora} ha {ritardo} minuti di ritardo."}
    return {"ora": ora, "stato": "orario", "ritardo": 0, "frase": f"Il tuo treno delle {ora} e' in orario."}
