"""Dietro ai riquadri cliccabili della pagina (impegni, WhatsApp): dettagli degli impegni, chat, risposte.
Regola: un messaggio parte SOLO dopo che Andrea ha visto il testo e ha premuto 'Invia' (il clic e' il suo si'), una persona alla volta, solo a chi e' in rubrica.
Testi di impegni e messaggi passano solo dalla pagina di Andrea (RAM): niente su disco, niente nei registri."""
import re
import time
import unicodedata
from datetime import datetime

from . import agenda, config, logs, whatsapp


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t)


# ---------------- impegni ----------------
def contatti_evento(ev: dict) -> list[str]:
    """Persone della rubrica che compaiono nell'impegno (nome e cognome interi nel titolo, nella descrizione o tra i partecipanti)."""
    try:
        rubrica = whatsapp._carica()
    except whatsapp.WhatsAppError:
        return []
    testo = _norm(" ".join([ev.get("titolo", ""), ev.get("descrizione", ""), ev.get("luogo", "")] + list(ev.get("partecipanti", []))))
    parole = set(testo.split())
    trovati = []
    for nome in rubrica:
        toks = _norm(nome).split()
        if len(toks) >= 2 and all(t in parole for t in toks):
            trovati.append(nome)
    return sorted(trovati, key=lambda n: -len(n))[:5]


def impegni(data_text: str = "") -> dict:
    """Impegni del giorno con i dettagli, calendario personale e di lavoro separati."""
    giorno = agenda.parse_day(data_text)
    out = []
    for nome, url, var in (("personale", config.CALENDARIO_PERSONALE_ICS, "CALENDARIO_PERSONALE_ICS"), ("lavoro", config.CALENDARIO_LAVORO_ICS, "CALENDARIO_LAVORO_ICS")):
        voce = {"calendario": nome, "errore": "", "eventi": []}
        if not url:
            voce["errore"] = "Non collegato."
        else:
            try:
                for e in agenda.eventi(url, giorno):
                    if e["tutto_giorno"]:
                        quando = "tutto il giorno"
                    else:
                        quando = f"{e['inizio']:%H:%M}" + (f"–{e['fine']:%H:%M}" if e["fine"] else "")
                    voce["eventi"].append({"quando": quando, "titolo": e["titolo"], "luogo": e["luogo"], "descrizione": e.get("descrizione", ""),
                                           "partecipanti": e.get("partecipanti", []), "contatti": contatti_evento(e)})
            except agenda.AgendaError as err:
                voce["errore"] = str(err)
            except Exception:
                voce["errore"] = "Non riesco a leggere il calendario."
        out.append(voce)
    return {"giorno": f"{giorno:%d/%m/%Y}", "calendari": out}


# ---------------- WhatsApp ----------------
def rubrica_nomi() -> list[str]:
    try:
        return sorted(whatsapp._carica(), key=str.lower)
    except whatsapp.WhatsAppError:
        return []


def chat_lista() -> list[dict]:
    chat = whatsapp._helper_json("/chat").get("chat", [])
    rubrica_per_numero = {}
    try:
        rubrica_per_numero = {n: k for k, n in whatsapp._carica().items()}
    except whatsapp.WhatsAppError:
        pass
    return [{"id": c["id"], "nome": whatsapp._nome_chat(c), "non_lette": c["non_lette"],
             "in_rubrica": c.get("numero", "") in rubrica_per_numero} for c in chat[:30]]


