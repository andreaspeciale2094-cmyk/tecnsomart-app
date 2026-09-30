from .. import scheduler

SCHEMAS = [
    {
        "name": "background_task",
        "description": "Avvia un agente autonomo in background per un compito lungo (ricerche, analisi, raccolta info). Il risultato arriva nelle notifiche. Usalo quando l'utente non deve aspettare.",
        "input_schema": {"type": "object", "properties": {"goal": {"type": "string", "description": "Obiettivo completo e autosufficiente"}}, "required": ["goal"]},
    },
    {
        "name": "schedule_task",
        "description": "Pianifica un'attivita' ricorrente o un promemoria. Usa `at` (HH:MM, ogni giorno) oppure `every_minutes`. `prompt` e' l'istruzione che Jarvis eseguira' da solo; il risultato va nelle notifiche.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "prompt": {"type": "string"}, "at": {"type": "string"}, "every_minutes": {"type": "integer"}},
            "required": ["name", "prompt"],
        },
    },
    {"name": "list_tasks", "description": "Elenca le attivita' pianificate.", "input_schema": {"type": "object", "properties": {}}},
    {
        "name": "cancel_task",
        "description": "Annulla un'attivita' pianificata tramite id.",
        "input_schema": {"type": "object", "properties": {"job_id": {"type": "integer"}}, "required": ["job_id"]},
    },
]


def schedule_task(name, prompt, at="", every_minutes=0):
    if not at and not every_minutes:
        return "Specifica `at` (HH:MM) oppure `every_minutes`."
    return f"Pianificato (id {scheduler.add_job(name, prompt, at, every_minutes)})."


HANDLERS = {
    "background_task": lambda goal: scheduler.start_background_agent(goal),
    "schedule_task": schedule_task,
    "list_tasks": lambda: scheduler.list_jobs() or "Nessuna attivita' pianificata.",
    "cancel_task": lambda job_id: "Annullata." if scheduler.cancel_job(job_id) else "Id non trovato.",
}
