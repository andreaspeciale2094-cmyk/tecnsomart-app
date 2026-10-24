from .. import amazon

SCHEMAS = [
    {"name": "amazon_cerca", "description": ("Cerca prodotti su Amazon.it e li elenca numerati (titolo, prezzo, stelle). Non compra niente. Usalo per 'cerca su Amazon...', 'trovami...'. "
                                            "Poi Andrea sceglie un numero. Se Amazon chiede un CAPTCHA o il login, ti dice cosa fare: fermati e riferiscilo."),
     "input_schema": {"type": "object", "properties": {"cosa": {"type": "string"}, "quanti": {"type": "integer"}}, "required": ["cosa"]}},
    {"name": "amazon_carrello_prepara", "description": ("Primo passo per mettere un risultato nel carrello: chiede il si' ad Andrea. NON tocca Amazon. Dopo, aspetta che Andrea risponda con un NUOVO messaggio."),
     "input_schema": {"type": "object", "properties": {"numero": {"type": "integer"}}, "required": ["numero"]}},
    {"name": "amazon_carrello_conferma", "description": ("Secondo passo: mette nel carrello (mai il pagamento) SOLO dopo che Andrea ha scritto un nuovo messaggio con il si'. Mai acquistare: l'acquisto lo fa Andrea."),
     "input_schema": {"type": "object", "properties": {"numero": {"type": "integer"}}, "required": ["numero"]}},
]


def _cerca(cosa: str, quanti: int = 5) -> str:
    try:
        return amazon.cerca(cosa, quanti)
    except amazon.AmazonError as e:
        return f"Errore: {e}"


def _prepara(numero: int) -> str:
    try:
        return amazon.prepara_carrello(numero)
    except amazon.AmazonError as e:
        return f"Errore: {e}"


def _conferma(numero: int) -> str:
    try:
        return amazon.conferma_carrello(numero)
    except amazon.AmazonError as e:
        return f"Errore: {e}"


HANDLERS = {"amazon_cerca": _cerca, "amazon_carrello_prepara": _prepara, "amazon_carrello_conferma": _conferma}
