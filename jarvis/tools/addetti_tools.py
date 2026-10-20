from .. import negozi
from .. import addetti

SCHEMAS = [
    {
        "name": "focus_addetto",
        "description": (
            "Numeri del mese di un addetto dei negozi TecnoSmart (pezzi per prodotto e punti per categoria) confrontati con la squadra. "
            "Senza nome da' il quadro di tutta la squadra. Usalo quando Andrea chiede come sta andando un ragazzo. "
            "Rispondi in poche frasi semplici: dove eccelle, dove ha mancanze (sotto la media) e che focus dare. Il mese e' parziale: "
            "confronta con la squadra, non con il target. Non salvare questi dati in memoria (ne' con remember ne' con core_add) "
            "e non riportare i nomi in altri strumenti."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome dell'addetto. Vuoto per tutta la squadra."},
                "mese": {"type": "string", "description": "Mese AAAA-MM. Se manca, il mese in corso."},
            },
        },
    },
]


def focus_addetto(nome: str = "", mese: str = "") -> str:
    try:
        return addetti.riepilogo(nome, mese)
    except negozi.NegoziError as e:
        return f"Errore: {e}"


HANDLERS = {"focus_addetto": focus_addetto}
