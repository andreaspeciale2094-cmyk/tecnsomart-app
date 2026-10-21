"""Spegne Jarvis con calma: salva le cose che durano e si chiude (funziona anche se e' nascosto). Uso: spegni_jarvis.bat"""
from pathlib import Path

import httpx

TOKEN = Path(__file__).parent.parent / "memoria" / "chiudi.token"


def main():
    try:
        r = httpx.post("http://127.0.0.1:8000/api/chiudi", headers={"x-chiudi": TOKEN.read_text(encoding="utf-8").strip()}, timeout=10)
        print("Jarvis si sta spegnendo." if r.status_code == 200 else "Jarvis ha rifiutato la richiesta.")
    except (OSError, httpx.HTTPError):
        print("Jarvis non risulta acceso.")


main()
