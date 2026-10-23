from .. import chiamate, rubrica_sync

_NOTA = "La chiamata parte SEMPRE dal cellulare di Andrea, collegato al PC: NON chiedere da quale telefono, app o dispositivo, e non proporre alternative. Non puoi rispondere alle chiamate ne' parlare: avvii soltanto la chiamata dal PC. Nomi e numeri non vanno in memoria ne' nei riassunti."
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
    {
        "name": "rubrica_sincronizza",
        "description": "Aggiorna adesso la rubrica con i contatti Google di Andrea (nomi e numeri cambiati dal telefono). Di solito si aggiorna da sola ogni 3 ore. Non mostrare nomi o numeri.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _prova(fn, *a):
    try:
        return fn(*a)
    except (chiamate.ChiamataError, rubrica_sync.RubricaError) as e:
        return f"Errore: {e}"


HANDLERS = {
    "chiama_prepara": lambda chi: _prova(chiamate.prepara, chi),
    "chiama_avvia": lambda id_chiamata: _prova(chiamate.avvia, id_chiamata),
    "rubrica_sincronizza": lambda: _prova(rubrica_sync.sincronizza),
}
