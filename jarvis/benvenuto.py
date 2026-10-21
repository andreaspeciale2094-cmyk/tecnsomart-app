"""Saluto quando torni al PC: la prima volta del giorno 'Buongiorno Andrea' (o 'Buonasera' dopo le 18),
le volte dopo 'Bentornato Andrea'. Capisce che sei tornato quando accendi il PC o quando si risveglia dallo standby (opzionale: anche dopo
BENVENUTO_ASSENZA secondi di PC fermo, spento di default). Il giorno cambia alle 5 del mattino.
Ricorda solo la data dell'ultimo saluto (memoria/benvenuto.json)."""
import json
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import ascolto, config, fase, logs

STATO = Path(__file__).parent.parent / "memoria" / "benvenuto.json"
PAUSA_MIN = 60  # secondi: mai due saluti ravvicinati


def _carica() -> dict:
    try:
        return json.loads(STATO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _salva(d: dict):
    try:
        STATO.parent.mkdir(parents=True, exist_ok=True)
        STATO.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def giorno_di(adesso: datetime) -> str:
    return (adesso - timedelta(hours=5)).date().isoformat()  # il "giorno" comincia alle 5


def frase(adesso: datetime, stato: dict) -> str:
    nome = f" {config.USER_NAME}" if config.USER_NAME else ""
    if stato.get("giorno") != giorno_di(adesso):
        return f"{'Buongiorno' if 5 <= adesso.hour < 18 else 'Buonasera'}{nome}."
    return f"Bentornato{nome}."


def secondi_di_inattivita() -> float:
    """Da quanto tempo non tocchi mouse o tastiera (solo Windows)."""
    if sys.platform != "win32":
        return 0.0
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    return ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


def saluta(adesso: datetime | None = None, parla=None):
    adesso = adesso or datetime.now(ZoneInfo(config.FUSO))
    stato = _carica()
    testo = frase(adesso, stato)
    _salva({"giorno": giorno_di(adesso), "ultimo": time.time()})
    fase.imposta("rispondo")
    (parla or ascolto.parla)(testo)
    fase.imposta("")
    logs.log_azione("BENVENUTO: saluto detto")


def ciclo(idle=secondi_di_inattivita, dormi=time.sleep, adesso=time.time, parla=None, ripetizioni=None):
    """Controlla ogni 3 secondi. Ritorno = sveglia dallo standby, oppure uso di nuovo il PC dopo un'assenza."""
    dormi(8)  # Jarvis deve essere pronto
    ultimo_saluto = _carica().get("ultimo", 0.0)
    if adesso() - ultimo_saluto > 30 * 60:  # appena acceso il PC (o Jarvis): saluta
        saluta(parla=parla)
        ultimo_saluto = adesso()
    prima, assente, n = adesso(), False, 0
    while ripetizioni is None or n < ripetizioni:
        n += 1
        dormi(3)
        t = adesso()
        salto = t - prima - 3
        prima = t
        i = idle()
        ritorno = False
        if salto > 45:  # il PC e' stato in standby
            ritorno, assente = True, False
        elif config.BENVENUTO_ASSENZA and i >= config.BENVENUTO_ASSENZA:
            assente = True
        elif config.BENVENUTO_ASSENZA and assente and i < 6:
            ritorno, assente = True, False
        if ritorno and t - ultimo_saluto > PAUSA_MIN:
            try:
                saluta(parla=parla)
            except Exception as e:
                logs.log_error(e, "benvenuto")
            ultimo_saluto = t


def avvia():
    if config.ENABLE_BENVENUTO:
        threading.Thread(target=ciclo, daemon=True).start()
