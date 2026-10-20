"""Controlla i due calendari: indirizzo presente, calendario leggibile, quanti impegni oggi (solo numeri).
Non mostra mai gli indirizzi. Uso: .venv\\Scripts\\python.exe scripts\\controlla_agenda.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import agenda, config  # noqa: E402


def main():
    day = agenda.parse_day()
    ok = True
    for nome, url, var in (("personale", config.CALENDARIO_PERSONALE_ICS, "CALENDARIO_PERSONALE_ICS"),
                           ("di lavoro", config.CALENDARIO_LAVORO_ICS, "CALENDARIO_LAVORO_ICS")):
        print(f"Calendario {nome}...", end=" ")
        if not url:
            print(f"MANCA {var} nel file .env")
            ok = False
            continue
        try:
            n = len(agenda.eventi(url, day))
            print(f"OK, {n} impegni oggi")
        except agenda.AgendaError as e:
            print("ERRORE:", e)
            ok = False
    print("\nTUTTO OK: puoi dire a Jarvis 'buongiorno'." if ok else "\nNon ancora: sistema le righe sopra.")


main()
