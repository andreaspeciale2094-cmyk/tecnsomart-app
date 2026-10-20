"""Controlla la porta 'addetti' dell'app. Non mostra nomi ne' numeri, solo quanti addetti ha letto.
Uso: .venv\\Scripts\\python.exe scripts\\controlla_addetti.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import addetti, config, negozi  # noqa: E402


def main():
    print("1. Chiave TECNOSMART_TOKEN...", "OK" if config.TECNOSMART_TOKEN else "MANCA")
    if not config.TECNOSMART_TOKEN:
        return
    print("2. Chiedo all'app i numeri degli addetti del mese...")
    try:
        raw = addetti.leggi()
    except negozi.NegoziError as e:
        return print("   ERRORE:", e)
    print(f"   OK: {len(raw.get('addetti') or {})} addetti con numeri nel mese {raw.get('mese')}")
    print("\nTUTTO OK. Metti JARVIS_ADDETTI=true nel .env, riavvia Jarvis e chiedi: 'come sta andando <nome>?'")


main()
