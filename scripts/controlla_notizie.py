"""Mostra quali giornali rispondono e i primi titoli. Non scrive niente."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import notizie

for nome, arg, url in notizie._fonti():
    try:
        n = len(notizie._leggi_feed((nome, arg, url)))
        print(f"OK     {nome}: {n} titoli")
    except Exception as e:
        print(f"NON VA {nome}: {type(e).__name__}")
print()
notizie.aggiorna()
for tema in ("Milano", "politica", "Milan"):
    print("=== " + tema)
    print(notizie.titoli(tema, 4))
