"""Registro dei tool. Ogni modulo espone SCHEMAS (per Claude) e HANDLERS (funzioni).
I moduli extra si caricano solo se attivati in .env: quelli spenti non costano nulla."""
from .. import config
from . import agents, home, mail_calendar, memory_tools, pc, web

_MODULES = [memory_tools, web]
if config.PC_CONTROL:
    _MODULES.append(pc)
if config.ENABLE_HOME:
    _MODULES.append(home)
if config.ENABLE_MAIL:
    _MODULES.append(mail_calendar)
if config.ENABLE_AGENTS:
    _MODULES.append(agents)

SCHEMAS = [s for m in _MODULES for s in m.SCHEMAS]
HANDLERS = {k: v for m in _MODULES for k, v in m.HANDLERS.items()}


def run_tool(name: str, args: dict) -> str:
    handler = HANDLERS.get(name)
    if not handler:
        return f"Errore: tool sconosciuto '{name}'"
    try:
        return str(handler(**args))[:20000]
    except Exception as e:  # il cervello vede l'errore e puo' riprovare
        return f"Errore in {name}: {e}"
