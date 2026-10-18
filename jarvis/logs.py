"""Registri semplici in logs/: errori (senza chiavi ne' messaggi privati) e consumi."""
import re
from datetime import datetime
from pathlib import Path

import anthropic
import httpx

from . import config

LOG_DIR = Path("logs")


def _write(name: str, line: str):
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_DIR / name, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {line}\n")
    except OSError:
        pass  # il registro non deve mai far fallire Jarvis


def clean(text: str) -> str:
    text = re.sub(r"\b(sk|gsk|xai|key)[-_][A-Za-z0-9_\-]{8,}", "[chiave]", text)  # mai chiavi nel registro
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
    _write("errori.log", f"{cause} | {type(e).__name__} | {clean(str(e))}")


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
    # cache: lettura = 10% del prezzo normale, scrittura = 125%
    cost = (fresh * config.PRICE_CLAUDE_IN + created * config.PRICE_CLAUDE_IN * 1.25
            + cached * config.PRICE_CLAUDE_IN * 0.1 + out * config.PRICE_CLAUDE_OUT) / 1e6
    saved = f"{round(100 * cached / total_in)}% dell'ingresso letto dalla cache" if total_in and cached else "cache non usata"
    _write("consumi.log", f"CLAUDE {model} | ingresso nuovo {fresh} | scritto in cache {created} | letto da cache {cached} | uscita {out} | {saved} | costo stimato ${cost:.5f}")


def log_groq(model: str, tokens_in: int, tokens_out: int):
    cost = (tokens_in * config.PRICE_GROQ_IN + tokens_out * config.PRICE_GROQ_OUT) / 1e6
    _write("consumi.log", f"GROQ {model} | ingresso {tokens_in} | uscita {tokens_out} | costo stimato ${cost:.5f}")


def log_route(note: str):
    _write("consumi.log", f"ROUTER | {note}")


def log_latency(first_text_s: float | None, total_s: float):
    first = f"{first_text_s:.2f}s" if first_text_s is not None else "nessun testo"
    _write("consumi.log", f"TEMPI | primo testo dopo {first} | risposta completa dopo {total_s:.2f}s")


def log_voice(provider: str, e: Exception):
    status = f" (errore {e.response.status_code})" if isinstance(getattr(e, "response", None), httpx.Response) else ""
    _write("errori.log", f"voce | {provider} non disponibile{status}: {clean(str(e))} | passo alla voce successiva")


def log_page(tag: str, detail: str):
    _write("consumi.log", f"PAGINA | {tag} | {clean(detail)[:80]}")


def log_memory(note: str):
    """Registro delle azioni sulla memoria: solo numeri e conteggi, mai il contenuto dei ricordi."""
    _write("consumi.log", f"MEMORIA | {clean(note)[:100]}")
