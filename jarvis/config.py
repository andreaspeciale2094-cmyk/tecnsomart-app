import os
from pathlib import Path
from dotenv import load_dotenv

# Legge SEMPRE il .env della cartella principale del progetto (mai uno finito per sbaglio dentro jarvis/).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = os.getenv("JARVIS_MODEL", "claude-sonnet-5-5")
USER_NAME = os.getenv("JARVIS_USER_NAME", "signore")
METEO_CITTA = os.getenv("METEO_CITTA", "").strip()  # per il meteo accanto all'ora (solo il nome della citta')


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
ENABLE_BANCA = _flag("JARVIS_BANCA")  # conto personale in SOLA LETTURA (Enable Banking)
BANCA_APP_ID = os.getenv("ENABLE_BANKING_APP_ID", "")
BANCA_CHIAVE = os.getenv("ENABLE_BANKING_KEY", "")  # percorso del file .pem (predefinito: memoria/banca/chiave.pem)
BANCA_RITORNO = os.getenv("ENABLE_BANKING_RITORNO", "https://localhost:8000/banca/ritorno")
BANCA_PRESENTE = _flag("ENABLE_BANKING_PRESENTE", True)  # avvisa la banca che Andrea e' presente (meno limiti)
TELEFONO_URL = os.getenv("TELEFONO_URL", "").strip()  # indirizzo dell'app sul telefono che fa partire la chiamata (rete privata Tailscale), es. http://100.x.x.x:8080/chiama
TELEFONO_CHIAVE = os.getenv("TELEFONO_CHIAVE", "").strip()  # parola segreta che il telefono controlla
ENABLE_PROMEMORIA = _flag("JARVIS_PROMEMORIA", True)  # "ricordami alle 17 di..." (spegnere con false)
ENABLE_SALUTE = _flag("JARVIS_SALUTE", True)  # controlla da solo che le parti di Jarvis funzionino, ripara le cose sicure e avvisa del resto (+ guardiano dei consumi)
TETTO_MENSILE = os.getenv("TETTO_MENSILE", "25")  # dollari: soglia del guardiano dei consumi (il tetto vero lo imposta Andrea nella Console Anthropic)
ENABLE_BACKUP = _flag("JARVIS_BACKUP", True)  # copia di sicurezza settimanale di schede, rubrica a mano, promemoria, target (solo sul PC)
ENABLE_TRENI = _flag("JARVIS_TRENI", True)  # "com'e' il mio treno?" (fonte non ufficiale, spegnere con false)
ENABLE_CHIAMATE = _flag("JARVIS_CHIAMATE", True)  # telefonate dal PC con il si' di Andrea (spegnere con false)
ENABLE_WHATSAPP = _flag("JARVIS_WHATSAPP")  # prepara messaggi WhatsApp e apre l'app con il testo pronto (invia Andrea)
WHATSAPP_PRECARICA = _flag("JARVIS_WHATSAPP_PRECARICA", True)  # accende l'app WhatsApp del PC all'avvio (ridotta) cosi' al clic si apre subito; false per non farlo
ENABLE_WHATSAPP_INVIO = _flag("JARVIS_WHATSAPP_INVIO")  # invio senza finestre (eccezione regola 5); richiede JARVIS_WHATSAPP
ENABLE_PULIZIA = _flag("JARVIS_PULIZIA", True)  # pulizia di fine giornata a mezzanotte e alla chiusura (spegnere con false)
ENABLE_TELEGRAM = _flag("JARVIS_TELEGRAM")  # parlare con Jarvis dal telefono con Telegram (solo l'account di Andrea)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")  # dal bot creato con @BotFather: solo in .env
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID", "")
ENABLE_ASCOLTO = _flag("JARVIS_ASCOLTO")  # ascolto in stanza: risponde solo se chiamato ("Hey Jarvis")
ASCOLTO_SOGLIA = float(os.getenv("ASCOLTO_SOGLIA", "0.5"))  # piu' bassa = si sveglia piu' facilmente (anche per errore)
ASCOLTO_PAUSA_FINE = int(os.getenv("ASCOLTO_PAUSA_FINE", "9"))  # blocchi da 80 ms di silenzio che chiudono la frase (9 = 0,7 s; piu' basso = piu' veloce ma puo' tagliarti)
ASCOLTO_INTERRUZIONE = os.getenv("ASCOLTO_INTERRUZIONE", "auto")  # "Hey Jarvis" mentre parla lo ferma: auto = acceso (con le cuffie anche parlando sopra), true/false per forzare
ASCOLTO_FINESTRA = int(os.getenv("ASCOLTO_FINESTRA", "45"))  # secondi di conversazione aperta dopo una risposta, senza ripetere "Hey Jarvis"
RITMO_RITARDO = float(os.getenv("RITMO_RITARDO", "0.15"))  # secondi di ritardo tra l'audio che parte e quello che si sente (cuffie bluetooth: 0.2-0.3)
ASCOLTO_ATTESA = float(os.getenv("ASCOLTO_ATTESA", "2.5"))  # secondi di attesa prima di dire "Un attimo / Ci penso io / Subito" (piu' bassa = lo dice piu' spesso)
ASCOLTO_DISPOSITIVO = os.getenv("ASCOLTO_DISPOSITIVO", "")  # numero o nome del microfono (vuoto = quello predefinito)
ENABLE_WHATSAPP_LEGGI = _flag("JARVIS_WHATSAPP_LEGGI")  # legge i messaggi in arrivo (chat singole, solo in memoria); richiede JARVIS_WHATSAPP_INVIO
ENABLE_BENVENUTO = _flag("JARVIS_BENVENUTO", True)  # saluto quando torni al PC (Buongiorno la prima volta del giorno, poi Bentornato)
BENVENUTO_ASSENZA = int(os.getenv("BENVENUTO_ASSENZA", "0"))  # 0 = spento (predefinito): saluta solo all'accensione e dopo lo standby; se > 0, saluta anche dopo tanti secondi di PC fermo
ENABLE_PC_COMANDI = _flag("JARVIS_PC")  # apri app e giochi, volume, blocco; spegni/riavvia/chiudi solo dopo il si'
ENABLE_AGENDA = _flag("JARVIS_AGENDA")  # briefing del mattino e impegni dai calendari Google (sola lettura)
CALENDARIO_PERSONALE_ICS = os.getenv("CALENDARIO_PERSONALE_ICS", "")  # indirizzo segreto iCal: solo in .env
CALENDARIO_LAVORO_ICS = os.getenv("CALENDARIO_LAVORO_ICS", "")
FUSO = os.getenv("JARVIS_FUSO", "Europe/Rome")
TECNOSMART_TOKEN = os.getenv("TECNOSMART_TOKEN", "")  # chiave segreta dell'indirizzo di sola lettura dell'app
WORKDIR = Path(os.getenv("JARVIS_WORKDIR", "./workspace")).resolve()
DB_PATH = os.getenv("JARVIS_DB", "jarvis.db")
MAX_TOOL_ROUNDS = 12
ENABLE_VIGILE = _flag("JARVIS_VIGILE", True)  # agente vigile in sottofondo: ti avvisa solo se c'e' qualcosa che conta (impegno imminente, mail o messaggi importanti)
BANCA_SOGLIA = float(os.getenv("BANCA_SOGLIA", "50"))  # il vigile segnala solo movimenti da questa cifra in su (euro); il saldo solo a richiesta
VIGILE_BANCA = _flag("JARVIS_VIGILE_BANCA", True)  # il vigile controlla il conto 4 volte al giorno e avvisa di entrate e uscite nuove (solo se la banca e' collegata)
VIGILE_BANCA_ORARI = [x.strip() for x in os.getenv("VIGILE_BANCA_ORARI", "09:00,13:00,17:00,21:00").split(",") if x.strip()]
ENABLE_AGENTI = _flag("JARVIS_AGENTI", True)  # agenti specializzati che lavorano insieme per le richieste ampie (quadro di oggi, briefing...)
AGENTI_MODEL = os.getenv("JARVIS_AGENTI_MODEL", "claude-haiku-5-5")  # modello piu' leggero per gli agenti: costano meno del cervello
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
IMAP_LAVORO_USER = os.getenv("IMAP_LAVORO_USER", "")  # seconda casella Gmail (lavoro): password per le app, solo in .env
IMAP_LAVORO_PASSWORD = os.getenv("IMAP_LAVORO_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
ENABLE_POSTA = _flag("JARVIS_POSTA")  # leggere, preparare bozze e inviare email (solo dopo il si' di Andrea)
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
GROQ_STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")  # riconoscimento vocale su Groq
ENABLE_ROUTER = bool(GROQ_API_KEY) and _flag("JARVIS_ROUTER", True)

# Quanto "pensa" Claude: low (veloce ed economico, consigliato), medium, high.
EFFORT = os.getenv("JARVIS_EFFORT", "auto")  # "auto" = basso per le cose semplici, medio quando c'e' da ragionare (o low/medium/high fisso)

# Prezzi in dollari per milione di token, usati SOLO per il costo stimato nel registro consumi.
# Claude Sonnet 5.5 (listino Anthropic). Groq: controlla il listino sul loro sito e correggi se serve.
PRICE_CLAUDE_IN = float(os.getenv("PRICE_CLAUDE_IN", "2.00"))
PRICE_CLAUDE_OUT = float(os.getenv("PRICE_CLAUDE_OUT", "10.00"))
PRICE_GROQ_IN = float(os.getenv("PRICE_GROQ_IN", "0.59"))
PRICE_GROQ_OUT = float(os.getenv("PRICE_GROQ_OUT", "0.79"))

# Quale voce usare: auto (la migliore disponibile, con ripiego sulla gratuita), edge (SOLO gratuita: nessuna spesa),
# elevenlabs oppure openai. In ogni caso, se una voce a pagamento fallisce si passa alla gratuita.
VOICE_MODE = os.getenv("JARVIS_VOICE", "auto").strip().lower()
