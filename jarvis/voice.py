"""Voce naturale: TTS (ElevenLabs / OpenAI) e STT (Whisper)."""
import httpx
from . import config


def tts_available() -> bool:
    return bool(config.ELEVENLABS_API_KEY or config.OPENAI_API_KEY)


def stt_available() -> bool:
    return bool(config.OPENAI_API_KEY)


def synthesize(text: str) -> bytes:
    text = text[:2500]
    if config.ELEVENLABS_API_KEY:
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
            headers={"xi-api-key": config.ELEVENLABS_API_KEY},
            json={"text": text, "model_id": "eleven_multilingual_v2"},
            timeout=60,
        )
    else:
        r = httpx.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            json={"model": "gpt-4o-mini-tts", "voice": "onyx", "input": text,
                  "instructions": "Parla in italiano con tono calmo, elegante e sicuro, come un maggiordomo hi-tech."},
            timeout=60,
        )
    r.raise_for_status()
    return r.content


def transcribe(audio: bytes, content_type: str) -> str:
    ext = "mp4" if "mp4" in content_type else "ogg" if "ogg" in content_type else "webm"
    r = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        files={"file": (f"audio.{ext}", audio, content_type)},
        data={"model": "whisper-1", "language": "it"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["text"].strip()
