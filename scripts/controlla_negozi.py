"""Controlla il collegamento con l'app dei negozi, in 3 passi: file dei target, chiave, risposta dell'app.
Non mostra mai la chiave. Uso: .venv\\Scripts\\python.exe scripts\\controlla_negozi.py"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import config, negozi  # noqa: E402


def main():
    print("1. File dei target (memoria\\negozi.json)...")
    try:
        cfg = negozi.load_config()
    except negozi.NegoziError as e:
        return print("   ERRORE:", e)
    if not str(cfg.get("url", "")).startswith("https://script.google.com/"):
        return print("   ERRORE: nel file manca l'indirizzo dell'app (campo \"url\", deve iniziare con https://script.google.com/).")
    print("   OK:", ", ".join(k for k in cfg.get("run", {})), "| mesi con target:", sorted({m for r in cfg["run"].values() for m in r.get("mesi", {})}))
    print("2. Chiave TECNOSMART_TOKEN nel file .env...", "OK (presente)" if config.TECNOSMART_TOKEN else "MANCA")
    if not config.TECNOSMART_TOKEN:
        return
    print("3. Chiedo all'app il riepilogo di oggi...")
    try:
        raw = negozi.fetch(cfg["url"], date.today().isoformat())
    except negozi.NegoziError as e:
        return print("   ERRORE:", e)
    for kind in ("mono", "multi"):
        print(f"   {kind}: {len(raw.get(kind) or {})} negozi con dati nel mese")
    print("\nTUTTO OK: Jarvis puo' leggere i negozi. Prova a dirgli: 'fammi il riepilogo serale dei negozi'.")


main()
