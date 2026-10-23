"""Chiamate perse dal telefono: una macro di MacroDroid manda a Jarvis (via Tailscale) il numero di chi ha chiamato; Jarvis lo riconosce in rubrica e lo dice
(scheda sulla pagina, e a voce se e' libero e non e' notte). 'Richiamalo' poi funziona con la solita conferma (chiama_prepara).
Numeri e nomi stanno SOLO in RAM (svuotati a mezzanotte); nei registri solo 'ricevuta', mai numero o nome. Solo informazione: non parte nessuna azione da qui."""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config, logs

_perse: list[dict] = []   # {"numero", "nome", "ts", "volte"}
_lock = threading.Lock()
_ora_richieste: list[float] = []


def _normalizza(numero: str) -> str:
    cifre = re.sub(r"\D", "", numero or "")
    if cifre.startswith("00"):
        cifre = cifre[2:]
    if len(cifre) == 10 and cifre.startswith("3"):
        cifre = "39" + cifre
    return cifre


def _nome(numero: str, nome_telefono: str) -> str:
    try:
        from . import whatsapp
        n = whatsapp._nome_da_rubrica(numero, "")
        if n and n != ("+" + numero):
            return n
    except Exception:
        pass
    return (nome_telefono or "").strip()[:60] or ("+" + numero if numero else "un numero sconosciuto")


def registra(numero: str, nome: str = "") -> str:
    """Una chiamata persa nuova. Ritorna la frase per Andrea (o '' se e' un doppione o troppe richieste)."""
    adesso = time.time()
    with _lock:
        _ora_richieste[:] = [t for t in _ora_richieste if adesso - t < 3600]
        if len(_ora_richieste) >= 40:
            return ""  # troppe richieste in un'ora: qualcosa non va, si ignora
        _ora_richieste.append(adesso)
        num = _normalizza(numero)
        nome_ok = _nome(num, nome)
        for p in _perse:
            if p["numero"] == num and num:
                if adesso - p["ts"] < 45:
                    return ""  # lo stesso squillo segnalato due volte
                p.update(ts=adesso, volte=p["volte"] + 1)
                volte = p["volte"]
                break
        else:
            _perse.append({"numero": num, "nome": nome_ok, "ts": adesso, "volte": 1})
            volte = 1
        del _perse[:-30]
    logs.log_route("CHIAMATE PERSE: ricevuta")
    return f"{nome_ok} ti ha chiamato" + (f" ({volte} volte)." if volte > 1 else ".")


def elenco() -> str:
    with _lock:
        voci = list(_perse)
    if not voci:
        return "Oggi non risultano chiamate perse."
    fuso = ZoneInfo(config.FUSO)
    return "Chiamate perse oggi: " + "; ".join(
        f"{p['nome']} alle {datetime.fromtimestamp(p['ts'], fuso).strftime('%H:%M')}" + (f" ({p['volte']} volte)" if p["volte"] > 1 else "") for p in voci) + "."


def svuota():
    with _lock:
        _perse.clear()
