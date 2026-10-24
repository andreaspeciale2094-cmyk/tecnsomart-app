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
    {"name": "diario_agenti", "description": "Cosa hanno fatto oggi gli agenti di sottofondo (treno, promemoria, avvisi, riparazioni). Da leggere nel resoconto serale, quando Andrea chiude la giornata.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "promesse_aperte", "description": "Le cose che Andrea ha promesso OGGI su WhatsApp ('ti faccio sapere', 'domani ti chiamo', 'ti mando il file') e non ha ancora mantenuto. Da leggere nel resoconto serale. Usa un modello leggero solo se ci sono candidati.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "chiamate_perse", "description": "Le chiamate perse di oggi sul telefono di Andrea (le manda il telefono a Jarvis). Per 'chi mi ha chiamato?'. Se Andrea vuole richiamare, usa chiama_prepara con il nome.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "agenti_attivi", "description": "L'elenco vero degli agenti di sottofondo accesi e cosa fa ciascuno. Usalo se Andrea chiede 'quali agenti sono attivi?', 'cosa fanno gli agenti?'.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "promemoria_elenco", "description": "Elenca i promemoria in attesa.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "promemoria_togli", "description": "Toglie un promemoria (per id o per parole del testo) oppure 'tutti'.",
     "input_schema": {"type": "object", "properties": {"id_o_testo": {"type": "string"}}, "required": ["id_o_testo"]}},
]


def _crea(testo: str, ora: str = "", giorno: str = "", tra_minuti: int = 0) -> str:
    try:
        return promemoria.crea(testo, ora, giorno, tra_minuti)
    except promemoria.PromemoriaError as e:
        return f"Errore: {e}"


def _diario() -> str:
    from .. import vigile
    return vigile.diario_testo()


def _promesse() -> str:
    from .. import config, promesse
    if not (config.ENABLE_WHATSAPP and config.ENABLE_WHATSAPP_LEGGI):
        return "La lettura di WhatsApp non e' attiva: non posso controllare le promesse."
    return promesse.testo()


def _perse() -> str:
    from .. import chiamate_perse
    return chiamate_perse.elenco()


def _agenti() -> str:
    from .. import vigile
    return vigile.agenti_elenco()


HANDLERS = {"agenti_attivi": _agenti, "chiamate_perse": _perse, "promesse_aperte": _promesse, "diario_agenti": _diario, "promemoria_crea": _crea, "promemoria_elenco": promemoria.elenco, "promemoria_togli": promemoria.togli}
