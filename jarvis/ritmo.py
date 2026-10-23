"""Ritmo della voce di Jarvis: misura quanto e' forte la voce momento per momento, cosi' la sfera della pagina si muove a tempo.
Solo numeri (nessun testo, nessun audio salvato): l'mp3 si decodifica in memoria e si butta. Se manca `miniaudio` non succede niente di male:
la sfera usa il ritmo simulato di prima."""
from __future__ import annotations

import threading
import time

from . import config

try:
    import numpy as np
    import miniaudio
except ImportError:
    np = miniaudio = None

DT = 0.02          # un valore ogni 20 millesimi di secondo
_lock = threading.Lock()
_c = {"id": 0, "t0": 0.0, "env": [], "fine": 0.0}


def disponibile() -> bool:
    return miniaudio is not None and np is not None


def inviluppo(mp3: bytes) -> list[float]:
    """Dal file mp3 ricava la forza della voce (0-1) ogni DT secondi. Lista vuota se non riesce."""
    if not disponibile():
        return []
    try:
        d = miniaudio.decode(bytes(mp3), nchannels=1, sample_rate=16000)
        x = np.frombuffer(d.samples, dtype=np.int16).astype(np.float32) / 32768.0
        n = int(16000 * DT)
        pezzi = len(x) // n
        if pezzi < 2:
            return []
        rms = np.sqrt((x[: pezzi * n].reshape(pezzi, n) ** 2).mean(axis=1))
        alto = float(np.percentile(rms, 95)) or 1.0
        v = np.clip(rms / alto, 0.0, 1.0) ** 0.7                 # il parlato e' forte a tratti: si ammorbidisce
        v = np.convolve(v, np.ones(3) / 3, mode="same")            # un po' di morbidezza tra un valore e l'altro
        return [round(float(a), 3) for a in v]
    except Exception:
        return []


def inizia(env: list[float]):
    """Da chiamare nel momento in cui parte l'audio."""
    if not env:
        return
    with _lock:
        _c["id"] += 1
        _c["t0"] = time.time() + config.RITMO_RITARDO  # le cuffie (bluetooth soprattutto) suonano un po' dopo
        _c["env"] = env
        _c["fine"] = _c["t0"] + len(env) * DT + 0.3


def fine():
    with _lock:
        _c["fine"] = 0.0


def stato(visto: int = 0) -> dict:
    """Per la pagina: se sta parlando, a che punto e' la frase, e (solo se e' nuova) la forma della voce."""
    with _lock:
        ora = time.time()
        if not _c["env"] or ora > _c["fine"]:
            return {"parla": False, "id": _c["id"]}
        r = {"parla": True, "id": _c["id"], "t": round(ora - _c["t0"], 3), "dt": DT}
        if visto != _c["id"]:
            r["env"] = _c["env"]
        return r
