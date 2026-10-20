from .. import pulizia

SCHEMAS = [
    {
        "name": "chiudi_giornata",
        "description": (
            "Pulizia di fine giornata a comando: tiene nell'archivio solo le cose che durano (decisioni, impegni, preferenze, persone) e "
            "domani si riparte leggeri. Usalo quando Andrea dice 'chiudiamo la giornata' o 'pulisci la memoria'. Non cancella ricordi esistenti "
            "e non salva dati di negozi, ragazzi, banca, mail o WhatsApp. Dopo, di' in una frase cosa e' successo."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def chiudi_giornata() -> str:
    return pulizia.pulisci(svuota=True)


HANDLERS = {"chiudi_giornata": chiudi_giornata}
