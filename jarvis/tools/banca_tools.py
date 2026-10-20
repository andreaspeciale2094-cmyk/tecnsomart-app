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
    {
        "name": "banca_movimenti",
        "description": (
            "Elenco dei singoli movimenti del conto di Andrea, uno per riga, con data di pagamento. Usalo quando chiede cosa ha speso un certo "
            "giorno, 'ieri', 'giorno per giorno' o il dettaglio. Per 'ieri' usa giorni=3 e guarda solo la data di ieri: non dire che e' "
            "impossibile solo perche' la banca registra alcuni pagamenti dopo. Somma tu per giorno e raggruppa in categorie. "
            "Se manca il nome del negozio dillo una volta. " + _NOTA
        ),
        "input_schema": {"type": "object", "properties": {
            "giorni": {"type": "integer", "description": "Quanti giorni indietro (predefinito 7)."},
            "anche_entrate": {"type": "boolean", "description": "Includi anche le entrate (predefinito no)."}}},
    },
]


def banca_riepilogo(giorni: int = 30) -> str:
    try:
        return banca.riepilogo(int(giorni))
    except banca.BancaError as e:
        return f"Errore: {e}"


def banca_movimenti(giorni: int = 7, anche_entrate: bool = False) -> str:
    try:
        return banca.elenco(int(giorni), bool(anche_entrate))
    except banca.BancaError as e:
        return f"Errore: {e}"


HANDLERS = {"banca_riepilogo": banca_riepilogo, "banca_movimenti": banca_movimenti}
