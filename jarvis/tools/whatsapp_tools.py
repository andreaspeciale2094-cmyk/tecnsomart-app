from .. import config, whatsapp

_NOTA = ("Non puoi leggere le chat e non invii tu: apri WhatsApp con il testo pronto e Andrea preme Invio. "
         "Nomi, numeri e messaggi non vanno in memoria (ne' remember ne' core_add) ne' nei riassunti.")
SCHEMAS = [
    {
        "name": "whatsapp_contatto_salva",
        "description": "Salva il numero di una persona nella rubrica sul PC di Andrea. " + _NOTA,
        "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}, "numero": {"type": "string"}}, "required": ["nome", "numero"]},
    },
    {
        "name": "whatsapp_rubrica",
        "description": "Elenca i nomi presenti nella rubrica (mai i numeri).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "whatsapp_prepara",
        "description": (
            "Prepara un messaggio WhatsApp per una persona (nome in rubrica o numero) SENZA aprirlo. Leggi il testo ad Andrea e chiedi "
            "'Lo apro in WhatsApp?'. Scrivi nel tono di Andrea, breve, senza inventare fatti. " + _NOTA
        ),
        "input_schema": {"type": "object", "properties": {"a": {"type": "string", "description": "Nome in rubrica o numero."}, "testo": {"type": "string"}}, "required": ["a", "testo"]},
    },
    {
        "name": "whatsapp_apri",
        "description": (
            ("Se esiste lo strumento whatsapp_invia usa quello e non questo. " if config.ENABLE_WHATSAPP_INVIO else "") +
            "Apre WhatsApp sul PC con il messaggio gia' scritto, SOLO dopo che Andrea l'ha visto e ha detto un si' chiaro in un messaggio "
            "successivo. Non funziona nello stesso turno della preparazione. Mai in background. Poi di' ad Andrea di premere Invio."
        ),
        "input_schema": {"type": "object", "properties": {"id_messaggio": {"type": "string"}}, "required": ["id_messaggio"]},
    },
]


if config.ENABLE_WHATSAPP_INVIO:
    SCHEMAS.append({
        "name": "whatsapp_invia",
        "description": (
            "Invia SENZA finestre un messaggio gia' preparato con whatsapp_prepara, SOLO dopo che Andrea l'ha visto e ha detto un si' chiaro "
            "in un messaggio successivo. Solo a persone della rubrica. Non funziona nello stesso turno della preparazione. Mai in background. "
            "Il messaggio parte con una pausa di qualche secondo: non dire 'inviato' prima della risposta dello strumento."
        ),
        "input_schema": {"type": "object", "properties": {"id_messaggio": {"type": "string"}}, "required": ["id_messaggio"]},
    })


def _prova(fn, *a):
    try:
        return fn(*a)
    except whatsapp.WhatsAppError as e:
        return f"Errore: {e}"


HANDLERS = {
    "whatsapp_contatto_salva": lambda nome, numero: _prova(whatsapp.salva_contatto, nome, numero),
    "whatsapp_rubrica": lambda: _prova(whatsapp.nomi),
    "whatsapp_prepara": lambda a, testo: _prova(whatsapp.prepara, a, testo),
    "whatsapp_apri": lambda id_messaggio: _prova(whatsapp.apri, id_messaggio),
    "whatsapp_invia": lambda id_messaggio: _prova(whatsapp.invia, id_messaggio),
}
