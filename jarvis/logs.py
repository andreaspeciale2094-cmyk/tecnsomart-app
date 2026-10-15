"""Registri semplici in logs/: errori (senza chiavi ne' messaggi privati) e consumi."""
import re
from datetime import datetime
from pathlib import Path

import anthropic

LOG_DIR = Path("logs")


def _write(name: str, line: str):
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_DIR / name, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {line}\n")
    except OSError:
        pass  # il registro non deve mai far fallire Jarvis


def _clean(text: str) -> str:
    text = re.sub(r"(sk|gsk|xai)-[A-Za-z0-9_\-]{8,}", "[chiave]", text)  # mai chiavi nel registro
    return re.sub(r"\s+", " ", text)[:300]


def explain(e: Exception) -> tuple[str, str]:
    """Ritorna (messaggio in italiano per Andrea, causa breve)."""
    text = str(e).lower()
    if isinstance(e, anthropic.APIStatusError) and ("credit balance" in text or "billing" in text):
        return ("Il credito di Claude e' finito. Caricalo su console.anthropic.com, nella sezione Billing, e poi riprova.", "credito finito")
    if isinstance(e, anthropic.AuthenticationError) or (isinstance(e, TypeError) and "authentication" in text):
        return ("La chiave di Claude manca o non e' valida. Controlla la riga ANTHROPIC_API_KEY nel file .env.", "chiave non valida")
    if isinstance(e, anthropic.APIConnectionError):
        return ("Non riesco a collegarmi a internet. Controlla la connessione e riprova.", "niente internet")
    if isinstance(e, anthropic.RateLimitError):
        return ("Ci sono troppe richieste in poco tempo. Aspetta un minuto e riprova.", "troppe richieste")
    if isinstance(e, anthropic.PermissionDeniedError):
        return ("Il tuo account Claude non ha il permesso per questa richiesta. Controlla le impostazioni su console.anthropic.com.", "permesso negato")
    if isinstance(e, anthropic.NotFoundError):
        return ("Il modello scelto non esiste per il tuo account. Controlla la riga JARVIS_MODEL nel file .env.", "modello non trovato")
    if isinstance(e, anthropic.APIStatusError) and e.status_code >= 500:
        return ("Il servizio di Claude e' occupato in questo momento. Riprova tra poco.", "servizio occupato")
    return ("Si e' verificato un problema inatteso. Ho scritto i dettagli nel registro degli errori.", "errore inatteso")


def log_error(e: Exception, cause: str):
    _write("errori.log", f"{cause} | {type(e).__name__} | {_clean(str(e))}")


def handle(e: Exception) -> str:
    message, cause = explain(e)
    log_error(e, cause)
    return message


def log_usage(model: str, usage):
    if usage is None:
        return
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    created = getattr(usage, "cache_creation_input_tokens", 0) or 0
    fresh = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    total_in = fresh + cached + created
    saved = f"{round(100 * cached / total_in)}% dell'ingresso letto dalla cache (costa molto meno)" if total_in and cached else "cache non usata"
    _write("consumi.log", f"{model} | ingresso nuovo {fresh} | scritto in cache {created} | letto da cache {cached} | uscita {out} | {saved}")
