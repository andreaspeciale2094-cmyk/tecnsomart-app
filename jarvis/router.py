"""Router: le richieste semplici vanno a Groq (economico e veloce), le difficili a Claude.
Regole locali e gratuite decidono prima; Groq stesso si tira indietro ("@@CLAUDE@@") se non e' sicuro.
Qualunque errore di Groq -> si passa a Claude, senza che l'utente se ne accorga."""
import re

import httpx

from . import brain_prompts, config, logs

ESCAPE = "@@CLAUDE@@"

# Se compare una di queste parole serve Claude (strumenti, memoria, ricerche, ragionamento, testi lunghi).
_HARD = re.compile(
    r"\b(ricord\w*|dimentic\w*|memoria|cerca\w*|ricerc\w*|notizi\w*|meteo|che tempo|prezz\w*|costa|costano|treno|treni|amazon|"
    r"riassum\w*|riassunt\w*|scriv\w*|spieg\w*|perch[eé]|confront\w*|analizz\w*|consigli\w*|codice|programm\w*|"
    r"chiud\w*|apri\w*|avvia\w*|lancia\w*|volume|muto|blocca\w*|standby|spegni\w*|riavvia\w*|pulisci|pulizia|mail|e-mail|email|posta|bozza|rispond\w*|calendari\w*|whatsapp|telegram|file|cartella|crea\w*|genera\w*|calcol\w*|piano|strategia|"
    r"negozi\w*|addett\w*|banc\w*|conto|conti|saldo|movimenti|abbonament\w*|cassa|contant\w*|prelev\w*|spes[aeio]\b|ragazz\w*|focus|report|giornalier\w*|target|colloqui\w*|impegn\w*|agenda|appuntament\w*|riunion\w*|briefing|chi (?:è|e'|ha)|quando (?:è|e'|ha)|oggi su|ultim[ei])\b",
    re.IGNORECASE,
)


def is_simple(text: str, history: list[dict]) -> bool:
    t = text.strip()
    if config.ENABLE_AGENDA and re.search(r"\bbuon\s?g\w*|\bbuond\w*", t, re.IGNORECASE):
        return False  # con l'agenda attiva, il buongiorno e' il briefing: serve Claude con gli strumenti
    if not t or len(t) > 140 or len(t.split()) > 22:
        return False
    if _HARD.search(t):
        return False
    if re.search(r"\d", t) and re.search(r"\b(per|pi[uù]|meno|diviso|fa|radice|percento)\b|[+*/×÷=]", t):
        return False  # conti: meglio Claude
    # se negli ultimi scambi Claude ha usato strumenti, resta con Claude per coerenza
    for m in history[-6:]:
        if isinstance(m.get("content"), list):
            for b in m["content"]:
                if getattr(b, "type", None) in ("tool_use", "server_tool_use") or (isinstance(b, dict) and b.get("type") == "tool_result"):
                    return False
    return True


def _text_history(history: list[dict], limit: int = 6) -> list[dict]:
    """Ultimi scambi come solo testo (Groq non vede strumenti ne' blocchi di pensiero)."""
    out = []
    for m in history:
        c = m["content"]
        if isinstance(c, str):
            out.append({"role": m["role"], "content": c})
        elif m["role"] == "assistant":
            txt = "".join(getattr(b, "text", "") for b in c if getattr(b, "type", None) == "text").strip()
            if txt:
                out.append({"role": "assistant", "content": txt})
    return out[-limit:]


def groq_text(system: str, user: str, max_tokens: int = 900, timeout: int = 25) -> str:
    """Una richiesta semplice a Groq (usata per i riassunti). Alza un errore se non risponde."""
    payload = {"model": config.GROQ_MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
               "max_tokens": max_tokens, "temperature": 0.2}
    if "gpt-oss" in config.GROQ_MODEL:
        payload["reasoning_effort"] = "low"
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"}, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    usage = data.get("usage", {})
    logs.log_groq(config.GROQ_MODEL, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return (data["choices"][0]["message"].get("content") or "").strip()


def ask_groq(history: list[dict], query: str, summary: str = "") -> str | None:
    """Ritorna la risposta di Groq, oppure None se serve Claude."""
    system = (
        brain_prompts.STATIC_PROMPT
        + "\n\n"
        + brain_prompts.viva_prompt()
        + "\n\n"
        + brain_prompts.context_prompt(query, summary=summary)
        + f"\n\nRispondi solo se la risposta e' semplice e certa. Se serve cercare online, usare la memoria personale, fare calcoli o ragionamenti, "
        f"o non sei sicuro, rispondi ESATTAMENTE con {ESCAPE} e nient'altro."
    )
    payload = {"model": config.GROQ_MODEL, "messages": [{"role": "system", "content": system}] + _text_history(history),
               "max_tokens": 300, "temperature": 0.4}
    if "gpt-oss" in config.GROQ_MODEL:
        # modello che "ragiona": poco ragionamento, cosi' resta veloce e i token bastano per la risposta
        payload["reasoning_effort"] = "low"
        payload["max_tokens"] = 800
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json=payload,
        timeout=8,
    )
    r.raise_for_status()
    data = r.json()
    usage = data.get("usage", {})
    logs.log_groq(config.GROQ_MODEL, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    reply = (data["choices"][0]["message"].get("content") or "").strip()
    if not reply or ESCAPE in reply:
        return None
    return reply


def route(history: list[dict], query: str, summary: str = "") -> str | None:
    """Prova Groq per le richieste semplici. None = risponde Claude."""
    if not config.ENABLE_ROUTER or not is_simple(query, history[:-1]):
        return None
    try:
        reply = ask_groq(history, query, summary)
    except httpx.HTTPStatusError as e:  # Groq risponde ma rifiuta: scriviamo il perche' (senza chiavi)
        logs.log_route(f"Groq ha risposto errore {e.response.status_code}: {logs.clean(e.response.text)}. Passo a Claude")
        return None
    except Exception as e:  # Groq giu', niente rete...: si va su Claude
        logs.log_route(f"Groq non disponibile ({type(e).__name__}: {logs.clean(str(e))}), passo a Claude")
        return None
    logs.log_route("risposto da Groq" if reply else "Groq non e' sicuro, passo a Claude")
    return reply
