from .. import negozi

SCHEMAS = [
    {
        "name": "riepilogo_negozi",
        "description": (
            "Riepilogo del RUN giornaliero dei negozi TecnoSmart: per gruppo e per negozio, oggi e mese contro i target, con i colori "
            "verde/giallo/rosso dell'app, chi e' indietro, chi sta recuperando e chi non ha inserito i dati. Usalo per il riepilogo serale. "
            "Racconta a voce in modo naturale: andamento del gruppo, i negozi sotto target, chi recupera, le anomalie (dati mancanti), "
            "un giudizio e uno o due consigli concreti; per questo riepilogo puoi usare fino a 8 frasi brevi. "
            "Se hai anche lo strumento cassa_resoconto, a fine riepilogo serale aggiungi in una frase quanto contante resta in cassa. "
            "Se Andrea chiede di un negozio in particolare e hai scheda_leggi, leggi anche la sua scheda (tipo negozio) per dire cosa e' gia' stato provato. "
            "Non salvare questi numeri in memoria (ne' con remember ne' con core_add): sono dati dei negozi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Giorno nel formato AAAA-MM-GG. Se manca, oggi."},
                "tipo": {"type": "string", "enum": ["mono", "multi", "tutti"], "description": "Quale RUN: mono brand, multi brand o tutti (predefinito)."},
            },
        },
    },
]


def riepilogo_negozi(data: str = "", tipo: str = "tutti") -> str:
    try:
        return negozi.riepilogo(data, tipo)
    except negozi.NegoziError as e:
        return f"Errore: {e}"
    except ValueError:
        return "Errore: la data deve essere nel formato AAAA-MM-GG."


HANDLERS = {"riepilogo_negozi": riepilogo_negozi}
