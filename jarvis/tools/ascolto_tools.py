from .. import ascolto

SCHEMAS = [
    {
        "name": "ascolto_pausa",
        "description": (
            "Mette in pausa l'ascolto in stanza per N minuti (riunione, telefonata, privacy); poi riprende da solo. Usalo quando Andrea dice "
            "'non ascoltare', 'silenzio per un'ora', 'sto in riunione'. Per riprendere prima: Ctrl+Alt+J o 'ascolto on' da Telegram."
        ),
        "input_schema": {"type": "object", "properties": {"minuti": {"type": "integer", "description": "Da 1 a 480."}}, "required": ["minuti"]},
    },
]

HANDLERS = {"ascolto_pausa": lambda minuti: ascolto.pausa(minuti)}
