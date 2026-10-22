"""Agenda: legge i calendari Google (personale e di lavoro) in SOLA LETTURA dall'indirizzo segreto iCal.
Gestisce gli eventi che si ripetono, le eccezioni, gli orari in UTC e il fuso italiano. Gli indirizzi stanno solo in .env."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import icalendar
import recurring_ical_events

from . import config

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


class AgendaError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.FUSO)
    except Exception:
        raise AgendaError(f"Il fuso orario '{config.FUSO}' non e' valido (JARVIS_FUSO nel .env).")


def _scarica(url: str) -> icalendar.Calendar:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=25)
        r.raise_for_status()
        return icalendar.Calendar.from_ical(r.content)
    except httpx.HTTPStatusError:
        raise AgendaError("Google ha rifiutato l'indirizzo del calendario: forse e' stato reimpostato. Va preso di nuovo.")
    except httpx.HTTPError:
        raise AgendaError("Non riesco a raggiungere il calendario. Controlla internet.")
    except ValueError:
        raise AgendaError("L'indirizzo del calendario non da' un calendario valido.")


def eventi(url: str, day: date) -> list[dict]:
    zone = tz()
    cal = _scarica(url)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day, time(23, 59, 59), tzinfo=zone)
    out = []
    for e in recurring_ical_events.of(cal).between(start, end):
        if str(e.get("STATUS", "")).upper() == "CANCELLED":
            continue
        s = e.get("DTSTART").dt
        f = e.get("DTEND").dt if e.get("DTEND") else None
        titolo = str(e.get("SUMMARY", "")).strip() or "(senza titolo)"
        luogo = str(e.get("LOCATION", "")).strip()
        descrizione = str(e.get("DESCRIPTION", "")).strip()[:600]
        part = e.get("ATTENDEE")
        part = part if isinstance(part, list) else ([part] if part else [])
        partecipanti = []
        for a in part:  # solo i nomi (o la parte prima della @): servono per trovare le persone in rubrica
            nome = str(getattr(a, "params", {}).get("CN", "")).strip() or str(a).replace("mailto:", "").split("@")[0]
            if nome and nome not in partecipanti:
                partecipanti.append(nome[:60])
        extra = {"descrizione": descrizione, "partecipanti": partecipanti[:12]}
        if isinstance(s, datetime):
            s = s.astimezone(zone) if s.tzinfo else s.replace(tzinfo=zone)
            if isinstance(f, datetime):
                f = f.astimezone(zone) if f.tzinfo else f.replace(tzinfo=zone)
            out.append({"tutto_giorno": False, "inizio": s, "fine": f if isinstance(f, datetime) else None, "titolo": titolo, "luogo": luogo, **extra})
        else:
            out.append({"tutto_giorno": True, "inizio": datetime.combine(s, time.min, tzinfo=zone), "fine": None, "titolo": titolo, "luogo": luogo, **extra})
    out.sort(key=lambda x: (not x["tutto_giorno"], x["inizio"]))
    return out


def _riga(ev: dict, day: date) -> str:
    luogo = f" ({ev['luogo']})" if ev["luogo"] else ""
    if ev["tutto_giorno"]:
        return f"- tutto il giorno: {ev['titolo']}{luogo}"
    s, f = ev["inizio"], ev["fine"]
    if s.date() < day:
        quando = f"dal giorno prima, fino alle {f:%H:%M}" if f else "dal giorno prima"
    elif f and f.date() > day:
        quando = f"dalle {s:%H:%M}, continua il giorno dopo"
    else:
        quando = f"{s:%H:%M}-{f:%H:%M}" if f else f"{s:%H:%M}"
    return f"- {quando}: {ev['titolo']}{luogo}"


def _sezione(nome: str, url: str, var: str, day: date) -> str:
    if not url:
        return f"{nome}: NON COLLEGATO (manca {var} nel file .env)."
    try:
        evs = eventi(url, day)
    except AgendaError as e:
        return f"{nome}: ERRORE, {e}"
    return f"{nome}:\n" + ("\n".join(_riga(e, day) for e in evs) if evs else "- nessun impegno")


def parse_day(text: str = "") -> date:
    if not text:
        return datetime.now(tz()).date()
    return datetime.strptime(text, "%Y-%m-%d").date()


def briefing(day_text: str = "") -> str:
    now = datetime.now(tz())
    day = parse_day(day_text)
    quando = f"{GIORNI[day.weekday()]} {day.day} {MESI[day.month - 1]} {day.year}"
    if day == now.date():
        testa = f"Oggi e' {quando}, sono le {now:%H:%M}."
    else:
        testa = f"Agenda di {quando}."
    return "\n".join([
        testa,
        _sezione("CALENDARIO PERSONALE", config.CALENDARIO_PERSONALE_ICS, "CALENDARIO_PERSONALE_ICS", day),
        _sezione("CALENDARIO DI LAVORO", config.CALENDARIO_LAVORO_ICS, "CALENDARIO_LAVORO_ICS", day),
    ])
