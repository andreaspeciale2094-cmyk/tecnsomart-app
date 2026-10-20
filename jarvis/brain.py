"""Il cervello: Claude + ciclo di tool use + memoria."""
import anthropic

from . import config, logs, router, tools
from .brain_prompts import STATIC_PROMPT, context_prompt, system_blocks, system_prompt  # noqa: F401

client = anthropic.Anthropic()

# Ricerca web lato server di Anthropic (nessun codice da mantenere).
SERVER_TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if config.ENABLE_WEB_SEARCH else []


BLOCKED_UNATTENDED = {"run_shell", "write_file", "background_task", "schedule_task", "cancel_task",
                      "banca_riepilogo", "banca_movimenti"}  # la banca solo quando Andrea e' presente


def _last_user_text(history: list[dict]) -> str:
    for m in reversed(history):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"]
    return ""


def _without_thinking(content: list) -> list:
    """Toglie i "pensieri" nascosti di Claude prima di salvarli nella storia.
    Sono firmati sul testo di partenza (system, strumenti, messaggi): noi lo cambiamo a ogni richiesta (ora, ricordi,
    riassunto), quindi rimandarli indietro darebbe errore 400 ("bound to a different conversation"). Non servono."""
    return [b for b in content if getattr(b, "type", None) not in ("thinking", "redacted_thinking")]


def think_stream(history: list[dict], unattended: bool = False, summary: str = ""):
    """Ciclo agentico a pezzi: produce eventi {"type": "text"|"tool"|"done", ...}.
    Il testo arriva man mano che Claude lo scrive, cosi' Jarvis puo' parlare subito."""
    log: list[str] = []
    query = _last_user_text(history)
    if not unattended:  # richieste semplici: prima Groq (economico), se non e' sicuro risponde Claude
        quick = router.route(history, query, summary)
        if quick:
            history.append({"role": "assistant", "content": quick})
            yield {"type": "text", "delta": quick}
            yield {"type": "done", "reply": quick, "tools": ["risposto da Groq"]}
            return
    schemas = [t for t in tools.SCHEMAS if not (unattended and t["name"] in BLOCKED_UNATTENDED)]
    for _ in range(config.MAX_TOOL_ROUNDS):
        with client.messages.stream(
            model=config.MODEL,
            max_tokens=4096,  # il "pensiero" conta nel limite
            output_config={"effort": config.EFFORT},
            system=system_blocks(query, unattended, summary),
            tools=schemas + SERVER_TOOLS,
            messages=history,
        ) as stream:
            for ev in stream:
                if ev.type == "text":
                    yield {"type": "text", "delta": ev.text}
                elif ev.type == "content_block_start" and getattr(ev.content_block, "type", "") in ("tool_use", "server_tool_use"):
                    yield {"type": "tool", "name": ev.content_block.name}  # subito: la pagina puo' dire cosa sta facendo
            resp = stream.get_final_message()
        logs.log_usage(config.MODEL, resp.usage)
        history.append({"role": "assistant", "content": _without_thinking(resp.content)})

        if resp.stop_reason == "pause_turn":  # il server-side tool ha bisogno di continuare
            continue
        if resp.stop_reason != "tool_use":
            yield {"type": "done", "reply": "".join(b.text for b in resp.content if b.type == "text").strip(), "tools": log}
            return

        results = []
        for b in resp.content:
            if b.type == "tool_use":
                log.append(f"{b.name}({b.input})")
                out = "Errore: tool non consentito in background." if unattended and b.name in BLOCKED_UNATTENDED else tools.run_tool(b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        history.append({"role": "user", "content": results})
    msg = "Ho raggiunto il limite di passaggi su questa richiesta, signore."
    yield {"type": "text", "delta": msg}
    yield {"type": "done", "reply": msg, "tools": log}


def think(history: list[dict], unattended: bool = False, summary: str = "") -> tuple[str, list[str]]:
    """Come think_stream, ma aspetta la fine. Ritorna (risposta, log strumenti)."""
    reply, log = "", []
    for ev in think_stream(history, unattended, summary):
        if ev["type"] == "done":
            reply, log = ev["reply"], ev["tools"]
    return reply, log
