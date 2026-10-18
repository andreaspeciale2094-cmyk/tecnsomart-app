"""Riassunto dei messaggi vecchi: fatti, decisioni, cose da fare. Le informazioni permanenti vanno nell'archivio dei ricordi."""
import json
import re

from . import config, logs, router

SYSTEM = """Sei l'archivista di Jarvis, il maggiordomo di {nome}. Ricevi una parte vecchia di una conversazione.
Rispondi SOLO con un oggetto JSON con due campi:
- "riassunto": al massimo 10 righe brevi, una per riga, con i fatti, le decisioni e le cose da fare. Niente saluti, niente chiacchiere. Includi il vecchio riassunto, se c'e'.
- "fatti_permanenti": elenco (anche vuoto, massimo 8) di informazioni DURATURE su {nome} (preferenze, persone, abitudini, impegni ricorrenti), ognuna in una frase breve e completa. Non metterci cose passeggere.
Non scrivere mai password, chiavi, numeri di carte o conti, ne' dati personali dei clienti dei negozi."""

_SECRET = re.compile(r"password|passwd|\biban\b|\b\d{12,19}\b|\bsk-|gsk_|\bpin\b", re.IGNORECASE)


def _ask_claude(system: str, user: str) -> str:
    from . import brain  # import tardivo: brain -> router -> ...

    resp = brain.client.messages.create(
        model=config.MODEL, max_tokens=1200, output_config={"effort": "low"}, system=system,
        messages=[{"role": "user", "content": user}],
    )
    logs.log_usage(config.MODEL, resp.usage)
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _ask(system: str, user: str) -> str:
    if config.ENABLE_ROUTER:  # Groq costa pochissimo; se non risponde, Claude
        try:
            return router.groq_text(system, user)
        except Exception as e:
            logs.log_route(f"Riassunto: Groq non disponibile ({type(e).__name__}), uso Claude")
    return _ask_claude(system, user)


def parse(raw: str) -> tuple[str, list[str]]:
    """Legge la risposta; se non e' un JSON valido usa il testo come riassunto (max 10 righe), senza fatti."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(m.group(0)) if m else {}
        summary, facts = data.get("riassunto", ""), data.get("fatti_permanenti", [])
        if isinstance(summary, list):
            summary = "\n".join(map(str, summary))
        if not isinstance(facts, list):
            facts = []
    except (ValueError, AttributeError):
        summary, facts = "", []
    if not str(summary).strip():
        summary = re.sub(r"[{}\"]", "", raw)
    lines = [l.strip(" -*•\t") for l in str(summary).splitlines() if l.strip(" -*•\t")][:10]
    clean = [" ".join(str(f).split()) for f in facts]
    clean = [f for f in clean if 3 < len(f) <= 200 and not _SECRET.search(f)][:8]
    return "\n".join(f"- {l}" for l in lines), clean


def compact(old: list[dict], previous: str = "") -> tuple[str, list[str]]:
    """old: messaggi di solo testo [{role, content}]. Ritorna (riassunto, fatti permanenti)."""
    dialogo = "\n".join(f"{'Utente' if m['role'] == 'user' else 'Jarvis'}: {m['content']}" for m in old)
    user = (f"Vecchio riassunto:\n{previous}\n\n" if previous else "") + f"Conversazione da riassumere:\n{dialogo[:12000]}"
    return parse(_ask(SYSTEM.format(nome=config.USER_NAME), user))
