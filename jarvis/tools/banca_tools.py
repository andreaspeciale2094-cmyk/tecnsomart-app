from .. import banca

_NOTA = ("Sono dati bancari di Andrea: sola lettura, non salvarli in memoria (ne' remember ne' core_add) e non metterli nei riassunti. "
         "Non puoi pagare ne' spostare soldi e non devi mai chiedere password o codici.")
SCHEMAS = [
    {
        "name": "banca_riepilogo",
        "description": (
            "Riepilogo del conto personale di Andrea (sola lettura): saldo, entrate e uscite, dove vanno i soldi, spese che si ripetono "
            "(possibili abbonamenti), uscite piu' grosse. Racconta in poche frasi semplici, raggruppa tu i destinatari in categorie "
            "(casa, spesa, benzina, ecc.) e segnala cose strane. " + _NOTA
        ),
        "input_schema": {"type": "object", "properties": {"giorni": {"type": "integer", "description": "Quanti giorni indietro (predefinito 30)."}}},
    },
]


def banca_riepilogo(giorni: int = 30) -> str:
    try:
        return banca.riepilogo(int(giorni))
    except banca.BancaError as e:
        return f"Errore: {e}"


HANDLERS = {"banca_riepilogo": banca_riepilogo}
