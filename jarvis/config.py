import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("JARVIS_MODEL", "claude-sonnet-5-5")
USER_NAME = os.getenv("JARVIS_USER_NAME", "signore")


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "si", "yes")


PC_CONTROL = _flag("JARVIS_PC_CONTROL")
# Funzioni extra: spente di default, cosi' non costano nulla e non pesano su ogni messaggio.
ENABLE_WEB_SEARCH = _flag("JARVIS_WEB_SEARCH", True)
ENABLE_AGENTS = _flag("JARVIS_AGENTS")  # attivita' pianificate, briefing e agenti in background
ENABLE_MAIL = _flag("JARVIS_MAIL")  # mail e calendario in lettura
ENABLE_HOME = _flag("JARVIS_HOME")  # domotica Home Assistant
WORKDIR = Path(os.getenv("JARVIS_WORKDIR", "./workspace")).resolve()
DB_PATH = os.getenv("JARVIS_DB", "jarvis.db")
MAX_TOOL_ROUNDS = 12
MAX_HISTORY = 40

HA_URL = os.getenv("HA_URL", "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN", "")
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
CALENDAR_ICS_URL = os.getenv("CALENDAR_ICS_URL", "")

# Sicurezza
PASSWORD = os.getenv("JARVIS_PASSWORD", "")

# Voce (opzionale, migliora la qualita'). ElevenLabs ha la precedenza su OpenAI per il TTS.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
OPENAI_VOICE = os.getenv("OPENAI_VOICE", "onyx")  # onyx, echo, ash, fable, alloy...
VOICE_STYLE = os.getenv("VOICE_STYLE", "Parla in italiano con tono calmo, elegante, sicuro e leggermente ironico, come un maggiordomo hi-tech britannico. Ritmo misurato, dizione impeccabile.")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # TTS, Whisper (STT) ed embeddings

# Proattivita'
BRIEFING_TIME = os.getenv("BRIEFING_TIME", "")  # es. 07:30 (ora locale del server)

# Voce gratuita (Edge TTS, nessuna chiave). Voci italiane: it-IT-DiegoNeural (maschile), it-IT-GiuseppeMultilingualNeural, it-IT-ElsaNeural (femminile)
EDGE_VOICE = os.getenv("EDGE_VOICE", "it-IT-GiuseppeMultilingualNeural")
EDGE_RATE = os.getenv("EDGE_RATE", "-3%")
EDGE_PITCH = os.getenv("EDGE_PITCH", "+0Hz")
