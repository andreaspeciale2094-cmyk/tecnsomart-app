"""Promemoria a voce: 'ricordami alle 17 di chiamare Marco'. Restano in memoria/promemoria.json sul PC (solo il testo che dice Andrea) e si cancellano appena detti.
Li controlla il vigile ogni minuto: a voce se Jarvis e' libero, altrimenti una scheda sulla pagina. Nei registri solo 'promemoria creato/detto', mai il testo."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, logs

FILE = Path(__file__).parent.parent / "memoria" / "promemoria.json"
_lock = threading.Lock()


class PromemoriaError(Exception):
    pass


def _adesso() -> datetime:
    return datetime.now(ZoneInfo(config.FUSO))


def _carica() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []
    except (OSError, ValueError):
        return []


def _salva(lista: list[dict]):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")


def crea(testo: str, ora: str = "", giorno: str = "", tra_minuti: int = 0) -> str:
    testo = (testo or "").strip()[:300]
    if not testo:
        raise PromemoriaError("Dimmi cosa devo ricordarti.")
    adesso = _adesso()
    if tra_minuti and int(tra_minuti) > 0:
        quando = adesso + timedelta(minutes=int(tra_minuti))
    else:
        try:
            h, m = (int(x) for x in ora.replace(".", ":").split(":"))
            g = giorno.strip().lower()
            if g in ("domani", "tomorrow"):
                data = (adesso + timedelta(days=1)).date()
            elif len(g) == 10 and g[4] == "-":
                data = datetime.strptime(g, "%Y-%m-%d").date()
            else:
                data = adesso.date()
            quando = datetime(data.year, data.month, data.day, h, m, tzinfo=adesso.tzinfo)
            if quando <= adesso and not g:  # 'alle 9' detto alle 15 senza giorno: e' domani
                quando += timedelta(days=1)
        except (ValueError, AttributeError):
            raise PromemoriaError("Non ho capito l'ora: dimmela cosi', per esempio 'alle 17 e 30' oppure 'tra 20 minuti'.")
    if quando <= adesso:
        raise PromemoriaError("Quell'ora e' gia' passata.")
    with _lock:
        lista = _carica()
        lista.append({"id": uuid.uuid4().hex[:8], "quando": quando.isoformat(), "testo": testo})
        _salva(lista[-50:])
    logs.log_route("PROMEMORIA: creato")
    giorni = (quando.date() - adesso.date()).days
    return f"Ok, ti ricordo {'oggi' if giorni == 0 else 'domani' if giorni == 1 else quando.strftime('%d/%m')} alle {quando.strftime('%H:%M')}: {testo}"


def elenco() -> str:
    with _lock:
        lista = sorted(_carica(), key=lambda p: p["quando"])
    if not lista:
        return "Non hai promemoria in attesa."
    return "\n".join(f"- {p['id']}: {datetime.fromisoformat(p['quando']).strftime('%d/%m %H:%M')} {p['testo']}" for p in lista)


def togli(id_o_testo: str) -> str:
    chiave = (id_o_testo or "").strip().lower()
    with _lock:
        lista = _carica()
        resto = [p for p in lista if p["id"] != chiave and chiave not in p["testo"].lower()] if chiave else lista
        if chiave == "tutti":
            resto = []
        _salva(resto)
    n = len(lista) - len(resto)
    return f"Tolti {n} promemoria." if n else "Non trovo quel promemoria."


def scaduti() -> list[dict]:
    """I promemoria arrivati all'ora (non ancora detti)."""
    adesso = _adesso()
    with _lock:
        return [p for p in _carica() if datetime.fromisoformat(p["quando"]) <= adesso]


def fatto(id_: str):
    with _lock:
        _salva([p for p in _carica() if p["id"] != id_])
