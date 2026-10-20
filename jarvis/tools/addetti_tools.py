from .. import addetti, negozi, schede

SCHEMAS = [
    {
        "name": "focus_addetto",
        "description": (
            "Numeri del mese di un addetto dei negozi TecnoSmart (pezzi per prodotto e punti per categoria) confrontati con la squadra. "
            "Senza nome da' il quadro di tutta la squadra. Usalo quando Andrea chiede come sta andando un ragazzo. "
            "Rispondi in poche frasi semplici: dove eccelle, dove ha mancanze (sotto la media) e che focus dare. Il mese e' parziale: "
            "confronta con la squadra, non con il target. Non salvare questi dati in memoria (ne' con remember ne' con core_add) "
            "e non riportare i nomi in altri strumenti. Se esiste la scheda del ragazzo, viene allegata: usala per dire cosa e' gia' stato provato. "
            "Se noti un punto forte o debole, proponi a voce di segnarlo nella scheda e scrivi solo dopo il si' di Andrea."
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
        out = addetti.riepilogo(nome, mese)
        sch = schede.leggi(nome) if nome else None
        return out + (f"\n\nSCHEDA SALVATA SUL PC:\n{sch}" if sch else "")
    except negozi.NegoziError as e:
        return f"Errore: {e}"


HANDLERS = {"focus_addetto": focus_addetto}
