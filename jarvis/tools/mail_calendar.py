"""Mail (IMAP, sola lettura) e calendario (feed iCal segreto, sola lettura). Nessun OAuth necessario."""
import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

import httpx
from .. import config

SCHEMAS = [
    {
        "name": "unread_emails",
        "description": "Elenca mittente e oggetto delle ultime mail non lette.",
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
    {
        "name": "upcoming_events",
        "description": "Eventi del calendario nei prossimi N giorni (default 7).",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}},
    },
]


def unread_emails(limit: int = 10):
    if not (config.IMAP_USER and config.IMAP_PASSWORD):
        return "Mail non configurata (IMAP_USER / IMAP_PASSWORD nel .env)."
    m = imaplib.IMAP4_SSL(config.IMAP_HOST)
    m.login(config.IMAP_USER, config.IMAP_PASSWORD)
    m.select("INBOX", readonly=True)
    _, data = m.search(None, "UNSEEN")
    out = []
    for num in reversed(data[0].split()[-limit:]):
        _, msg = m.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        h = email.message_from_bytes(msg[0][1])
        dec = lambda v: str(make_header(decode_header(v or "")))
        out.append(f"{dec(h['From'])} | {dec(h['Subject'])}")
    m.logout()
    return out or "Nessuna mail non letta."


def _parse_dt(v: str):
    v = v.strip()
    try:
        if v.endswith("Z"):
            return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if "T" in v:
            return datetime.strptime(v, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        return datetime.strptime(v, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def upcoming_events(days: int = 7):
    if not config.CALENDAR_ICS_URL:
        return "Calendario non configurato (CALENDAR_ICS_URL nel .env)."
    text = httpx.get(config.CALENDAR_ICS_URL, timeout=20, follow_redirects=True).text
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold
    now, end = datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=days)
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        s = re.search(r"DTSTART[^:]*:(\S+)", block)
        t = re.search(r"SUMMARY[^:]*:(.*)", block)
        start = _parse_dt(s.group(1)) if s else None
        if start and now <= start <= end:
            events.append((start, t.group(1).strip() if t else "(senza titolo)"))
    events.sort()
    return [f"{d:%a %d/%m %H:%M} UTC - {t}" for d, t in events] or "Nessun evento."


HANDLERS = {"unread_emails": unread_emails, "upcoming_events": upcoming_events}
