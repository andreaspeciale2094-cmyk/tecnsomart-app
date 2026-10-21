"""Telegram: parlare con Jarvis dal telefono (testo e messaggi vocali). Risponde SOLO all'account di Andrea (TELEGRAM_USER_ID).
Funziona finche' Jarvis e' acceso sul PC (il telefono scrive al bot, Jarvis legge da internet: nessuna porta aperta sul PC).
Il contenuto dei messaggi non va mai nei registri. Messaggi vecchi (ricevuti a Jarvis spento) non vengono eseguiti."""
import threading
import time

import httpx

from . import ascolto, config, dialogo, logs, voice

SESSIONE = "telegram"
ETA_MAX = 15 * 60  # secondi: un messaggio piu' vecchio non si esegue
_avvisato_sconosciuto = False


def _api(metodo: str, **dati) -> dict:
    r = httpx.post(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{metodo}", json=dati, timeout=65)
    r.raise_for_status()
    return r.json()


def _scrivi(chat: int, testo: str):
    testo = testo.strip() or "..."
    for i in range(0, len(testo), 4000):
        _api("sendMessage", chat_id=chat, text=testo[i:i + 4000])


def _ascolta(file_id: str) -> str:
    info = _api("getFile", file_id=file_id)["result"]
    audio = httpx.get(f"https://api.telegram.org/file/bot{config.TELEGRAM_TOKEN}/{info['file_path']}", timeout=60).content
    return voice.transcribe(audio, "audio/ogg")


def _rispondi(testo: str) -> str:
    return dialogo.rispondi(SESSIONE, testo)


def gestisci(update: dict):
    """Un messaggio in arrivo. Ignora chiunque non sia Andrea."""
    global _avvisato_sconosciuto
    m = update.get("message") or {}
    chat = (m.get("chat") or {}).get("id")
    mittente = (m.get("from") or {}).get("id")
    if not chat or (m.get("chat") or {}).get("type") != "private":
        return
    if not config.TELEGRAM_USER_ID:  # modalita' di preparazione: dice solo il numero dell'account, non esegue niente
        _scrivi(chat, f"Ciao! Il tuo numero e' {mittente}. Scrivilo nel file .env come TELEGRAM_USER_ID={mittente} e riavvia Jarvis: da quel momento rispondo solo a te.")
        return
    if str(mittente) != str(config.TELEGRAM_USER_ID):
        if not _avvisato_sconosciuto:
            _avvisato_sconosciuto = True
            logs.log_route("TELEGRAM: messaggio da un account non autorizzato, ignorato")
        return
    if time.time() - m.get("date", time.time()) > ETA_MAX:
        _scrivi(chat, "Ho ricevuto un tuo messaggio mentre ero spento e non lo eseguo, per sicurezza. Rimandalo, se serve.")
        return
    try:
        _api("sendChatAction", chat_id=chat, action="typing")
        if m.get("text") and m["text"].strip().lower().rstrip("!. ") in ("ascolto off", "/ascolto_off", "ascolto spento", "ascolto on", "/ascolto_on", "ascolto acceso"):
            acceso = m["text"].strip().lower().rstrip("!. ") in ("ascolto on", "/ascolto_on", "ascolto acceso")
            ascolto.imposta(acceso)
            _scrivi(chat, "Ascolto in stanza acceso." if acceso else "Ascolto in stanza spento: il microfono e' libero. Scrivi 'ascolto on' per riaccenderlo.")
            return
        if m.get("text"):
            testo = m["text"]
        elif m.get("voice") or m.get("audio"):
            if not voice.stt_available():
                _scrivi(chat, "Non posso ascoltare i vocali: manca il riconoscimento vocale. Scrivimi il messaggio.")
                return
            testo = _ascolta((m.get("voice") or m.get("audio"))["file_id"])
        else:
            _scrivi(chat, "Per ora capisco solo testo e messaggi vocali.")
            return
        _scrivi(chat, _rispondi(testo))
    except Exception as e:  # il bot non deve mai fermarsi per un errore
        logs.log_error(e, "telegram")
        try:
            _scrivi(chat, "Ho avuto un problema con questo messaggio. Riprova tra poco.")
        except Exception:
            pass


def _ciclo():
    offset = None
    while True:
        try:
            r = _api("getUpdates", timeout=50, offset=offset, allowed_updates=["message"])
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                threading.Thread(target=gestisci, args=(u,), daemon=True).start()
        except Exception as e:
            logs.log_error(e, "telegram: collegamento")
            time.sleep(10)


def avvia():
    if config.ENABLE_TELEGRAM and config.TELEGRAM_TOKEN:
        threading.Thread(target=_ciclo, daemon=True).start()
