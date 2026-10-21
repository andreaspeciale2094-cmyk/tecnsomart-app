"""Cosa sta facendo Jarvis adesso (ascolto, pensa, parla), da qualunque canale: serve allo sfondo animato del PC.
Dura pochi secondi se nessuno la rinnova, cosi' non resta mai bloccata. Nessun testo, solo l'etichetta."""
import time

_f = {"fase": "", "t": 0.0}
VALIDE = {"", "ti ascolto", "capisco", "rispondo"}


def imposta(fase: str):
    _f["fase"], _f["t"] = (fase if fase in VALIDE else ""), time.time()


def leggi(durata: float = 4.0) -> str:
    return _f["fase"] if time.time() - _f["t"] < durata else ""
