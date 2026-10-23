from .. import promemoria

SCHEMAS = [
    {
        "name": "promemoria_crea",
        "description": ("Crea un promemoria a voce: Jarvis lo dira' all'ora giusta. Usalo per 'ricordami alle 17 di chiamare Marco', 'tra 20 minuti ricordami la pasta', 'domani alle 9 ricordami...'. "
                        "Parametri: testo (cosa ricordare, breve), ora (HH:MM) oppure tra_minuti, giorno (oggi/domani/AAAA-MM-GG, facoltativo). Conferma in una frase."),
        "input_schema": {"type": "object", "properties": {
            "testo": {"type": "string"}, "ora": {"type": "string", "description": "HH:MM"}, "tra_minuti": {"type": "integer"},
            "giorno": {"type": "string", "description": "oggi, domani o AAAA-MM-GG"}}, "required": ["testo"]},
    },
    {"name": "promemoria_elenco", "description": "Elenca i promemoria in attesa.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "promemoria_togli", "description": "Toglie un promemoria (per id o per parole del testo) oppure 'tutti'.",
     "input_schema": {"type": "object", "properties": {"id_o_testo": {"type": "string"}}, "required": ["id_o_testo"]}},
]


def _crea(testo: str, ora: str = "", giorno: str = "", tra_minuti: int = 0) -> str:
    try:
        return promemoria.crea(testo, ora, giorno, tra_minuti)
    except promemoria.PromemoriaError as e:
        return f"Errore: {e}"


HANDLERS = {"promemoria_crea": _crea, "promemoria_elenco": promemoria.elenco, "promemoria_togli": promemoria.togli}
