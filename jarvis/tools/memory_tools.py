from .. import memory, memory_core

SCHEMAS = [
    {
        "name": "remember",
        "description": "Salva nell'ARCHIVIO un fatto duraturo sull'utente (preferenze, persone, impegni, dettagli). Usalo proattivamente. Per le cose essenziali e permanenti usa invece core_add.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "recall",
        "description": "Cerca nell'archivio dei ricordi (per significato). Usalo quando serve qualcosa che non e' nella memoria viva ne' nei ricordi gia' mostrati. Senza query restituisce i piu' recenti.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    {
        "name": "core_add",
        "description": "Aggiunge UNA riga breve alla MEMORIA VIVA (sempre letta): solo cose essenziali e permanenti su chi e' l'utente, regole, orari ricorrenti, persone importanti. Il resto va in `remember`.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "core_remove",
        "description": "Toglie una riga dalla memoria viva, tramite il suo numero (vedi core_show).",
        "input_schema": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]},
    },
    {"name": "core_show", "description": "Mostra le righe della memoria viva con il loro numero.", "input_schema": {"type": "object", "properties": {}}},
    {
        "name": "forget",
        "description": "Elimina un ricordo tramite il suo id.",
        "input_schema": {"type": "object", "properties": {"fact_id": {"type": "integer"}}, "required": ["fact_id"]},
    },
]

def _core_show():
    return "\n".join(f"{n}. {t}" for n, t in memory_core.numbered()) or "La memoria viva e' vuota."


HANDLERS = {
    "core_add": lambda text: memory_core.add(text),
    "core_remove": lambda number: memory_core.remove(number),
    "core_show": _core_show,
    "remember": lambda text: f"Salvato (id {memory.remember(text)})",
    "recall": lambda query="": memory.recall(query) or "Nessun ricordo trovato.",
    "forget": lambda fact_id: "Eliminato." if memory.forget(fact_id) else "Id non trovato.",
}
