from .. import siti

QUALITA = ("Fai siti professionali: struttura chiara (header con menu, sezioni, footer), grafica curata e coerente (palette di 2-3 colori, spazi larghi, titoli ben gerarchizzati), "
           "adatti al telefono (responsive), veloci, accessibili (contrasti, testi alternativi, tasti raggiungibili), in italiano, con testi veri e utili e non 'lorem ipsum'. "
           "Di norma file semplici: index.html + stile.css + script.js (niente strumenti da installare). Font solo di Google Fonts, immagini solo vere dell'utente o disegni SVG. "
           "NON scrivere mai chiavi, password, token o dati personali dentro un sito (e' pubblico). Prima chiedi scopo, colori, pagine e testi se mancano; poi scrivi tutto in una volta.")

SCHEMAS = [
    {"name": "sito_scrivi", "description": "Crea o aggiorna i file di un sito o di una webapp sul PC di Andrea (cartella locale, mai online). " + QUALITA +
     " Per le webapp con dati usa Google Apps Script come l'app dei negozi (file .gs a parte, senza chiavi). Dopo aver scritto dai l'anteprima con sito_anteprima. Pubblicare online e' un altro passo e vuole il si' di Andrea.",
     "input_schema": {"type": "object", "properties": {"nome": {"type": "string", "description": "nome corto del sito: lettere minuscole, numeri e trattini"},
                                                       "file": {"type": "array", "items": {"type": "object", "properties": {"percorso": {"type": "string"}, "contenuto": {"type": "string"}}, "required": ["percorso", "contenuto"]}}},
                      "required": ["nome", "file"]}},
    {"name": "sito_leggi", "description": "Legge un sito gia' fatto (elenco dei file, oppure il contenuto di un file) per poterlo modificare.",
     "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}, "percorso": {"type": "string"}}, "required": ["nome"]}},
    {"name": "siti_elenco", "description": "Elenca i siti che Jarvis ha fatto sul PC.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "sito_anteprima", "description": "Apre nel browser del PC l'anteprima di un sito fatto da Jarvis ('fammi vedere il sito').",
     "input_schema": {"type": "object", "properties": {"nome": {"type": "string"}}, "required": ["nome"]}},
]


def _protetto(f):
    def w(*a, **k):
        try:
            return f(*a, **k)
        except siti.SitoError as e:
            return f"Errore: {e}"
    return w


HANDLERS = {"sito_scrivi": _protetto(siti.scrivi), "sito_leggi": _protetto(siti.leggi), "siti_elenco": siti.elenco, "sito_anteprima": _protetto(siti.anteprima)}
