"""Salute di Jarvis e guardiano dei consumi (nessun modello, costo zero): ogni 5 minuti controlla che le sue parti funzionino.
Ripara da solo SOLO cio' che e' suo e sicuro (riaccendere il programma di WhatsApp, l'ascolto, rifare la sincronizzazione della rubrica), al massimo 3 tentativi
all'ora; il resto (WhatsApp da ricollegare, permesso della banca, chiavi, errori) lo dice con una scheda. Non tocca Windows, non cancella niente, non modifica il codice.
Nei registri solo etichette ('SALUTE: ...'), mai testi privati. I consumi sono una STIMA (i prezzi sono quelli del cervello, quindi per eccesso)."""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, logs

RADICE = Path(__file__).parent.parent
OGNI = 300
_avvisati: dict[str, float] = {}
_tentativi: dict[str, list[float]] = {}
_visto = {"mic_da": 0.0}
_t0 = time.time()


def _avvisa(chiave: str, testo: str, ore: float = 6):
    """Una scheda 'salute' sulla pagina, non piu' di una ogni `ore` ore per lo stesso problema."""
    adesso = time.time()
    if adesso - _avvisati.get(chiave, 0) < ore * 3600:
        return False
    _avvisati[chiave] = adesso
    from . import vigile
    vigile._aggiungi("salute", testo, True)
    logs.log_route(f"SALUTE: avviso '{chiave}'")
    return True


_ETICHETTE = {"whatsapp_programma": "il programma di WhatsApp", "ascolto_programma": "l'ascolto", "rubrica": "l'aggiornamento della rubrica"}


def _prova(chiave: str, azione) -> bool:
    """Tenta una riparazione sicura, al massimo 3 volte all'ora. True se l'ha provata (anche se non e' detto che sia riuscita)."""
    adesso = time.time()
    t = [x for x in _tentativi.get(chiave, []) if adesso - x < 3600]
    if len(t) >= 3:
        _tentativi[chiave] = t
        return False
    t.append(adesso)
    _tentativi[chiave] = t
    try:
        azione()
        logs.log_route(f"SALUTE: provato a riparare '{chiave}'")
        from . import vigile
        with vigile._lock:
            vigile._diario.append((datetime.now(ZoneInfo(config.FUSO)).strftime("%H:%M"), "salute", f"ho riparato da solo: {_ETICHETTE.get(chiave, chiave)}"))
    except Exception as e:
        logs.log_route(f"SALUTE: riparazione '{chiave}' non riuscita ({type(e).__name__})")
    return True


def _whatsapp():
    if not (config.ENABLE_WHATSAPP and config.ENABLE_WHATSAPP_LEGGI):
        return
    from . import whatsapp
    st = whatsapp._stato()
    if st is None:
        if _prova("whatsapp_programma", whatsapp._avvia_helper):
            return
        _avvisa("whatsapp_programma", "Il programma di WhatsApp non riparte da solo: riavvia Jarvis. Se resta cosi', dimmelo.")
    elif st.get("bisogna_qr"):
        _avvisa("whatsapp_qr", "WhatsApp si e' scollegato dal telefono: va ricollegato con ricollega_whatsapp.bat (scansioni il codice).", 12)
    elif st.get("bloccato"):
        _avvisa("whatsapp_bloccato", "WhatsApp ha bloccato il collegamento di Jarvis: non insistere, dimmelo e vediamo.", 12)


def _ascolto():
    if not config.ENABLE_ASCOLTO:
        return
    from . import ascolto
    if not ascolto.stato.get("attivo"):
        _visto["mic_da"] = 0.0
        return
    th = getattr(ascolto, "_thread", None)
    if th is not None and not th.is_alive():
        if _prova("ascolto_programma", ascolto.avvia):
            return
        _avvisa("ascolto_programma", "L'ascolto si e' fermato e non riparte: riavvia Jarvis.")
        return
    if ascolto.stato.get("in_ascolto"):
        _visto["mic_da"] = 0.0
    else:
        _visto["mic_da"] = _visto["mic_da"] or time.time()
        if time.time() - _visto["mic_da"] > 600:
            _avvisa("ascolto_microfono", "Il microfono dell'ascolto non si apre da 10 minuti: controlla le cuffie o scegli un altro microfono dalla finestra sotto la scritta.", 6)


