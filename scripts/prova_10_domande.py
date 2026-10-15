"""Fine Fase 1: fa 10 domande di fila a Jarvis (che deve essere acceso) e dice se sono andate tutte bene.
Uso: python scripts/prova_10_domande.py"""
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
URL = "http://localhost:8000"
DOMANDE = [
    "Ciao, chi sei?", "Che ore sono?", "Che giorno e' oggi?", "Dimmi una battuta breve.", "Quanto fa 17 per 23?",
    "Come si dice 'buongiorno' in inglese?", "Dammi un consiglio per concentrarmi.", "Ricorda che il mio colore preferito e' il blu.",
    "Che colore mi piace?", "Grazie, per ora basta.",
]


def main():
    client = httpx.Client(timeout=90)
    if os.getenv("JARVIS_PASSWORD"):
        client.post(f"{URL}/api/login", json={"password": os.getenv("JARVIS_PASSWORD")})
    ok = 0
    for i, d in enumerate(DOMANDE, 1):
        t = time.time()
        try:
            r = client.post(f"{URL}/api/chat", json={"session": "prova10", "message": d})
            j = r.json()
            bene = r.status_code == 200 and not j.get("error") and j.get("reply")
            print(f"{i:2}. {'OK ' if bene else 'ERRORE'} ({time.time() - t:.1f}s) {d} -> {str(j.get('reply'))[:90]}")
            ok += bool(bene)
        except Exception as e:
            print(f"{i:2}. ERRORE {d} -> Jarvis non risponde ({e}). E' acceso?")
    print(f"\nRisultato: {ok} su {len(DOMANDE)}. " + ("Fase 1 superata!" if ok == len(DOMANDE) else "Non ancora: guarda gli errori sopra e logs/errori.log."))
    sys.exit(0 if ok == len(DOMANDE) else 1)


main()
