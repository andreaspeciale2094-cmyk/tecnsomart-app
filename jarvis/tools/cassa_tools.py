from .. import cassa

_NOTA = "Sono soldi di Andrea: non salvarli in memoria (ne' remember ne' core_add) e non metterli nei riassunti."
SCHEMAS = [
    {
        "name": "cassa_segna",
        "description": (
            "Segna nella cassa dei contanti un prelievo o una spesa detta da Andrea. Prima di scrivere ripeti a voce l'importo e il tipo "
            "('segno 60 euro spesi, giusto?') e scrivi solo dopo il si' di Andrea. Non spostare mai soldi e non toccare il conto: "
            "e' solo un registro. " + _NOTA
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["prelievo", "spesa"]},
                "importo": {"type": "number", "description": "Euro, numero positivo."},
                "nota": {"type": "string", "description": "Facoltativa: dove o per cosa (poche parole)."},
            },
            "required": ["tipo", "importo"],
        },
    },
    {
        "name": "cassa_resoconto",
        "description": "Quanto contante resta in cassa e cosa e' stato prelevato/speso in un giorno. Da usare anche nel riepilogo serale. " + _NOTA,
        "input_schema": {"type": "object", "properties": {"data": {"type": "string", "description": "AAAA-MM-GG, se manca oggi."}}},
    },
    {
        "name": "cassa_annulla_ultima",
        "description": "Annulla l'ultima voce della cassa se Andrea dice che e' sbagliata (resta nel registro come annullata). Chiedi conferma prima.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _prova(fn, *a):
    try:
        return fn(*a)
    except cassa.CassaError as e:
        return f"Errore: {e}"


HANDLERS = {
    "cassa_segna": lambda tipo, importo, nota="": _prova(cassa.segna, tipo, importo, nota),
    "cassa_resoconto": lambda data="": _prova(cassa.resoconto, data),
    "cassa_annulla_ultima": lambda: _prova(cassa.annulla_ultima),
}
