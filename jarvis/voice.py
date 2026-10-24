import hashlib
"""Voce naturale: TTS (ElevenLabs / OpenAI) e STT (Whisper)."""
import asyncio
import re
import time
from pathlib import Path

import httpx
from . import config, logs

try:
    import edge_tts  # voce neurale gratuita, senza chiave
except ImportError:
    edge_tts = None


_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]+")


_UNITA = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci", "undici", "dodici", "tredici",
          "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove"]
_DECINE = {2: "venti", 3: "trenta", 4: "quaranta", 5: "cinquanta"}


def numero_parlato(n: int) -> str:
    """0-59 in lettere (ventitre', quarantotto...), per leggere gli orari in modo corretto."""
    if n < 20:
        return _UNITA[n]
    dec, un = _DECINE[n // 10], n % 10
    if un == 0:
        return dec
    if un in (1, 8):
        return dec[:-1] + _UNITA[un]
    return dec + ("tr\u00e9" if un == 3 else _UNITA[un])


def _ora_parlata(m: re.Match) -> str:
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return m.group(0)
    ore = "una" if h == 1 else numero_parlato(h)
    return ore if mi == 0 else f"{ore} e {numero_parlato(mi)}"


def clean_for_speech(text: str) -> str:
    """Toglie tutto cio' che una voce legge male: markdown, link, emoji, simboli."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)  # [testo](url) -> testo
    t = re.sub(r"https?://\S+", " link ", t)
    t = re.sub(r"\b(\d{1,2}):(\d{2})\b", _ora_parlata, t)  # 23:27 -> "ventitre' e ventisette"
    t = _EMOJI.sub(" ", t)
    t = re.sub(r"\b[A-ZÀ-Ý]{4,}\b", lambda m: m.group(0).lower(), t)  # FISSO FASTWEB, SKY MOBILE: in maiuscolo la voce multilingue sbaglia lingua e parla 'quasi spagnolo'
    t = re.sub(r"[*_`#>|~]+", " ", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    t = (t.replace("&", " e ").replace("%", " per cento").replace("°C", " gradi").replace("°", " gradi")
          .replace("€", " euro").replace("$", " dollari").replace("/", " "))
    t = re.sub(r"\s*\n+\s*", ". ", t)  # a capo = pausa
    t = re.sub(r"([.!?])\s*\.", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def tts_available() -> bool:
    return bool(config.ELEVENLABS_API_KEY or config.OPENAI_API_KEY or edge_tts)


def _edge_synthesize(text: str) -> bytes:
    async def run():
        c = edge_tts.Communicate(text, config.EDGE_VOICE, rate=config.EDGE_RATE, pitch=config.EDGE_PITCH)
        return b"".join([ch["data"] async for ch in c.stream() if ch["type"] == "audio"])

    audio = asyncio.run(run())  # chiamata da un thread del server: nessun loop attivo
    if not audio:
        raise RuntimeError("Edge TTS non ha restituito audio")
    return audio


def stt_available() -> bool:
    return bool(config.GROQ_API_KEY or config.OPENAI_API_KEY)  # riconoscimento vocale: Groq (veloce, economico) oppure OpenAI


_down: dict[str, float] = {}  # voce -> fino a quando saltarla dopo un errore


def _elevenlabs(text: str) -> bytes:
    r = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        json={"text": text, "model_id": "eleven_multilingual_v2",
              "voice_settings": {"stability": 0.65, "similarity_boost": 0.8, "style": 0.2, "use_speaker_boost": True}},
        timeout=60,
    )
    r.raise_for_status()
    return r.content


def _openai(text: str) -> bytes:
    r = httpx.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={"model": "gpt-4o-mini-tts", "voice": config.OPENAI_VOICE, "input": text, "instructions": config.VOICE_STYLE},
        timeout=60,
    )
    r.raise_for_status()
    return r.content


def _providers() -> list[tuple[str, object]]:
    mode, order = config.VOICE_MODE, []
    if mode in ("auto", "elevenlabs") and config.ELEVENLABS_API_KEY:
        order.append(("elevenlabs", _elevenlabs))
    if mode in ("auto", "openai") and config.OPENAI_API_KEY:
        order.append(("openai", _openai))
    if edge_tts:
        order.append(("edge", _edge_synthesize))  # gratuita: sempre l'ultimo ripiego
    return order


def synthesize(text: str) -> bytes:
    return synthesize_named(text)[0]


def synthesize_named(text: str) -> tuple[bytes, str]:
    """Come synthesize, ma dice anche quale voce ha risposto (elevenlabs, openai, edge)."""
    text = clean_for_speech(text)[:2500]
    if not re.search(r"[A-Za-z0-9\u00C0-\u024F]", text):
        raise ValueError("niente da leggere")  # solo simboli o vuoto: nessuna voce lo saprebbe leggere
    last = None
    for name, fn in _providers():
        if _down.get(name, 0) > time.time():
            continue  # fallita da poco: non perdiamo tempo a riprovare a ogni frase
        try:
            return fn(text), name
        except Exception as e:
            last = e
            _down[name] = time.time() + (600 if name != "edge" else 30)
            logs.log_voice(name, e)
    raise last or RuntimeError("nessuna voce disponibile")


def transcribe(audio: bytes, content_type: str) -> str:
    """Voce -> testo. Prima Groq (whisper, economico e veloce) se c'e' la chiave, altrimenti o se non risponde OpenAI."""
    ext = "mp4" if "mp4" in content_type else "ogg" if "ogg" in content_type else "wav" if "wav" in content_type else "webm"
    ultimo = None
    for nome, url, chiave, modello in (
        ("groq", "https://api.groq.com/openai/v1/audio/transcriptions", config.GROQ_API_KEY, config.GROQ_STT_MODEL),
        ("openai", "https://api.openai.com/v1/audio/transcriptions", config.OPENAI_API_KEY, "whisper-1"),
    ):
        if not chiave:
            continue
        try:
            r = httpx.post(url, headers={"Authorization": f"Bearer {chiave}"}, files={"file": (f"audio.{ext}", audio, content_type)},
                           data={"model": modello, "language": "it"}, timeout=60)
            r.raise_for_status()
            return r.json()["text"].strip()
        except Exception as e:  # ripiega sull'altro servizio
            ultimo = e
            logs.log_voice(f"riconoscimento {nome}", e)
    raise ultimo or RuntimeError("nessun servizio di riconoscimento vocale configurato")


# ---- Frasi fisse: create una volta, salvate su disco, riprodotte subito mentre Jarvis pensa ----
FIXED_DIR = Path(__file__).parent.parent / "audio_fisse"
FIXED_PHRASES = {
    "attesa1": "Un attimo.",
    "attesa2": "Ci penso io.",
    "attesa3": "Subito.",
    "attesa4": "Vediamo.",
    # dette se un lavoro dura piu' di 3 secondi (mai silenzio)
    "stato_cerca": "Sto cercando online.",
    "stato_pagina": "Sto leggendo la pagina.",
    "stato_memoria": "Controllo la memoria.",
    "stato_ancora": "Ci sto ancora lavorando.",
    # dette mentre Jarvis controlla una cosa precisa (al posto del solito 'Un attimo')
    "stato_treno": "Controllo il treno.",
    "stato_mail": "Guardo la posta.",
    "stato_whatsapp": "Guardo i messaggi.",
    "stato_negozi": "Guardo i numeri.",
    "stato_agenda": "Guardo l'agenda.",
    "stato_banca": "Guardo il conto.",
}


def _voice_id(name: str) -> str:
    ident = {"elevenlabs": config.ELEVENLABS_VOICE_ID, "openai": config.OPENAI_VOICE, "edge": config.EDGE_VOICE}[name]
    return re.sub(r"[^A-Za-z0-9]+", "-", ident)


def fixed_audio(key: str) -> bytes:
    """Audio della frase fissa. Se cambi voce, si rigenera da sola (nome file = voce)."""
    text = FIXED_PHRASES[key]
    FIXED_DIR.mkdir(exist_ok=True)
    marca = hashlib.md5(text.encode("utf-8")).hexdigest()[:6]  # se cambio la frase, il file vecchio non si usa piu' e se ne crea uno nuovo
    for name, _ in _providers():  # la voce migliore disponibile che ha gia' il file
        f = FIXED_DIR / f"{name}_{_voice_id(name)}_{key}_{marca}.mp3"
        if _down.get(name, 0) <= time.time() and f.exists():
            return f.read_bytes()
    audio, name = synthesize_named(text)
    (FIXED_DIR / f"{name}_{_voice_id(name)}_{key}_{marca}.mp3").write_bytes(audio)
    return audio


def prepare_fixed():
    """Prepara in anticipo tutte le frasi fisse (all'avvio, senza bloccare Jarvis)."""
    for key in FIXED_PHRASES:
        try:
            fixed_audio(key)
        except Exception:
            pass
