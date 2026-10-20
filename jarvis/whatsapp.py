"""WhatsApp, solo canale ufficiale: Jarvis PREPARA il messaggio e apre WhatsApp sul PC con il testo gia' scritto
(collegamento ufficiale 'click to chat'). L'invio lo preme Andrea. Nessuna libreria non ufficiale, nessun accesso alle chat.
Rubrica in memoria/rubrica.json (solo sul PC, mai su GitHub). Il testo dei messaggi resta in RAM: niente su disco ne' nei registri."""
import json
import os
import re
import sys
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import quote

from . import logs, posta

RUBRICA = Path(__file__).parent.parent / "memoria" / "rubrica.json"
_pronti: dict[str, dict] = {}


class WhatsAppError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _numero(testo: str) -> str:
    n = re.sub(r"[^\d+]", "", testo.strip())
    n = n[2:] if n.startswith("00") else n.lstrip("+")
    if re.fullmatch(r"3\d{8,9}", n):  # cellulare italiano senza prefisso
        n = "39" + n
    if not re.fullmatch(r"\d{8,15}", n):
        raise WhatsAppError("Il numero non sembra valido: serve il numero completo, per esempio 333 1234567.")
    return n


def _carica() -> dict:
    if not RUBRICA.exists():
        return {}
    try:
        return json.loads(RUBRICA.read_text(encoding="utf-8"))
    except ValueError:
        raise WhatsAppError("Il file memoria\\rubrica.json non e' leggibile. Non l'ho toccato.")


def salva_contatto(nome: str, numero: str) -> str:
    nome = " ".join(nome.split())[:40]
    if not nome:
        raise WhatsAppError("Dimmi il nome della persona.")
    rubrica = _carica()
    rubrica[nome] = _numero(numero)
    RUBRICA.parent.mkdir(parents=True, exist_ok=True)
    RUBRICA.write_text(json.dumps(rubrica, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"Numero di {nome} salvato (solo sul tuo PC)."


def nomi() -> str:
    r = _carica()
    return "Nella rubrica ci sono: " + ", ".join(sorted(r)) if r else "La rubrica e' vuota."


def _trova(nome: str) -> tuple[str, str]:
    rubrica = _carica()
    n = nome.strip().lower()
    esatti = [k for k in rubrica if k.lower() == n]
    simili = esatti or [k for k in rubrica if n and (n in k.lower() or k.lower() in n)]
    if len(simili) == 1:
        return simili[0], rubrica[simili[0]]
    if len(simili) > 1:
        raise WhatsAppError("Ci sono piu' persone con quel nome: " + ", ".join(sorted(simili)) + ". Quale?")
    if re.search(r"\d{6,}", nome):
        return nome.strip(), _numero(nome)
    raise WhatsAppError(f"Non trovo '{nome}' nella rubrica. Dimmi il numero e lo salvo.")


def prepara(a: str, testo: str) -> str:
    testo = testo.strip()
    if not testo:
        raise WhatsAppError("Manca il testo del messaggio.")
    nome, numero = _trova(a)
    pid = uuid.uuid4().hex[:6]
    _pronti[pid] = {"nome": nome, "numero": numero, "testo": testo[:1000], "turno": posta.turno()}
    return (f"MESSAGGIO {pid} per {nome} (non ancora aperto)\n\n{testo[:1000]}\n\n"
            "Leggilo ad Andrea e chiedi: 'Lo apro in WhatsApp?'. Dopo il suo si' si apre WhatsApp con il testo scritto e lo invia lui.")


def apri(pid: str) -> str:
    p = _pronti.get(pid)
    if not p:
        raise WhatsAppError("Non trovo quel messaggio: ripreparalo.")
    if p["turno"] == posta.turno():
        raise WhatsAppError("Prima Andrea deve vedere il messaggio e dirti di aprirlo: aspetta il suo si'.")
    testo = quote(p["testo"])
    app = f"whatsapp://send?phone={p['numero']}&text={testo}"
    web = f"https://wa.me/{p['numero']}?text={testo}"
    try:
        if sys.platform == "win32":
            os.startfile(app)  # type: ignore[attr-defined]  # app WhatsApp sul PC
        else:
            webbrowser.open(web)
    except OSError:
        webbrowser.open(web)  # se l'app non c'e', WhatsApp Web
    del _pronti[pid]
    logs.log_azione("WHATSAPP aperto con messaggio pronto, invio da parte di Andrea (contenuto non salvato)")
    return f"Ho aperto WhatsApp con il messaggio per {p['nome']}. Premi Invio per mandarlo."
