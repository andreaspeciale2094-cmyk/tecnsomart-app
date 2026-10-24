"""Seconda prova Trenord: fa una MAPPA di cosa c'e' nella pagina del tabellone (campi, pulsanti, schede), prova la ricerca delle stazioni direttamente
e poi prova a cercare Gaggiano come farebbe una persona, salvando tutte le risposte vere del sito. Mostra solo orari e indirizzi pubblici del sito.
Uso: .venv\\Scripts\\python.exe scripts\\scopri_trenord2.py [stazione]"""
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

RUMORE = ("analytics", "google", "pinterest", "linkedin", "bing", "twitter", "iubenda", "lpsnmedia", "liveperson", "doubleclick", "facebook", "clarity", "hotjar", "tiktok", "yext")
CARTELLA.mkdir(exist_ok=True)
RISPOSTE = CARTELLA / "trenord_risposte2"
RISPOSTE.mkdir(exist_ok=True)
for f in RISPOSTE.glob("*.txt"):
    f.unlink()
chiamate = []
mappa = []

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
    pag = b.new_page(viewport={"width": 1400, "height": 1200}, locale="it-IT")

    def _risposta(r):
        if any(x in r.url for x in RUMORE) or "trenord.it" not in r.url:
            return
        if r.request.resource_type not in ("xhr", "fetch", "document"):
            return
        chiamate.append((r.status, r.request.method, r.url))
        try:
            (RISPOSTE / f"{len(chiamate):02d}.txt").write_text(f"{r.request.method} {r.url}\n\n" + r.text()[:30000], encoding="utf-8")
        except Exception:
            pass
    pag.on("response", _risposta)
    pag.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pag.wait_for_timeout(5000)
    for testo in ("Accetta tutti", "Accetta tutto", "Accetto", "Accetta"):
        try:
            pag.get_by_role("button", name=re.compile(testo, re.I)).first.click(timeout=1500)
            break
        except Exception:
            pass
    pag.wait_for_timeout(1500)
    mappa.append("TITOLO PAGINA: " + pag.title() + "  |  indirizzo: " + pag.url)
    mappa.append("\n--- CAMPI VISIBILI ---")
    for el in pag.locator("input, select, textarea").all():
        try:
            if el.is_visible():
                mappa.append(f"campo id={el.get_attribute('id')} name={el.get_attribute('name')} tipo={el.get_attribute('type')} segnaposto={el.get_attribute('placeholder')}")
        except Exception:
            pass
    mappa.append("\n--- PULSANTI E SCHEDE VISIBILI ---")
    for el in pag.locator("button, [role=tab], a[role=button], summary").all()[:200]:
        try:
            if el.is_visible():
                t = (el.inner_text() or "").strip().replace("\n", " ")[:60]
                if t:
                    mappa.append(f"{(el.get_attribute('role') or el.evaluate('e => e.tagName')).lower()}: {t}")
        except Exception:
            pass
    mappa.append("\n--- PARTI DELLA PAGINA CON 'tempo reale', 'stazione', 'treno' ---")
    for r in [x.strip() for x in pag.inner_text("body").splitlines() if re.search(r"stazione|treno|tempo reale|partenz|arriv", x, re.I)][:30]:
        mappa.append(r[:110])

    # ricerca delle stazioni chiamata direttamente
    mappa.append("\n--- PROVA DIRETTA: elenco stazioni ---")
    for tmpl in ("discovery", "carnet-partenza"):
        try:
            r = pag.request.get(f"https://www.trenord.it/rest/render/stationslist?query={stazione}&template={tmpl}")
            mappa.append(f"{tmpl}: stato {r.status}: " + r.text()[:700].replace("\n", " "))
        except Exception as e:
            mappa.append(f"{tmpl}: errore {str(e)[:100]}")

    # ricerca come una persona
    pag.screenshot(path=str(CARTELLA / "trenord2_prima.png"), full_page=True)
    try:  # la ricerca per stazione sta nella scheda "ARRIVI E PARTENZE" (non nella ricerca in alto del sito)
        pag.get_by_text(re.compile("^\\s*arrivi e partenze\\s*$", re.I)).first.click(timeout=4000)
        mappa.append("\nCliccato sulla scheda: ARRIVI E PARTENZE")
    except Exception as e:
        mappa.append("\nNon riesco a cliccare su ARRIVI E PARTENZE: " + str(e)[:100])
    pag.wait_for_timeout(2500)
    mappa.append("\n--- CAMPI VISIBILI DOPO LA SCHEDA ARRIVI E PARTENZE ---")
    campo = None
    for el in pag.locator("input").all():
        try:
            if not el.is_visible() or (el.get_attribute("type") or "text") not in ("text", "search"):
                continue
            sp = (el.get_attribute("placeholder") or "")
            mappa.append(f"campo id={el.get_attribute('id')} segnaposto={sp}")
            if campo is None and not re.fullmatch(r"\s*cerca\W*", sp, re.I):  # non la ricerca generale in alto ("Cerca...")
                campo = el
        except Exception:
            pass
    if campo is None:
        mappa.append("Non trovo un campo di testo visibile dopo il clic.")
    else:
        try:
            campo.click(timeout=4000)
            campo.type(stazione, delay=120)
            pag.wait_for_timeout(2500)
            try:
                pag.get_by_text(re.compile("^" + stazione, re.I)).first.click(timeout=3000)
            except Exception:
                pag.keyboard.press("ArrowDown")
                pag.keyboard.press("Enter")
            pag.wait_for_timeout(1500)
            for tasto in ("Cerca", "Mostra", "Visualizza", "Vai", "Invia"):
                try:
                    pag.get_by_role("button", name=re.compile("^" + tasto, re.I)).first.click(timeout=1500)
                    mappa.append(f"Premuto il pulsante: {tasto}")
                    break
                except Exception:
                    pass
            pag.wait_for_timeout(12000)
        except Exception as e:
            mappa.append("Non sono riuscito a scrivere nel campo: " + str(e)[:150])
    testo = pag.inner_text("body")
    (CARTELLA / "trenord2_pagina.txt").write_text(testo, encoding="utf-8")
    pag.screenshot(path=str(CARTELLA / "trenord2_dopo.png"), full_page=True)
    b.close()

(CARTELLA / "trenord2_mappa.txt").write_text("\n".join(mappa), encoding="utf-8")
print("\n".join(mappa[:80]))
print("\n=== Richieste fatte al sito Trenord ===")
for st, m, u in chiamate[-25:]:
    print(st, m, u[:170])
print("\n=== Righe con un orario ===")
for r in [x.strip() for x in testo.splitlines() if re.search(r"\b\d{1,2}[:.]\d{2}\b", x)][:30]:
    print(r[:150])
print("\nSalvati in memoria\\: trenord2_mappa.txt, trenord2_prima.png, trenord2_dopo.png, trenord2_pagina.txt e la cartella trenord_risposte2")
