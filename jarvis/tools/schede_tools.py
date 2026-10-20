from .. import schede

_NOTA = ("Sono dati di una persona: restano solo nella scheda sul PC. Non salvarli con remember o core_add e non metterli nei riassunti.")
SCHEMAS = [
    {
        "name": "scheda_leggi",
        "description": "Legge la scheda di un ragazzo (cosa va bene, punti deboli, cosa e' gia' stato provato, com'e' andata). " + _NOTA,
        "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]},
    },
    {
        "name": "scheda_aggiungi",
        "description": (
            "Scrive UNA riga nella scheda di un ragazzo, SOLO se Andrea te l'ha detto o ha confermato con un si' chiaro. "
            "Se invece sei tu a notare un punto forte o debole dai numeri, proponilo a voce e chiedi 'lo segno nella scheda?' "
            "prima di scrivere. Sezioni: va_bene, debole, provato, esito. " + _NOTA
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "sezione": {"type": "string", "enum": list(schede.SEZIONI)},
                "testo": {"type": "string", "description": "Una frase breve."},
            },
            "required": ["nome", "sezione", "testo"],
        },
    },
    {
        "name": "scheda_togli",
        "description": "Sposta la scheda di un ragazzo in _da_eliminare (non la cancella). Chiedi conferma ad Andrea prima e attendi un si' chiaro.",
        "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]},
    },
]


def scheda_leggi(nome: str) -> str:
    return schede.leggi(nome) or f"Non c'e' ancora una scheda per '{nome}'. Schede esistenti: {', '.join(schede.elenco()) or 'nessuna'}."


def _prova(fn, *a):
    try:
        return fn(*a)
    except schede.SchedaError as e:
        return f"Errore: {e}"


HANDLERS = {
    "scheda_leggi": scheda_leggi,
    "scheda_aggiungi": lambda nome, sezione, testo: _prova(schede.aggiungi, nome, sezione, testo),
    "scheda_togli": lambda nome: _prova(schede.togli, nome),
}
