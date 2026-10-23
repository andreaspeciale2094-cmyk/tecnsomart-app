from .. import agenti

SCHEMAS = [
    {
        "name": "delega_agenti",
        "description": (
            "Per richieste AMPIE su piu' cose insieme (il quadro di oggi, 'cosa devo sapere', un briefing, 'com'e' la situazione', un riepilogo di giornata): "
            "affida il lavoro a piu' agenti specializzati che lavorano NELLO STESSO MOMENTO e ti riportano un riassunto ciascuno. "
            "Agenti: agenda (impegni), posta (mail non lette), whatsapp (messaggi non letti), negozi (andamento punti vendita e ragazzi), soldi (conto, solo lettura), ricerca (internet), memoria (ricordi), pc (app e file). Usali anche per richieste che mischiano piu' cose (per esempio cercare online E controllare i ricordi E l'agenda). "
            "Scegli solo quelli che servono alla richiesta; nel campo richiesta puoi precisare cosa cercare. Poi metti tu insieme i riassunti in poche frasi "
            "(al massimo cinque, solo le cose che contano). Gli agenti leggono soltanto: per inviare, scrivere o fare qualcosa usi tu gli strumenti, con le conferme di Andrea. "
            "Per UNA sola cosa usa direttamente lo strumento giusto, senza agenti."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "compiti": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agente": {"type": "string", "enum": ["agenda", "posta", "whatsapp", "negozi", "soldi", "ricerca", "memoria", "pc"]},
                            "richiesta": {"type": "string", "description": "Cosa deve cercare (facoltativo)."},
                        },
                        "required": ["agente"],
                    },
                }
            },
            "required": ["compiti"],
        },
    },
]

HANDLERS = {"delega_agenti": lambda compiti: agenti.esegui(compiti)}
