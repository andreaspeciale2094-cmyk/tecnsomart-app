from .. import treni

SCHEMAS = [
    {
        "name": "turno_imposta",
        "description": ("Segna il turno di lavoro di Andrea: apertura, chiusura o riposo, per oggi o per domani. Serve all'agente dei treni: guarda da solo il treno di quel turno "
                        "(apertura 7:48, chiusura 13:18) e lo avvisa se e' puntuale, in ritardo o cancellato. Usalo quando dice 'domani faccio apertura', 'oggi chiusura', 'domani sono a casa'."),
        "input_schema": {"type": "object", "properties": {
            "turno": {"type": "string", "enum": ["apertura", "chiusura", "riposo"]},
            "giorno": {"type": "string", "description": "oggi (predefinito), domani, un giorno della settimana (lunedi...) o una data"}}, "required": ["turno"]},
    },
    {
        "name": "turni_settimana",
        "description": ("Segna in una volta TUTTI i turni di una settimana (Andrea li manda ogni venerdi): per esempio 'lunedi apertura, martedi chiusura, mercoledi riposo...'. "
                        "Per ogni giorno scrivi giorno (un giorno della settimana, oggi, domani o una data) e turno (apertura, chiusura, riposo). Da quel momento Jarvis controlla da solo il treno e dice la sveglia la sera prima."),
        "input_schema": {"type": "object", "properties": {"turni": {"type": "array", "items": {"type": "object", "properties": {
            "giorno": {"type": "string"}, "turno": {"type": "string", "enum": ["apertura", "chiusura", "riposo"]}}, "required": ["giorno", "turno"]}}}, "required": ["turni"]},
    },
    {
        "name": "treno_stato",
        "description": (
            "Controlla ADESSO lo stato di QUALUNQUE treno o stazione (non solo quelli di Andrea): in orario, in ritardo o soppresso. Esempi: 'com'e' il mio treno' "
            "(i suoi abituali, da Gaggiano verso Vigevano: apertura 7:48, chiusura 13:18), 'il treno delle 14:20 da Milano Porta Genova', 'ci sono ritardi da Abbiategrasso "
            "verso Milano?', 'com'e' il treno 2431?'. Per una fascia ('treni tra le 6 e le 10 domani') usa da, a e giorno: elenca tutte le partenze. Parametri: stazione (predefinita Gaggiano), ora (07:48), turno (apertura/chiusura), direzione (una parola, per esempio "
            "Milano o Mortara), numero (numero del treno). Senza parametri guarda il prossimo treno abituale di Andrea. La fonte e' non ufficiale e per Trenord e' parziale: se "
            "dice che non trova il treno non affermare che e' soppresso, di' che non risulta e di controllare l'app Trenord. Rispondi in una o due frasi."
        ),
        "input_schema": {"type": "object", "properties": {
            "stazione": {"type": "string", "description": "Stazione di partenza. Se manca: Gaggiano."},
            "ora": {"type": "string", "description": "Orario di partenza, per esempio 07:48."},
            "turno": {"type": "string", "description": "apertura o chiusura (solo per i treni abituali)"},
            "direzione": {"type": "string", "description": "Una parola della destinazione, per esempio Milano."},
            "numero": {"type": "string", "description": "Numero del treno."},
            "da": {"type": "string", "description": "Inizio fascia oraria (06:00): per 'treni tra le 6 e le 10'."},
            "a": {"type": "string", "description": "Fine fascia oraria (10:00)."},
            "giorno": {"type": "string", "description": "oggi (predefinito) o domani, solo con da/a."}}},
    },
]


def _stato(turno: str = "", ora: str = "", stazione: str = "", direzione: str = "", numero: str = "", da: str = "", a: str = "", giorno: str = "") -> str:
    try:
        if da or a:
            return treni.fascia(da, a, giorno, stazione, direzione)
        return treni.stato(ora, turno, stazione, direzione, numero)
    except treni.TreniError as e:
        return f"Errore: {e}"


def _turno(turno: str, giorno: str = "") -> str:
    try:
        return treni.imposta_turno(turno, giorno)
    except treni.TreniError as e:
        return f"Errore: {e}"


def _settimana(turni):
    try:
        return treni.imposta_settimana(turni)
    except treni.TreniError as e:
        return f"Errore: {e}"


HANDLERS = {"treno_stato": _stato, "turno_imposta": _turno, "turni_settimana": _settimana}
