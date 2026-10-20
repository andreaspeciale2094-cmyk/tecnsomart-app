from .. import agenda

SCHEMAS = [
    {
        "name": "briefing_mattino",
        "description": (
            "Briefing e agenda: data e ora, e gli impegni del giorno dal calendario PERSONALE e dal calendario di LAVORO, tenuti separati. "
            "Usalo quando l'utente dice buongiorno o chiede gli impegni, l'agenda o gli appuntamenti di oggi, di domani o di un altro giorno. "
            "Racconta a voce in modo naturale e breve (fino a 6 frasi): saluta secondo l'ora, di' la data, poi gli impegni personali, poi quelli di lavoro, "
            "in ordine di orario, dicendo chiaramente quando non ce ne sono. Se un calendario risulta non collegato o in errore, dillo con parole semplici. "
            "Non parlare di treno o soldi: non sono ancora collegati. Non salvare gli impegni in memoria."
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
