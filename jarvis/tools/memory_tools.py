from .. import memory

SCHEMAS = [
    {
        "name": "remember",
        "description": "Salva un fatto duraturo sull'utente (preferenze, persone, abitudini, impegni). Usalo proattivamente.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "recall",
        "description": "Cerca nella memoria a lungo termine. Senza query restituisce i fatti piu' recenti.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    {
        "name": "forget",
        "description": "Elimina un ricordo tramite il suo id.",
        "input_schema": {"type": "object", "properties": {"fact_id": {"type": "integer"}}, "required": ["fact_id"]},
    },
]

HANDLERS = {
    "remember": lambda text: f"Salvato (id {memory.remember(text)})",
    "recall": lambda query="": memory.recall(query) or "Nessun ricordo trovato.",
    "forget": lambda fact_id: "Eliminato." if memory.forget(fact_id) else "Id non trovato.",
}
