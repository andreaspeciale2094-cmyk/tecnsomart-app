"""Registro dei tool: ogni modulo espone SCHEMAS (per Claude) e HANDLERS (funzioni)."""
from . import memory_tools, web, pc, home, mail_calendar

_MODULES = [memory_tools, web, pc, home, mail_calendar]

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
