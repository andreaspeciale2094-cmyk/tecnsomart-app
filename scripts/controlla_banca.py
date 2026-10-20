"""Controlla il collegamento con la banca. Non mostra importi ne' nomi, solo se funziona.
Uso: .venv\\Scripts\\python.exe scripts\\controlla_banca.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import banca  # noqa: E402


def main():
    try:
        s = banca._sessione()
        print(f"1. Collegamento: OK ({len(s['conti'])} conto/i, valido fino al {s['scade']})")
        print(f"2. Movimenti ultimi 30 giorni: {len(banca.movimenti(30))} letti")
    except banca.BancaError as e:
        return print("ERRORE:", e)
    print("\nTUTTO OK. Metti JARVIS_BANCA=true nel .env, riavvia Jarvis e chiedi: 'come vanno i miei conti?'")


main()
