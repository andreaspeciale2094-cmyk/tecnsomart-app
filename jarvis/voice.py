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


def clean_for_speech(text: str) -> str:
    """Toglie tutto cio' che una voce legge male: markdown, link, emoji, simboli."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)  # [testo](url) -> testo
    t = re.sub(r"https?://\S+", " link ", t)
    t = _EMOJI.sub(" ", t)
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
    return bool(config.OPENAI_API_KEY)


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
    ext = "mp4" if "mp4" in content_type else "ogg" if "ogg" in content_type else "wav" if "wav" in content_type else "webm"
    r = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        files={"file": (f"audio.{ext}", audio, content_type)},
        data={"model": "whisper-1", "language": "it"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["text"].strip()


# ---- Frasi fisse: create una volta, salvate su disco, riprodotte subito mentre Jarvis pensa ----
FIXED_DIR = Path(__file__).parent.parent / "audio_fisse"
FIXED_PHRASES = {
    "attesa1": "Un attimo, signore.",
    "attesa2": "Ci penso io.",
    "attesa3": "Subito.",
    "attesa4": "Vediamo.",
    # dette se un lavoro dura piu' di 3 secondi (mai silenzio)
    "stato_cerca": "Sto cercando online, signore.",
    "stato_pagina": "Sto leggendo la pagina.",
    "stato_memoria": "Controllo la memoria.",
    "stato_ancora": "Ci sto ancora lavorando, signore.",
}


def _voice_id(name: str) -> str:
    ident = {"elevenlabs": config.ELEVENLABS_VOICE_ID, "openai": config.OPENAI_VOICE, "edge": config.EDGE_VOICE}[name]
    return re.sub(r"[^A-Za-z0-9]+", "-", ident)


def fixed_audio(key: str) -> bytes:
    """Audio della frase fissa. Se cambi voce, si rigenera da sola (nome file = voce)."""
    text = FIXED_PHRASES[key]
    FIXED_DIR.mkdir(exist_ok=True)
    for name, _ in _providers():  # la voce migliore disponibile che ha gia' il file
        f = FIXED_DIR / f"{name}_{_voice_id(name)}_{key}.mp3"
        if _down.get(name, 0) <= time.time() and f.exists():
            return f.read_bytes()
    audio, name = synthesize_named(text)
    (FIXED_DIR / f"{name}_{_voice_id(name)}_{key}.mp3").write_bytes(audio)
    return audio


def prepare_fixed():
    """Prepara in anticipo tutte le frasi fisse (all'avvio, senza bloccare Jarvis)."""
    for key in FIXED_PHRASES:
        try:
            fixed_audio(key)
        except Exception:
            pass
