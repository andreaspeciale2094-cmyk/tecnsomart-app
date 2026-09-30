"""Il cervello: Claude + ciclo di tool use + memoria."""
from datetime import datetime

import anthropic

from . import config, memory, tools

client = anthropic.Anthropic()

# Ricerca web lato server di Anthropic (nessun codice da mantenere).
SERVER_TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]


def system_prompt() -> str:
    facts = "\n".join(f"- [{f['id']}] {f['text']}" for f in memory.recall(limit=40)) or "(nessuno)"
    return f"""Sei JARVIS, l'assistente personale di {config.USER_NAME}. Rispondi in italiano, con tono elegante, brillante e leggermente ironico, come il Jarvis di Iron Man. Sii conciso: le risposte vengono spesso lette ad alta voce, quindi evita elenchi lunghi e markdown pesante.

Principi:
- Agisci, non limitarti a consigliare: usa i tool per fare le cose. Se servono piu' passi, concatenali da solo.
- Salva con `remember` ogni informazione duratura sull'utente, senza chiederlo.
- Prima di azioni irreversibili o con effetti esterni (cancellare file, comandi rischiosi, spegnere dispositivi importanti) chiedi conferma.
- Se un tool e' disattivato o non configurato, dillo e spiega come abilitarlo.
- Non inventare dati: se non sai, cerca o ammettilo.

Data e ora attuali: {datetime.now():%A %d %B %Y, %H:%M}.

Cosa sai dell'utente:
{facts}"""


def think(history: list[dict]) -> tuple[str, list[str]]:
    """Esegue il ciclo agentico. Modifica `history` in place; ritorna (risposta, log tool)."""
    log: list[str] = []
    for _ in range(config.MAX_TOOL_ROUNDS):
        resp = client.messages.create(
            model=config.MODEL,
            max_tokens=2048,
            system=system_prompt(),
            tools=tools.SCHEMAS + SERVER_TOOLS,
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
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": tools.run_tool(b.name, b.input)})
        history.append({"role": "user", "content": results})
    return "Ho raggiunto il limite di passaggi su questa richiesta, signore.", log
