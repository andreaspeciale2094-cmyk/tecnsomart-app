from .. import appunti

SCHEMAS = [
    {"name": "appunto_aggiungi", "description": "Segna una cosa in una lista semplice (senza ora): 'segna che devo ordinare i cavi', 'aggiungi latte alla lista della spesa'. Liste: 'da fare' (predefinita) e 'spesa'. Per cose con un'ora usa promemoria_crea.",
     "input_schema": {"type": "object", "properties": {"testo": {"type": "string"}, "lista": {"type": "string", "description": "spesa oppure da fare (predefinita)"}}, "required": ["testo"]}},
    {"name": "appunti_leggi", "description": "Legge le liste di appunti ('cosa c'e' nella lista della spesa?', 'cosa devo fare?'). Senza lista le legge tutte.",
     "input_schema": {"type": "object", "properties": {"lista": {"type": "string"}}}},
    {"name": "appunto_togli", "description": "Toglie una voce da una lista ('togli il latte dalla spesa') oppure 'tutto' per svuotarla. Solo se Andrea lo chiede.",
     "input_schema": {"type": "object", "properties": {"testo": {"type": "string"}, "lista": {"type": "string"}}, "required": ["testo"]}},
]


def _agg(testo: str, lista: str = "") -> str:
    try:
        return appunti.aggiungi(testo, lista)
    except appunti.AppuntiError as e:
        return f"Errore: {e}"


HANDLERS = {"appunto_aggiungi": _agg, "appunti_leggi": lambda lista="": appunti.leggi(lista), "appunto_togli": lambda testo, lista="": appunti.togli(testo, lista)}