def chat_messaggi(chat_id: str) -> dict:
    from urllib.parse import quote
    r = whatsapp._helper_json(f"/messaggi?id={quote(chat_id)}&n=10")
    if not r.get("ok"):
        raise whatsapp.WhatsAppError("Non ho messaggi recenti di questa chat.")
    numero = r.get("numero", "")
    nome = whatsapp._nome_chat(r)
    in_rubrica, rispondi_a = False, ""
    gruppo = bool(r.get("gruppo"))
    try:
        rubrica = whatsapp._carica()
        in_rubrica = any(n == numero for n in rubrica.values()) if numero else False
        if numero and in_rubrica:
            rispondi_a = next(k for k, n in rubrica.items() if n == numero)
        elif not numero and not gruppo and r.get("nome"):
            # WhatsApp a volte non da' il numero (contatti con numero nascosto): se il NOME coincide con una sola voce della rubrica si risponde a quella
            def norma(t: str) -> str:
                return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t.lower())).strip()
            uguali = [k for k in rubrica if norma(k) == norma(r["nome"])]
            if len(uguali) == 1:
                in_rubrica, rispondi_a = True, uguali[0]
    except whatsapp.WhatsAppError:
        pass
    return {"nome": nome, "numero_noto": bool(numero), "in_rubrica": in_rubrica, "gruppo": gruppo, "rispondi_a": rispondi_a,
            "messaggi": [{"da_me": bool(m["da_me"]), "testo": (m["chi"] + ": " if m.get("chi") else "") + m["testo"], "ora": datetime.fromtimestamp(m["ts"]).strftime("%H:%M")} for m in r["messaggi"]]}


def prepara_gruppo(chat_id: str, testo: str) -> dict:
    """Prepara un messaggio per un gruppo gia' in archivio (NON lo invia). Il nome del gruppo lo prende il server dalla chat, non dalla pagina."""
    from urllib.parse import quote
    testo = (testo or "").strip()
    if not testo:
        raise whatsapp.WhatsAppError("Scrivi prima il testo del messaggio.")
    r = whatsapp._helper_json(f"/messaggi?id={quote(chat_id)}&n=1&segna=0")
    if not r.get("ok") or not r.get("gruppo"):
        raise whatsapp.WhatsAppError("Questo gruppo non e' nell'archivio: non posso scrivergli.")
    out = whatsapp.prepara_gruppo(chat_id, r.get("nome") or "gruppo", testo)
    pid = re.search(r"MESSAGGIO (\w+) per", out).group(1)
    p = whatsapp._pronti[pid]
    return {"pid": pid, "nome": p["nome"], "testo": p["testo"], "in_rubrica": True, "gruppo": True}


def prepara(a: str, testo: str, numero_chat: str = "") -> dict:
    """Prepara il messaggio (NON lo invia) e ritorna cio' che la pagina deve far vedere ad Andrea."""
    testo = (testo or "").strip()
    if not testo:
        raise whatsapp.WhatsAppError("Scrivi prima il testo del messaggio.")
    out = whatsapp.prepara(a, testo)
    pid = re.search(r"MESSAGGIO (\w+) per", out).group(1)
    p = whatsapp._pronti[pid]
    return {"pid": pid, "nome": p["nome"], "testo": p["testo"], "in_rubrica": p["in_rubrica"]}


def invia_dopo_si(pid: str) -> str:
    """Invia il messaggio preparato. Va chiamato solo dal pulsante 'Invia' dopo che Andrea ha visto il testo: serve almeno 1 secondo dalla preparazione."""
    p = whatsapp._pronti.get(pid)
    if not p:
        raise whatsapp.WhatsAppError("Non trovo quel messaggio: preparalo di nuovo.")
    if time.time() - p.get("t", 0) < 1.0:
        raise whatsapp.WhatsAppError("Leggi prima il messaggio, poi premi Invia.")
    out = whatsapp.invia(pid, da_pagina=True)
    logs.log_azione("WHATSAPP inviato dalla pagina dopo il si' di Andrea (contenuto non salvato)")
    return out


def salva_da_chat(chat_id: str, nome: str) -> str:
    """Mette in rubrica la persona di una chat (il numero lo prende il programma, non passa dalla pagina)."""
    from urllib.parse import quote
    r = whatsapp._helper_json(f"/messaggi?id={quote(chat_id)}&n=1")
    if not r.get("ok") or not r.get("numero"):
        raise whatsapp.WhatsAppError("Di questa chat WhatsApp non mi dice il numero: salvalo a mano dicendomelo.")
    return whatsapp.salva_contatto(nome, r["numero"])
