"""Apre Chrome (visibile) con il profilo dedicato di Jarvis su Amazon: entri TU con il tuo account (password e verifica in due passaggi li scrivi tu).
Jarvis non vede mai la password. Quando hai finito chiudi la finestra: il login resta nel profilo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Manca il programma: fai doppio clic su installa_trenord.bat e riprova.")
from jarvis import amazon

with sync_playwright() as p:
    ctx = amazon._contesto(p, visibile=True)
    pag = ctx.pages[0] if ctx.pages else ctx.new_page()
    pag.goto(amazon.SITO + "/", wait_until="domcontentloaded")
    print("Nella finestra di Chrome clicca 'Accedi' in alto a destra e entra con il tuo account Amazon (anche la verifica in due passaggi).")
    print("Quando sei dentro CHIUDI la finestra di Chrome.")
    try:
        ctx.wait_for_event("close", timeout=15 * 60 * 1000)
    except Exception:
        pass
    try:
        ctx.close()
    except Exception:
        pass
print("Fatto: il collegamento ad Amazon e' salvato nel profilo di Jarvis.")