def _rubrica():
    from . import rubrica_sync
    if not rubrica_sync.configurata() or not rubrica_sync._stato["ultima"]:
        return
    if time.time() - rubrica_sync._stato["ultima"] > 7 * 3600:
        if _prova("rubrica", rubrica_sync.sincronizza):
            return
        _avvisa("rubrica", "La rubrica non si aggiorna dai contatti Google da piu' di 7 ore.", 24)


def _banca():
    if not config.ENABLE_BANCA:
        return
    try:
        scade = json.loads((RADICE / "memoria" / "banca" / "sessione.json").read_text(encoding="utf-8")).get("scade", "")
        giorni = (date.fromisoformat(scade) - date.today()).days if scade else None
    except (OSError, ValueError):
        return
    if giorni is None:
        return
    if giorni < 0:
        _avvisa("banca_scaduta", "Il permesso della banca e' scaduto: va rinnovato con scripts\\collega_banca.py (un minuto, con l'app della banca).", 24)
    elif giorni <= 7:
        _avvisa("banca_scade", f"Il permesso della banca scade tra {giorni} giorni: rinnovalo con scripts\\collega_banca.py.", 24)


def _errori():
    f = RADICE / "logs" / "errori.log"
    try:
        if not f.exists():
            return
        righe = f.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return
    limite = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    recenti = [r for r in righe if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", r) and r[:19] >= limite]
    if len(recenti) > 30:
        _avvisa("errori", f"Ci sono {len(recenti)} errori nell'ultima ora nel registro: qualcosa non va, dimmelo e guardiamo.", 6)


def _disco():
    try:
        libero = shutil.disk_usage(RADICE).free
    except OSError:
        return
    if libero < 1_000_000_000:
        _avvisa("disco", "Il disco del PC e' quasi pieno (meno di 1 giga libero).", 24)


def spesa_del_mese() -> float:
    """Somma dei costi stimati nel registro dei consumi per il mese in corso."""
    f = RADICE / "logs" / "consumi.log"
    mese = date.today().strftime("%Y-%m")
    tot = 0.0
    try:
        for r in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if r.startswith(mese):
                m = re.search(r"costo stimato \$([0-9.]+)", r)
                if m:
                    tot += float(m.group(1))
    except OSError:
        pass
    return tot


def _consumi():
    tetto = float(config.TETTO_MENSILE)
    oggi = date.today()
    spesa = spesa_del_mese()
    mese = oggi.strftime("%Y-%m")
    for soglia in (0.5, 0.75, 0.9):
        if spesa >= tetto * soglia:
            _avvisa(f"consumi_{mese}_{int(soglia * 100)}", f"Spesa stimata del mese: {spesa:.2f} dollari, il {int(soglia * 100)}% del tetto di {tetto:g}. (E' una stima per eccesso: il conto vero e' nella Console Anthropic.)", 24 * 31)
    if oggi.day >= 5:
        giorni_mese = (date(oggi.year + (oggi.month == 12), oggi.month % 12 + 1, 1) - date(oggi.year, oggi.month, 1)).days
        previsione = spesa / oggi.day * giorni_mese
        if previsione > tetto:
            _avvisa(f"consumi_previsione_{mese}", f"A questo ritmo a fine mese arrivi a circa {previsione:.0f} dollari, sopra il tetto di {tetto:g}. (Stima per eccesso.)", 24 * 7)


def controlla():
    for nome, f in (("whatsapp", _whatsapp), ("ascolto", _ascolto), ("rubrica", _rubrica), ("banca", _banca), ("errori", _errori), ("disco", _disco), ("consumi", _consumi)):
        try:
            f()
        except Exception as e:
            logs.log_error(e, f"salute {nome}")


def _ciclo():
    time.sleep(120)  # prima si lascia partire tutto
    while True:
        controlla()
        time.sleep(OGNI)


def avvia():
    if config.ENABLE_SALUTE:
        threading.Thread(target=_ciclo, daemon=True).start()
