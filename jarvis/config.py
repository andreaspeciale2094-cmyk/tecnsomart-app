import os
from pathlib import Path
from dotenv import load_dotenv

# Legge SEMPRE il .env della cartella principale del progetto (mai uno finito per sbaglio dentro jarvis/).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
ENABLE_NEGOZI = _flag("JARVIS_NEGOZI")  # riepilogo dei negozi TecnoSmart (RUN giornaliero)
ENABLE_ADDETTI = _flag("JARVIS_ADDETTI")  # focus per addetto e schede dei ragazzi (usa la stessa chiave dei negozi)
ENABLE_CASSA = _flag("JARVIS_CASSA")  # cassa dei contanti (prelievi e spese a voce, solo registro)
ENABLE_AGENDA = _flag("JARVIS_AGENDA")  # briefing del mattino e impegni dai calendari Google (sola lettura)
CALENDARIO_PERSONALE_ICS = os.getenv("CALENDARIO_PERSONALE_ICS", "")  # indirizzo segreto iCal: solo in .env
CALENDARIO_LAVORO_ICS = os.getenv("CALENDARIO_LAVORO_ICS", "")
FUSO = os.getenv("JARVIS_FUSO", "Europe/Rome")
TECNOSMART_TOKEN = os.getenv("TECNOSMART_TOKEN", "")  # chiave segreta dell'indirizzo di sola lettura dell'app
WORKDIR = Path(os.getenv("JARVIS_WORKDIR", "./workspace")).resolve()
DB_PATH = os.getenv("JARVIS_DB", "jarvis.db")
MAX_TOOL_ROUNDS = 12
MAX_HISTORY = 40
# Memoria della conversazione: ultimi 10 messaggi interi; quando i vecchi superano 20, vengono riassunti.
KEEP_RECENT = 10
COMPACT_WHEN_OLDER = 20
HARD_MAX_MESSAGES = 80  # rete di sicurezza se il riassunto non riesce

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

# Router: domande semplici a Groq (economico), il resto a Claude. Attivo solo se c'e' GROQ_API_KEY.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
ENABLE_ROUTER = bool(GROQ_API_KEY) and _flag("JARVIS_ROUTER", True)

# Quanto "pensa" Claude: low (veloce ed economico, consigliato), medium, high.
EFFORT = os.getenv("JARVIS_EFFORT", "low")

# Prezzi in dollari per milione di token, usati SOLO per il costo stimato nel registro consumi.
# Claude Sonnet 5.5 (listino Anthropic). Groq: controlla il listino sul loro sito e correggi se serve.
PRICE_CLAUDE_IN = float(os.getenv("PRICE_CLAUDE_IN", "2.00"))
PRICE_CLAUDE_OUT = float(os.getenv("PRICE_CLAUDE_OUT", "10.00"))
PRICE_GROQ_IN = float(os.getenv("PRICE_GROQ_IN", "0.59"))
PRICE_GROQ_OUT = float(os.getenv("PRICE_GROQ_OUT", "0.79"))

# Quale voce usare: auto (la migliore disponibile, con ripiego sulla gratuita), edge (SOLO gratuita: nessuna spesa),
# elevenlabs oppure openai. In ogni caso, se una voce a pagamento fallisce si passa alla gratuita.
VOICE_MODE = os.getenv("JARVIS_VOICE", "auto").strip().lower()
