"""Il cervello: Claude + ciclo di tool use + memoria."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

import anthropic

from . import config, logs, posta, router, tools
from .brain_prompts import STATIC_PROMPT, context_prompt, system_blocks, system_prompt  # noqa: F401

client = anthropic.Anthropic()

# Ricerca web lato server di Anthropic (nessun codice da mantenere).
SERVER_TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if config.ENABLE_WEB_SEARCH else []


BLOCKED_UNATTENDED = {"run_shell", "write_file", "background_task", "schedule_task", "cancel_task",
                      "banca_riepilogo", "banca_movimenti", "mail_invia", "chiama_prepara", "chiama_avvia", "whatsapp_apri", "whatsapp_invia", "whatsapp_non_lette", "whatsapp_leggi",
                      "pc_apri", "pc_volume", "pc_blocca", "pc_mostra_desktop", "pc_azione_prepara", "pc_azione_conferma", "pc_annulla_spegnimento", "pc_alias", "desktop_aggiungi", "desktop_togli", "desktop_importa_barra", "delega_agenti", "promemoria_crea", "promemoria_togli", "promesse_aperte", "calendario_prepara", "calendario_conferma", "amazon_cerca", "amazon_carrello_prepara", "amazon_carrello_conferma"}  # la banca solo quando Andrea e' presente


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


# Strumenti che SOLO leggono: se in una risposta Claude ne chiede piu' di uno, partono tutti nello stesso momento (agenda, posta, WhatsApp, negozi...).
# Appena c'e' anche uno strumento che scrive o fa qualcosa, si torna a uno alla volta, nell'ordine (stesse regole di prima).
SOLO_LETTURA = {"briefing_mattino", "riepilogo_negozi", "focus_addetto", "scheda_leggi", "mail_non_lette", "mail_leggi", "unread_emails", "upcoming_events",
                "whatsapp_non_lette", "whatsapp_leggi", "whatsapp_rubrica", "whatsapp_cerca", "whatsapp_chat_recenti", "treno_stato", "diario_agenti", "appunti_leggi", "agenti_attivi", "chiamate_perse", "promesse_aperte", "banca_riepilogo", "banca_movimenti", "cassa_resoconto", "pc_elenco_app", "pc_cerca",
                "fetch_url", "recall", "core_show", "list_tasks", "home_state", "read_file", "delega_agenti"}


SERIALI = {"banca_riepilogo", "banca_movimenti"}  # solo lettura, ma mai due insieme


def esegui_strumenti(blocchi: list, unattended: bool, log: list[str]) -> list[dict]:
    """Esegue gli strumenti chiesti da Claude e ritorna i risultati nello stesso ordine."""
    def uno(b):
        if unattended and b.name in BLOCKED_UNATTENDED:
            return "Errore: tool non consentito in background."
        return tools.run_tool(b.name, b.input)

    for b in blocchi:
        log.append(f"{b.name}({b.input})")
    if len(blocchi) > 1 and all(b.name in SOLO_LETTURA for b in blocchi):
        # la banca ha un limite di letture al giorno: le sue chiamate vanno una dopo l'altra (in un solo gruppo), il resto parte insieme
        gruppi = [[i] for i, b in enumerate(blocchi) if b.name not in SERIALI]
        if any(b.name in SERIALI for b in blocchi):
            gruppi.append([i for i, b in enumerate(blocchi) if b.name in SERIALI])
        outs = [""] * len(blocchi)

        def gruppo(indici):
            for i in indici:
                outs[i] = uno(blocchi[i])

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=min(len(gruppi), 6)) as ex:
            list(ex.map(gruppo, gruppi))
        log.append(f"letti insieme: {len(blocchi)} strumenti in {time.time() - t0:.1f} s")
    else:
        outs = [uno(b) for b in blocchi]
    return [{"type": "tool_result", "tool_use_id": b.id, "content": out} for b, out in zip(blocchi, outs)]


_RAGIONA = re.compile(r"\b(perch[eé]|come mai|conviene|meglio|confront\w*|decid\w*|consigli\w*|pianific\w*|strategia|organizz\w*|priorit\w*|analizz\w*|valut\w*|cosa ne pensi|che ne pensi|dovrei|secondo te|riassum\w*|quadro|situazione|prepara\w*|scriv\w*|rispond\w*)\b", re.IGNORECASE)


def _effort(query: str) -> str:
    """Quanto ragionare: poco per le cose semplici (piu' veloce), di piu' quando c'e' da pensare, decidere o scrivere."""
    if config.EFFORT != "auto":
        return config.EFFORT
    return "medium" if (len(query.split()) > 14 or _RAGIONA.search(query or "")) else "low"


def think_stream(history: list[dict], unattended: bool = False, summary: str = ""):
    """Ciclo agentico a pezzi: produce eventi {"type": "text"|"tool"|"done", ...}.
    Il testo arriva man mano che Claude lo scrive, cosi' Jarvis puo' parlare subito."""
    log: list[str] = []
    query = _last_user_text(history)
    if not unattended:
        posta.nuovo_turno()  # serve a garantire che una mail parta solo dopo un messaggio di Andrea
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
            output_config={"effort": _effort(query)},
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

        history.append({"role": "user", "content": esegui_strumenti([b for b in resp.content if b.type == "tool_use"], unattended, log)})
    msg = "Mi sono perso in troppi passaggi: prova a dividere la richiesta."
    yield {"type": "text", "delta": msg}
    yield {"type": "done", "reply": msg, "tools": log}


def think(history: list[dict], unattended: bool = False, summary: str = "") -> tuple[str, list[str]]:
    """Come think_stream, ma aspetta la fine. Ritorna (risposta, log strumenti)."""
    reply, log = "", []
    for ev in think_stream(history, unattended, summary):
        if ev["type"] == "done":
            reply, log = ev["reply"], ev["tools"]
    return reply, log
