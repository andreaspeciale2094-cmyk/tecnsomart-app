from .. import pulizia

SCHEMAS = [
    {
        "name": "chiudi_giornata",
        "description": (
            "Chiusura della giornata. Quando Andrea dice 'concludi la giornata', 'chiudiamo la giornata', 'fine giornata' o 'resoconto serale' fai PRIMA "
            "il resoconto serale e SOLO DOPO chiama questo strumento: chiedi insieme (nella stessa risposta) riepilogo_negozi, cassa_resoconto, mail_non_lette e "
            "whatsapp_non_lette (quelli che hai), poi racconta in poche frasi (al massimo otto): com'e' andata nei negozi (chi sotto target, chi ha recuperato, "
            "chi non ha inserito i dati), quanto contante resta in cassa, quante mail e quali chat aspettano. Mai dire 'non c'era niente di importante' senza "
            "aver letto i dati. Questo strumento fa la pulizia della memoria: tiene nell'archivio solo le cose che durano (decisioni, impegni, preferenze, persone), "
            "domani si riparte leggeri; non cancella ricordi esistenti e non salva dati di negozi, ragazzi, banca, mail o WhatsApp. Se Andrea chiede solo "
            "'pulisci la memoria' basta la pulizia. Dopo, di' in una frase cosa e' successo."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def chiudi_giornata() -> str:
    return pulizia.pulisci(svuota=True)


HANDLERS = {"chiudi_giornata": chiudi_giornata}
