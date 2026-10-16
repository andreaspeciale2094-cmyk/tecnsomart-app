"""Il cervello: Claude + ciclo di tool use + memoria."""
import anthropic

from . import config, logs, router, tools
from .brain_prompts import STATIC_PROMPT, context_prompt, system_blocks, system_prompt  # noqa: F401

client = anthropic.Anthropic()

# Ricerca web lato server di Anthropic (nessun codice da mantenere).
SERVER_TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if config.ENABLE_WEB_SEARCH else []


BLOCKED_UNATTENDED = {"run_shell", "write_file", "background_task", "schedule_task", "cancel_task"}


def _last_user_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"]
    return ""


def think(history: list[dict], unattended: bool = False) -> tuple[str, list[str]]:
    """Esegue il ciclo agentico. Modifica `history` in place; ritorna (risposta, log tool)."""
    log: list[str] = []
    query = _last_user_text(history)
    if not unattended:  # richieste semplici: prima Groq (economico), se non e' sicuro risponde Claude
        quick = router.route(history, query)
        if quick:
            history.append({"role": "assistant", "content": quick})
            return quick, ["risposto da Groq"]
    schemas = [t for t in tools.SCHEMAS if not (unattended and t["name"] in BLOCKED_UNATTENDED)]
    for _ in range(config.MAX_TOOL_ROUNDS):
        resp = client.messages.create(
            model=config.MODEL,
            max_tokens=4096,  # il "pensiero" conta nel limite
            output_config={"effort": config.EFFORT},
            system=system_blocks(query, unattended),
            tools=schemas + SERVER_TOOLS,
            messages=history,
        )
        logs.log_usage(config.MODEL, resp.usage)
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
