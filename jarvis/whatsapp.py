"""WhatsApp. Due modi:
1) canale ufficiale: Jarvis PREPARA il messaggio e apre WhatsApp sul PC con il testo gia' scritto ('click to chat'); l'invio lo preme Andrea.
2) invio senza finestre (JARVIS_WHATSAPP_INVIO=true, eccezione alla regola 5 decisa da Andrea il 20/10/2026, con rischio di blocco del
   numero accettato): un piccolo programma di appoggio (whatsapp_helper/, collegamento non ufficiale, SOLO INVIO) manda il messaggio.
   Parte solo dopo il si' di Andrea, solo a persone della rubrica, con pause tra un messaggio e l'altro, e si chiude con Jarvis.
Rubrica in memoria/rubrica.json (solo sul PC, mai su GitHub). Il testo dei messaggi resta in RAM: niente su disco ne' nei registri."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import quote

import httpx

from . import logs, posta

RUBRICA = Path(__file__).parent.parent / "memoria" / "rubrica.json"
_pronti: dict[str, dict] = {}
HELPER_DIR = Path(__file__).parent.parent / "whatsapp_helper"
TOKEN_FILE = Path(__file__).parent.parent / "memoria" / "whatsapp" / "token.txt"
HELPER_URL = "http://127.0.0.1:8787"
_figlio: subprocess.Popen | None = None


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


def _trova(nome: str) -> tuple[str, str, bool]:
    """(nome, numero, e' in rubrica)"""
    rubrica = _carica()
    n = nome.strip().lower()
    esatti = [k for k in rubrica if k.lower() == n]
    simili = esatti or [k for k in rubrica if n and (n in k.lower() or k.lower() in n)]
    if len(simili) == 1:
        return simili[0], rubrica[simili[0]], True
    if len(simili) > 1:
        raise WhatsAppError("Ci sono piu' persone con quel nome: " + ", ".join(sorted(simili)) + ". Quale?")
    if re.search(r"\d{6,}", re.sub(r"[\s.\-]", "", nome)):
        return nome.strip(), _numero(nome), False
    raise WhatsAppError(f"Non trovo '{nome}' nella rubrica. Dimmi il numero e lo salvo.")


def prepara(a: str, testo: str) -> str:
    testo = testo.strip()
    if not testo:
        raise WhatsAppError("Manca il testo del messaggio.")
    nome, numero, in_rubrica = _trova(a)
    pid = uuid.uuid4().hex[:6]
    _pronti[pid] = {"nome": nome, "numero": numero, "testo": testo[:1000], "turno": posta.turno(), "in_rubrica": in_rubrica}
    return (f"MESSAGGIO {pid} per {nome} (non ancora aperto)\n\n{testo[:1000]}\n\n"
            "Leggilo ad Andrea e chiedi: 'Lo apro in WhatsApp?'. Dopo il suo si': se hai lo strumento whatsapp_invia lo mandi tu senza finestre, altrimenti si apre WhatsApp e lo invia lui.")


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


# ---------------- invio senza finestre (programma di appoggio) ----------------
def _chiave() -> dict:
    if not TOKEN_FILE.exists():
        return {}
    return {"x-token": TOKEN_FILE.read_text(encoding="utf-8").strip()}


def _stato() -> dict | None:
    try:
        r = httpx.get(HELPER_URL + "/stato", headers=_chiave(), timeout=3)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _avvia_helper() -> dict:
    """Avvia il programma di appoggio nascosto (si chiude insieme a Jarvis) e aspetta che sia pronto."""
    global _figlio
    st = _stato()
    if st is not None:
        return st
    node = shutil.which("node")
    if not node or not (HELPER_DIR / "node_modules").exists():
        raise WhatsAppError("Manca il programma di appoggio per WhatsApp: serve Node.js e l'installazione fatta una volta con 3_collega_whatsapp.bat.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    _figlio = subprocess.Popen([node, "server.js"], cwd=HELPER_DIR, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=flags, env={**os.environ, "JARVIS_FIGLIO": "1"})
    for _ in range(40):
        time.sleep(0.5)
        st = _stato()
        if st is not None and (st.get("connesso") or st.get("bisogna_qr") or st.get("errore")):
            return st
    raise WhatsAppError("Il programma di appoggio di WhatsApp non e' partito. Riprova tra poco.")


def invia(pid: str) -> str:
    p = _pronti.get(pid)
    if not p:
        raise WhatsAppError("Non trovo quel messaggio: ripreparalo.")
    if p["turno"] == posta.turno():
        raise WhatsAppError("Prima Andrea deve vedere il messaggio e dirti di inviarlo: aspetta il suo si'.")
    if not p.get("in_rubrica"):
        raise WhatsAppError("Senza finestre invio solo a persone della rubrica: salva prima il numero con il suo nome.")
    st = _avvia_helper()
    if st.get("bloccato") or st.get("errore") and not st.get("connesso"):
        raise WhatsAppError(st.get("errore") or "WhatsApp non e' collegato.")
    if not st.get("connesso"):
        raise WhatsAppError("WhatsApp non e' ancora collegato: va fatto una volta con 3_collega_whatsapp.bat (codice da scansionare con il telefono).")
    try:
        r = httpx.post(HELPER_URL + "/invia", headers=_chiave(), json={"numero": p["numero"], "testo": p["testo"]}, timeout=90).json()
    except (httpx.HTTPError, ValueError):
        raise WhatsAppError("Non sono riuscito a parlare con il programma di WhatsApp. Il messaggio non e' partito.")
    if not r.get("ok"):
        raise WhatsAppError("Il messaggio non e' partito: " + str(r.get("errore", "errore sconosciuto")))
    del _pronti[pid]
    logs.log_azione("WHATSAPP inviato senza finestre (contenuto non salvato)")
    return f"Messaggio inviato a {p['nome']}."


def chiudi_helper():
    if _figlio and _figlio.poll() is None:
        _figlio.terminate()
