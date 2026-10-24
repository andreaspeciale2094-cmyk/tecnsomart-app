from .. import promesse

SCHEMAS = [
    {"name": "calendario_prepara", "description": ("Prepara un appuntamento da mettere sul calendario di Andrea (a voce: 'metti un appuntamento domani alle 10 con Marco'). Calcola tu la data vera (AAAA-MM-GG) dalla data di oggi. "
                                                  "NON scrive ancora niente: mostra la scheda e chiede il si'. Poi aspetta che Andrea risponda con un NUOVO messaggio. Calendario 'lavoro' per negozi, fornitori, ragazzi, colloqui; altrimenti 'personale'."),
     "input_schema": {"type": "object", "properties": {"titolo": {"type": "string"}, "data": {"type": "string", "description": "AAAA-MM-GG"}, "ora": {"type": "string", "description": "HH:MM"},
                                                       "durata_min": {"type": "integer"}, "luogo": {"type": "string"}, "calendario": {"type": "string", "enum": ["personale", "lavoro"]}}, "required": ["titolo", "data", "ora"]}},
    {"name": "calendario_conferma", "description": "Scrive sul calendario l'appuntamento preparato, SOLO dopo che Andrea ha scritto un nuovo messaggio con il si'. Mai senza il suo si'.",
     "input_schema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
]


def _prepara(titolo: str, data: str, ora: str, durata_min: int = 60, luogo: str = "", calendario: str = "personale") -> str:
    return promesse.prepara_da_voce(titolo, data, ora, durata_min, luogo, calendario)


def _conferma(id: str) -> str:
    return promesse.conferma_da_brain(id)


HANDLERS = {"calendario_prepara": _prepara, "calendario_conferma": _conferma}
