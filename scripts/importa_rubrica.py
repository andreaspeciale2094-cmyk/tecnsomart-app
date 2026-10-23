"""Importa i numeri dalla rubrica di Google Contatti (file CSV esportato da te) nella rubrica di Jarvis, solo sul PC.
Non mostra nomi ne' numeri, solo quanti ne ha importati. Uso: .venv\\Scripts\\python.exe scripts\\importa_rubrica.py "C:\\percorso\\contacts.csv" """
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import whatsapp  # noqa: E402


def _col(header, *parole):
    return [i for i, h in enumerate(header) if all(p in h.lower() for p in parole)]


def main():
    if len(sys.argv) < 2 or not Path(sys.argv[1]).exists():
        return print('Scrivi il percorso del file CSV tra virgolette dopo il nome dello script.')
    with open(sys.argv[1], encoding="utf-8-sig", newline="") as f:
        righe = list(csv.reader(f))
    header, dati = righe[0], righe[1:]
    nome_cols = [i for i, h in enumerate(header) if h.strip().lower() in ("first name", "given name", "nome", "middle name", "last name", "family name", "cognome", "name")]
    tel_cols = [i for i, h in enumerate(header) if re.search(r"(phone|telefono).*(value|valore)", h.lower())]
    if not nome_cols or not tel_cols:
        return print("Non riconosco le colonne del file: va bene l'esportazione CSV di Google Contatti.")
    rubrica = whatsapp._carica_manuale()
    nuovi = saltati = 0
    for r in dati:
        nome = " ".join(r[i].strip() for i in nome_cols if i < len(r) and r[i].strip())[:40]
        numeri = [n for i in tel_cols if i < len(r) for n in r[i].split(":::")]
        scelto = None
        for n in numeri:  # preferisce un cellulare
            try:
                v = whatsapp._numero(n)
            except whatsapp.WhatsAppError:
                continue
            if v.startswith("393") or scelto is None:
                scelto = v
            if v.startswith("393"):
                break
        if nome and scelto:
            rubrica[nome] = scelto
            nuovi += 1
        else:
            saltati += 1
    whatsapp.RUBRICA.parent.mkdir(parents=True, exist_ok=True)
    whatsapp.RUBRICA.write_text(json.dumps(rubrica, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Importati {nuovi} contatti (saltati {saltati} senza nome o senza numero valido). La rubrica resta solo sul tuo PC.")


main()
