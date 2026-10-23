from .. import chiamate

_NOTA = "Non puoi rispondere alle chiamate ne' parlare: avvii soltanto la chiamata dal PC. Nomi e numeri non vanno in memoria ne' nei riassunti."
SCHEMAS = [
    {
        "name": "chiama_prepara",
        "description": "Prepara una telefonata a una persona della rubrica (o a un numero) SENZA avviarla. Poi chiedi ad Andrea 'Chiamo <nome>?'. " + _NOTA,
        "input_schema": {"type": "object", "properties": {"chi": {"type": "string", "description": "Nome in rubrica o numero."}}, "required": ["chi"]},
    },
    {
        "name": "chiama_avvia",
        "description": ("Avvia la telefonata gia' preparata, SOLO dopo che Andrea ha sentito a chi chiami e ha detto un si' chiaro in un messaggio successivo. "
                        "Non funziona nello stesso turno della preparazione. Mai in background. " + _NOTA),
        "input_schema": {"type": "object", "properties": {"id_chiamata": {"type": "string"}}, "required": ["id_chiamata"]},
    },
]


def _prova(fn, *a):
    try:
        return fn(*a)
    except chiamate.ChiamataError as e:
        return f"Errore: {e}"


HANDLERS = {
    "chiama_prepara": lambda chi: _prova(chiamate.prepara, chi),
    "chiama_avvia": lambda id_chiamata: _prova(chiamate.avvia, id_chiamata),
}
