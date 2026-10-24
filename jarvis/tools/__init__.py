"""Registro dei tool. Ogni modulo espone SCHEMAS (per Claude) e HANDLERS (funzioni).
I moduli extra si caricano solo se attivati in .env: quelli spenti non costano nulla."""
import json
import threading
import time

from .. import config
from . import appunti_tools, amazon_tools, calendario_tools, promemoria_tools, addetti_tools, chiamate_tools, treni_tools, pc_comandi_tools, ascolto_tools, agenda_tools, agenti_tools, banca_tools, cassa_tools, agents, home, mail_calendar, memory_tools, negozi_tools, pc, posta_tools, pulizia_tools, schede_tools, web, whatsapp_tools

_MODULES = [memory_tools, web, appunti_tools]
if config.ENABLE_ASCOLTO:
    _MODULES.append(ascolto_tools)
if config.ENABLE_PC_COMANDI:
    _MODULES.append(pc_comandi_tools)
if config.ENABLE_PULIZIA:
    _MODULES.append(pulizia_tools)
if config.PC_CONTROL:
    _MODULES.append(pc)
if config.ENABLE_HOME:
    _MODULES.append(home)
if config.ENABLE_MAIL:
    _MODULES.append(mail_calendar)
if config.ENABLE_AGENTS:
    _MODULES.append(agents)
if config.ENABLE_NEGOZI:
    _MODULES.append(negozi_tools)
if config.ENABLE_ADDETTI:
    _MODULES += [addetti_tools, schede_tools]
if config.ENABLE_CASSA:
    _MODULES.append(cassa_tools)
if config.ENABLE_BANCA:
    _MODULES.append(banca_tools)
if config.ENABLE_POSTA:
    _MODULES.append(posta_tools)
if config.ENABLE_WHATSAPP:
    _MODULES.append(whatsapp_tools)
if config.ENABLE_CHIAMATE:
    _MODULES.append(chiamate_tools)
if config.ENABLE_TRENI:
    _MODULES.append(treni_tools)
if config.ENABLE_PROMEMORIA:
    _MODULES.append(promemoria_tools)
if config.ENABLE_AGENDA:
    _MODULES.append(calendario_tools)
if config.ENABLE_AMAZON:
    _MODULES.append(amazon_tools)
if config.ENABLE_AGENDA:
    _MODULES.append(agenda_tools)
if config.ENABLE_AGENTI:
    _MODULES.append(agenti_tools)

SCHEMAS = [s for m in _MODULES for s in m.SCHEMAS]
HANDLERS = {k: v for m in _MODULES for k, v in m.HANDLERS.items()}


# Letture che si rifanno spesso: il risultato resta in RAM per qualche secondo e in sottofondo viene tenuto fresco (agenda, posta, WhatsApp),
# cosi' "dammi un quadro di oggi" non aspetta internet. Nulla finisce su disco. Gli errori non si tengono mai.
CACHE_LETTURE = {"briefing_mattino": 300, "mail_non_lette": 90, "whatsapp_non_lette": 20, "riepilogo_negozi": 120}  # secondi di validita'
_PREDEFINITI = {"mail_non_lette": {"limite": 10, "conto": "tutti"}, "briefing_mattino": {"data": ""}, "riepilogo_negozi": {"data": "", "tipo": "tutti"}}
_cache: dict[str, tuple[float, str]] = {}


def _chiave(name: str, args: dict) -> str:
    utili = {k: v for k, v in (args or {}).items() if _PREDEFINITI.get(name, {}).get(k) != v}  # {} e {"limite": 10} sono la stessa richiesta
    return name + json.dumps(utili, sort_keys=True, default=str)


def run_tool(name: str, args: dict) -> str:
    handler = HANDLERS.get(name)
    if not handler:
        return f"Errore: tool sconosciuto '{name}'"
    ttl = CACHE_LETTURE.get(name)
    chiave = _chiave(name, args) if ttl else ""
    if ttl:
        trovato = _cache.get(chiave)
        if trovato and time.time() - trovato[0] < ttl:
            return trovato[1]
    try:
        out = str(handler(**args))[:20000]
    except Exception as e:  # il cervello vede l'errore e puo' riprovare
        return f"Errore in {name}: {e}"
    if ttl and not out.startswith("Errore"):
        _cache[chiave] = (time.time(), out)
    return out


def _tieni_freschi():
    """Ogni tanto rilegge in sottofondo agenda, posta e WhatsApp (solo se attivi). Se uno non risponde, aspetta 5 minuti prima di riprovare."""
    rifai = {"briefing_mattino": 240, "mail_non_lette": 75, "whatsapp_non_lette": 15}
    riprova_dopo: dict[str, float] = {}
    while True:
        for nome, eta in rifai.items():
            if nome not in HANDLERS or time.time() < riprova_dopo.get(nome, 0):
                continue
            c = _cache.get(_chiave(nome, {}))
            if c and time.time() - c[0] < eta:
                continue
            _cache.pop(_chiave(nome, {}), None)
            if run_tool(nome, {}).startswith("Errore"):
                riprova_dopo[nome] = time.time() + 300
        time.sleep(10)


def avvia_cache():
    if any(n in HANDLERS for n in ("briefing_mattino", "mail_non_lette", "whatsapp_non_lette")):
        threading.Thread(target=_tieni_freschi, daemon=True).start()
