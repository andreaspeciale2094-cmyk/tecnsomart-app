"""Prima prova: apre (senza finestre) il tabellone in tempo reale del sito Trenord, cerca la stazione e salva cosa vede, cosi' si capisce
come leggerlo. Mostra solo orari dei treni e indirizzi pubblici del sito: niente di personale.
Uso: .venv\\Scripts\\python.exe scripts\\scopri_trenord.py [stazione]"""
import re
import sys
from pathlib import Path

CARTELLA = Path(__file__).parent.parent / "memoria"
URL = "https://www.trenord.it/linee-e-orari/circolazione/tempo-reale/"
stazione = sys.argv[1] if len(sys.argv) > 1 else "Gaggiano"

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Manca il programma: fai doppio clic su installa_trenord.bat e riprova.")

chiamate = []
CARTELLA.mkdir(exist_ok=True)
with sync_playwright() as p:
    b = None
    for canale in ("chrome", "msedge"):
        try:
            b = p.chromium.launch(channel=canale, headless=True)
            break
        except Exception as e:
            ultimo = e
    if b is None:
        sys.exit(f"Non riesco ad aprire Chrome o Edge in modo invisibile: {str(ultimo)[:150]}")
    pag = b.new_page(viewport={"width": 1280, "height": 1100}, locale="it-IT")
    pag.on("response", lambda r: chiamate.append((r.status, r.url)) if r.request.resource_type in ("xhr", "fetch") else None)
    pag.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pag.wait_for_timeout(4000)
    for testo in ("Accetta tutti", "Accetta tutto", "Accetto", "Accetta"):
        try:
            pag.get_by_role("button", name=re.compile(testo, re.I)).first.click(timeout=1500)
            break
        except Exception:
            pass
    for etichetta in ("Cerca stazione", "Stazione"):
        try:
            pag.get_by_text(re.compile(etichetta, re.I)).first.click(timeout=3000)
            break
        except Exception:
            pass
    campo = None
    for sel in ("input[placeholder*='tazione' i]", "input[aria-label*='tazione' i]", "input[type='search']", "input[type='text']"):
        loc = pag.locator(sel)
        if loc.count():
            campo = loc.first
            break
    if campo is None:
        print("Non trovo il campo della stazione nella pagina.")
    else:
        campo.click()
        campo.fill(stazione)
        pag.wait_for_timeout(2500)
        try:
            pag.get_by_text(re.compile(stazione, re.I)).nth(1).click(timeout=3000)
        except Exception:
            pag.keyboard.press("ArrowDown")
            pag.keyboard.press("Enter")
        pag.wait_for_timeout(6000)
    testo = pag.inner_text("body")
    (CARTELLA / "trenord_pagina.txt").write_text(testo, encoding="utf-8")
    pag.screenshot(path=str(CARTELLA / "trenord_pagina.png"), full_page=True)
    b.close()

print("=== Indirizzi chiamati dalla pagina (xhr/fetch) ===")
for stato, u in chiamate[-25:]:
    print(stato, u[:200])
print("\n=== Righe della pagina con un orario ===")
righe = [r.strip() for r in testo.splitlines() if re.search(r"\b\d{1,2}[:.]\d{2}\b", r)]
for r in righe[:40]:
    print(r[:160])
print("\nSalvati: memoria\\trenord_pagina.txt e memoria\\trenord_pagina.png")
