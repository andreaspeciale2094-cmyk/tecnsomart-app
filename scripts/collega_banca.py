"""Collega (o rinnova) il conto personale in SOLA LETTURA. Si fa una volta, poi circa ogni 90 giorni.
Uso: .venv\\Scripts\\python.exe scripts\\collega_banca.py [Intesa|UniCredit]"""
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import banca  # noqa: E402


def main():
    nome = {"intesa": "Intesa Sanpaolo", "unicredit": "UniCredit"}.get((sys.argv[1] if len(sys.argv) > 1 else "intesa").lower())
    if not nome:
        return print("Scrivi 'Intesa' oppure 'UniCredit' dopo il nome del file.")
    try:
        url = banca.avvia_collegamento(nome)
    except banca.BancaError as e:
        return print("ERRORE:", e)
    print(f"Ora si apre il browser: entra nella banca ({nome}) e conferma con la sua app. Il permesso e' solo di LETTURA.")
    webbrowser.open(url)
    print("\nAlla fine il browser mostra una pagina di errore ('impossibile raggiungere il sito'): e' normale.")
    print("Copia tutto l'indirizzo in alto nel browser (quello con 'code=') e incollalo qui sotto, poi Invio.")
    try:
        print(banca.completa_collegamento(input("Indirizzo: ")))
    except banca.BancaError as e:
        print("ERRORE:", e)


main()
