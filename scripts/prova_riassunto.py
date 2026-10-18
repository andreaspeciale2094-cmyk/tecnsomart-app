"""Prova della memoria lunga: fa 16 scambi brevi (costano pochi centesimi), aspetta il riassunto e poi chiede
una cosa detta all'inizio. Jarvis deve essere acceso. Uso: python scripts/prova_riassunto.py"""
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
URL = "http://localhost:8000"
SESSIONE = "prova-riassunto"


def main():
    c = httpx.Client(timeout=90)
    if os.getenv("JARVIS_PASSWORD"):
        c.post(f"{URL}/api/login", json={"password": os.getenv("JARVIS_PASSWORD")})

    def chiedi(testo):
        r = c.post(f"{URL}/api/chat", json={"session": SESSIONE, "message": testo})
        return r.json().get("reply", "")

    print("1. Dico una cosa all'inizio...")
    print("   Jarvis:", chiedi("Per questa prova: la mia citta preferita e Lisbona. Rispondi solo ok."))
    for i in range(1, 16):
        r = chiedi(f"Prova numero {i}. Rispondi solo ok.")
        print(f"   {i:2}. {r[:50]}")
    print("2. Aspetto il riassunto (10 secondi)...")
    time.sleep(10)
    print("3. Chiedo la cosa detta all'inizio...")
    risposta = chiedi("Qual era la mia citta preferita che ti ho detto all'inizio della prova?")
    print("   Jarvis:", risposta)
    if "lisbona" in risposta.lower():
        print("\nRISULTATO: ha ricordato Lisbona. La memoria lunga funziona.")
    else:
        print("\nRISULTATO: non l'ha ricordata. Guarda logs/consumi.log (righe MEMORIA) e logs/errori.log.")
    print("Ricorda di dire a Jarvis: 'dimentica che la mia citta preferita e Lisbona' per ripulire la prova.")
    sys.exit(0 if "lisbona" in risposta.lower() else 1)


main()
