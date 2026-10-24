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
RUMORE = ("analytics", "google", "pinterest", "linkedin", "bing", "twitter", "iubenda", "lpsnmedia", "doubleclick", "facebook", "clarity", "hotjar", "tiktok", "yext")
CARTELLA.mkdir(exist_ok=True)
RISPOSTE = CARTELLA / "trenord_risposte"
RISPOSTE.mkdir(exist_ok=True)
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
    def _risposta(r):
        if r.request.resource_type not in ("xhr", "fetch") or any(x in r.url for x in RUMORE):
            return
        chiamate.append((r.status, r.url))
        try:  # si salva il contenuto delle risposte vere del sito (solo orari e stati dei treni)
            corpo = r.text()
            (RISPOSTE / f"{len(chiamate):02d}.txt").write_text(r.url + "\n\n" + corpo[:20000], encoding="utf-8")
        except Exception:
            pass
    pag.on("response", _risposta)
    pag.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pag.wait_for_timeout(4000)
    for testo in ("Accetta tutti", "Accetta tutto", "Accetto", "Accetta"):
        try:
            pag.get_by_role("button", name=re.compile(testo, re.I)).first.click(timeout=1500)
            break
        except Exception:
            pass
    pag.screenshot(path=str(CARTELLA / "trenord_prima.png"), full_page=True)
    for etichetta in ("Cerca stazione", "Stazione"):
        try:
            pag.get_by_text(re.compile(etichetta, re.I)).first.click(timeout=3000)
            break
        except Exception:
            pass
    campo = None
    for sel in ("input[placeholder*='tazione' i]", "input[aria-label*='tazione' i]", "input[type='search']", "input[type='text']"):
        loc = pag.locator(sel)
        for i in range(loc.count()):
            if loc.nth(i).is_visible():
                campo = loc.nth(i)
                break
        if campo is not None:
            break
    if campo is None:
        print("Non trovo il campo della stazione nella pagina.")
    else:
        try:
            campo.click(timeout=5000)
            campo.fill(stazione)
            pag.wait_for_timeout(2500)
            try:
                pag.get_by_text(re.compile(stazione, re.I)).nth(1).click(timeout=3000)
            except Exception:
                pag.keyboard.press("ArrowDown")
                pag.keyboard.press("Enter")
            pag.wait_for_timeout(12000)
        except Exception as e:
            print("Non sono riuscito a scrivere nel campo:", str(e)[:150])
    testo = pag.inner_text("body")
    (CARTELLA / "trenord_pagina.txt").write_text(testo, encoding="utf-8")
    pag.screenshot(path=str(CARTELLA / "trenord_pagina.png"), full_page=True)
    b.close()

print("=== Indirizzi del sito chiamati dalla pagina (senza pubblicita') ===")
for stato, u in chiamate[-25:]:
    print(stato, u[:200])
print("\n=== Prime righe di testo della pagina ===")
for r in [r.strip() for r in testo.splitlines() if r.strip()][:25]:
    print(r[:120])
print("\n=== Righe della pagina con un orario ===")
righe = [r.strip() for r in testo.splitlines() if re.search(r"\b\d{1,2}[:.]\d{2}\b", r)]
for r in righe[:40]:
    print(r[:160])
print("\nSalvati: memoria\\trenord_pagina.txt, trenord_prima.png, trenord_pagina.png e la cartella memoria\\trenord_risposte")
