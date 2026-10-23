from .. import agenda

SCHEMAS = [
    {
        "name": "briefing_mattino",
        "description": (
            "Briefing e agenda: data e ora, e gli impegni del giorno dal calendario PERSONALE e dal calendario di LAVORO, tenuti separati. "
            "Usalo quando l'utente dice buongiorno o chiede gli impegni, l'agenda o gli appuntamenti di oggi, di domani o di un altro giorno. "
            "Racconta a voce in modo naturale e BREVE (al massimo quattro frasi): prima cio' che conta di oggi, in ordine di orario, distinguendo personale e lavoro solo se serve; se non ci sono impegni dillo in una frase. "
            "La data dilla solo se e' utile, il saluto solo se ti hanno salutato. Se un calendario risulta non collegato o in errore, dillo con parole semplici. "
            "Il treno non e' ancora collegato: non parlarne. Se per oggi (e solo per il briefing di OGGI) hai anche lo strumento banca_riepilogo, "
            "chiamalo con giorni=7 e aggiungi UNA frase sul saldo e su eventuali pagamenti in attesa; se la banca da' errore, non insistere e non dirlo. "
            "Non salvare gli impegni ne' i soldi in memoria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"data": {"type": "string", "description": "Giorno nel formato AAAA-MM-GG. Se manca, oggi."}},
        },
    },
]


def briefing_mattino(data: str = "") -> str:
    try:
        return agenda.briefing(data)
    except agenda.AgendaError as e:
        return f"Errore: {e}"
    except ValueError:
        return "Errore: la data deve essere nel formato AAAA-MM-GG."


HANDLERS = {"briefing_mattino": briefing_mattino}
