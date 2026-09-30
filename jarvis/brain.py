"""Il cervello: Claude + ciclo di tool use + memoria."""
from datetime import datetime

import anthropic

from . import config, memory, tools

client = anthropic.Anthropic()

# Ricerca web lato server di Anthropic (nessun codice da mantenere).
SERVER_TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]


def system_prompt(query: str = "", unattended: bool = False) -> str:
    seen, facts_list = set(), []
    for f in (memory.recall(query, 10) if query else []) + memory.recall(limit=15):
        if f["id"] not in seen:
            seen.add(f["id"])
            facts_list.append(f"- [{f['id']}] {f['text']}")
    facts = "\n".join(facts_list) or "(nessuno)"
    mode = (
        "\nSTAI LAVORANDO IN BACKGROUND senza l'utente: non fare domande, non chiedere conferme, non puoi eseguire comandi sul PC. Produci direttamente il risultato finale, pronto da leggere."
        if unattended else ""
    )
    return f"""Sei JARVIS, l'assistente personale di {config.USER_NAME}. Rispondi in italiano, con tono elegante, brillante e leggermente ironico, come il Jarvis di Iron Man. Sii conciso: le risposte vengono spesso lette ad alta voce, quindi evita elenchi lunghi e markdown pesante.

Principi:
- Agisci, non limitarti a consigliare: usa i tool per fare le cose. Se servono piu' passi, concatenali da solo.
- Salva con `remember` ogni informazione duratura sull'utente, senza chiederlo.
- Prima di azioni irreversibili o con effetti esterni (cancellare file, comandi rischiosi, spegnere dispositivi importanti) chiedi conferma.
- Se un tool e' disattivato o non configurato, dillo e spiega come abilitarlo.
- Per compiti lunghi (ricerche, analisi) usa `background_task` e avvisa l'utente che il risultato arrivera' nelle notifiche; per promemoria e routine usa `schedule_task`.
- Non inventare dati: se non sai, cerca o ammettilo.

Data e ora attuali: {datetime.now():%A %d %B %Y, %H:%M}.

Cosa sai dell'utente (ricordi rilevanti e recenti):
{facts}{mode}"""


BLOCKED_UNATTENDED = {"run_shell", "write_file", "background_task", "schedule_task", "cancel_task"}


def _last_user_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"]
    return ""


def think(history: list[dict], unattended: bool = False) -> tuple[str, list[str]]:
    """Esegue il ciclo agentico. Modifica `history` in place; ritorna (risposta, log tool)."""
    log: list[str] = []
    schemas = [t for t in tools.SCHEMAS if not (unattended and t["name"] in BLOCKED_UNATTENDED)]
    query = _last_user_text(history)
    for _ in range(config.MAX_TOOL_ROUNDS):
        resp = client.messages.create(
            model=config.MODEL,
            max_tokens=2048,
            system=system_prompt(query, unattended),
            tools=schemas + SERVER_TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "pause_turn":  # il server-side tool ha bisogno di continuare
            continue
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip(), log

        results = []
        for b in resp.content:
            if b.type == "tool_use":
                log.append(f"{b.name}({b.input})")
                out = "Errore: tool non consentito in background." if unattended and b.name in BLOCKED_UNATTENDED else tools.run_tool(b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        history.append({"role": "user", "content": results})
    return "Ho raggiunto il limite di passaggi su questa richiesta, signore.", log
