"""Conversazioni in corso: storia recente + riassunto dei messaggi vecchi (compattazione)."""
import threading
import time

from . import config, logs, memory, summarize

histories: dict[str, list] = {}
summaries: dict[str, str] = {}
_lock = threading.Lock()
_compacting: set[str] = set()


def text_turns(history: list) -> list[dict]:
    """Solo i messaggi di testo (utente e Jarvis): niente strumenti ne' blocchi di pensiero."""
    out = []
    for m in history:
        c = m["content"]
        if isinstance(c, str):
            out.append({"role": m["role"], "content": c})
        elif m["role"] == "assistant":
            txt = "".join(getattr(b, "text", "") for b in c if getattr(b, "type", None) == "text").strip()
            if txt:
                out.append({"role": "assistant", "content": txt})
    return out


def get(sid: str) -> list:
    return histories.setdefault(sid, [])


def start_request(sid: str, message: str) -> tuple[list, int]:
    """Aggiunge il messaggio dell'utente. Rete di sicurezza: se la storia e' enorme riparte pulita."""
    with _lock:
        h = get(sid)
        if len(h) > config.HARD_MAX_MESSAGES:
            recent = text_turns(h)[-config.KEEP_RECENT:]
            while recent and recent[0]["role"] != "user":
                recent.pop(0)
            h[:] = recent
        before = len(h)
        h.append({"role": "user", "content": message})
        return h, before


def needs_compaction(sid: str) -> bool:
    return len(text_turns(get(sid))) > config.KEEP_RECENT + config.COMPACT_WHEN_OLDER


def compact_in_background(sid: str) -> None:
    if sid in _compacting or not needs_compaction(sid):
        return
    _compacting.add(sid)

    def run():
        try:
            for attempt in range(3):  # se nel frattempo arriva altro, riprova dopo qualche secondo
                if compact_session(sid) or not needs_compaction(sid):
                    break
                time.sleep(2)
        except Exception as e:  # non deve mai disturbare la conversazione
            logs.log_route(f"Riassunto non riuscito ({type(e).__name__}): riprovo al prossimo giro")
        finally:
            _compacting.discard(sid)

    threading.Thread(target=run, daemon=True).start()


def compact_session(sid: str) -> bool:
    with _lock:
        snap = list(get(sid))
        previous = summaries.get(sid, "")
    turns = text_turns(snap)
    if len(turns) <= config.KEEP_RECENT + config.COMPACT_WHEN_OLDER:
        return False
    old, recent = turns[:-config.KEEP_RECENT], turns[-config.KEEP_RECENT:]
    while recent and recent[0]["role"] != "user":  # la nuova storia deve iniziare da un messaggio dell'utente
        old.append(recent.pop(0))
    summary, facts = summarize.compact(old, previous)  # lento: senza tenere il blocco
    saved = [memory.remember(f) for f in facts]
    with _lock:
        h = get(sid)
        if len(h) != len(snap) or any(a is not b for a, b in zip(h, snap)):
            return False  # nel frattempo e' arrivato altro: si riprova al prossimo giro
        h[:] = recent   # storia pulita, solo testo: i "pensieri" di Claude restano validi
        summaries[sid] = summary
    logs.log_memory(f"compattazione: riassunti {len(old)} messaggi, {len(saved)} fatti nell'archivio")
    return True


def clear_summaries() -> None:
    """Quando si dimentica qualcosa, i riassunti (solo in memoria RAM) si svuotano: potrebbero contenerlo."""
    with _lock:
        summaries.clear()


memory.FORGET_HOOKS.append(clear_summaries)
