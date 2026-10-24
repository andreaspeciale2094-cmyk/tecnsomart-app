"""Mostra le partenze che Jarvis legge dal sito Trenord per una stazione (solo orari e stati dei treni).
Uso: .venv\\Scripts\\python.exe scripts\\controlla_trenord.py [stazione]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import trenord

nome = sys.argv[1] if len(sys.argv) > 1 else "Gaggiano"
try:
    for t in trenord.partenze(nome):
        stato = "CANCELLATO" if t["provvedimento"] else (f"{t['ritardo']} min di ritardo" if t["ritardo"] >= 3 else "in orario")
        print(f"{t['compOrarioPartenza']}  {t['linea']} {t['numeroTreno']}  verso {t['destinazione']}: {stato}")
except trenord.TrenordError as e:
    print("ERRORE:", e)
