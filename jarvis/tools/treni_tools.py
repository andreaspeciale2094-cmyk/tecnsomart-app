from .. import treni

SCHEMAS = [
    {
        "name": "treno_stato",
        "description": (
            "Controlla ADESSO se il treno di Andrea (da Gaggiano verso Vigevano) e' in orario, in ritardo o soppresso. Treni abituali: apertura 7:48, chiusura 13:18. "
            "Usalo quando chiede 'com'e' il mio treno', 'il treno c'e'?', 'e' in ritardo?'. Senza parametri guarda il prossimo treno abituale di oggi; con 'turno' "
            "(apertura/chiusura) o 'ora' (per esempio 07:48) quello indicato. La fonte e' non ufficiale e per Trenord e' parziale: se dice che non trova il treno "
            "non affermare che e' soppresso, di' che non risulta e di controllare l'app Trenord. Rispondi in una frase."
        ),
        "input_schema": {"type": "object", "properties": {"turno": {"type": "string", "description": "apertura o chiusura"}, "ora": {"type": "string", "description": "Orario di partenza, per esempio 07:48."}}},
    },
]


def _stato(turno: str = "", ora: str = "") -> str:
    try:
        return treni.stato(ora, turno)
    except treni.TreniError as e:
        return f"Errore: {e}"


HANDLERS = {"treno_stato": _stato}
