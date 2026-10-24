"""Siti e webapp fatti da Jarvis: i file stanno SOLO sul PC in memoria/siti/<nome>. Si vedono in anteprima da questo PC.
Niente si cancella (le versioni vecchie vanno in memoria/_da_eliminare/siti) e niente va online da qui."""
import re
import shutil
import time
from pathlib import Path

from . import logs

BASE = Path(__file__).parent.parent / "memoria" / "siti"
SCARTO = Path(__file__).parent.parent / "memoria" / "_da_eliminare" / "siti"
ESTENSIONI = {".html", ".css", ".js", ".json", ".svg", ".txt", ".md", ".webmanifest", ".gs", ".xml", ".csv"}
MAX_FILE, MAX_TOTALE, MAX_NUMERO = 400_000, 2_000_000, 40
# chiavi e segreti non devono mai finire dentro un sito (i siti sono pubblici)
SEGRETI = re.compile(r"sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY|\b\d{9,10}:[A-Za-z0-9_-]{30,}\b|gsk_[A-Za-z0-9]{20,}", re.IGNORECASE)
_NOME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class SitoError(Exception):
    pass


def _nome(nome: str) -> str:
    n = (nome or "").strip().lower().replace(" ", "-").replace("_", "-")
    if not _NOME.match(n):
        raise SitoError("Il nome del sito deve avere solo lettere, numeri e trattini (massimo 40).")
    return n


def _percorso(cartella: Path, rel: str) -> Path:
    r = (rel or "").replace("\\", "/").strip().lstrip("/")
    p = (cartella / r).resolve()
    if not r or cartella.resolve() not in p.parents or any(x.startswith(".") for x in Path(r).parts):
        raise SitoError(f"Percorso non valido: {rel}")
    if p.suffix.lower() not in ESTENSIONI:
        raise SitoError(f"Tipo di file non permesso: {p.suffix or rel}")
    return p


def elenco() -> str:
    if not BASE.exists():
        return "Non ci sono ancora siti."
    righe = []
    for c in sorted(BASE.iterdir()):
        if c.is_dir():
            n = sum(1 for f in c.rglob("*") if f.is_file())
            righe.append(f"- {c.name} ({n} file)")
    return "Siti sul PC:\n" + "\n".join(righe) if righe else "Non ci sono ancora siti."


def leggi(nome: str, percorso: str = "") -> str:
    c = BASE / _nome(nome)
    if not c.is_dir():
        raise SitoError("Questo sito non esiste.")
    if not percorso:
        return "File del sito:\n" + "\n".join(f"- {f.relative_to(c).as_posix()} ({f.stat().st_size} byte)" for f in sorted(c.rglob("*")) if f.is_file())
    p = _percorso(c, percorso)
    if not p.is_file():
        raise SitoError("Questo file non esiste.")
    return p.read_text(encoding="utf-8", errors="replace")


def scrivi(nome: str, file: list[dict]) -> str:
    """Crea o aggiorna i file di un sito. Se un file c'era gia', la versione vecchia va in _da_eliminare."""
    n = _nome(nome)
    if not file or len(file) > MAX_NUMERO:
        raise SitoError(f"Servono da 1 a {MAX_NUMERO} file.")
    c = BASE / n
    pronti, totale = [], 0
    for f in file:
        testo = f.get("contenuto")
        if not isinstance(testo, str):
            raise SitoError("Ogni file ha bisogno del suo contenuto.")
        p = _percorso(c, f.get("percorso", ""))
        dim = len(testo.encode("utf-8"))
        totale += dim
        if dim > MAX_FILE or totale > MAX_TOTALE:
            raise SitoError("File troppo grande: spezzalo in piu' file.")
        if SEGRETI.search(testo):
            raise SitoError("Dentro il file c'e' qualcosa che sembra una chiave o una password: i siti sono pubblici, non va mai scritta li'. Non salvo nulla.")
        pronti.append((p, testo))
    c.mkdir(parents=True, exist_ok=True)
    adesso = time.strftime("%Y%m%d-%H%M%S")
    for p, testo in pronti:
        if p.exists():
            vecchio = SCARTO / f"{n}-{adesso}" / p.relative_to(c)
            vecchio.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, vecchio)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(testo, encoding="utf-8")
    logs.log_route(f"SITI: {len(pronti)} file scritti (sito {n})")
    return f"Fatto: {len(pronti)} file nel sito '{n}'. Anteprima: /anteprima/{n}/ (dal pulsante o dicendo 'fammi vedere il sito')."


def cartella_anteprima(nome: str) -> Path:
    c = BASE / _nome(nome)
    if not c.is_dir():
        raise SitoError("Questo sito non esiste.")
    return c


def file_anteprima(nome: str, rel: str) -> Path | None:
    """Il file da mostrare in anteprima (solo dentro la cartella del sito). Percorso vuoto = index.html."""
    c = cartella_anteprima(nome)
    rel = rel or "index.html"
    if rel.endswith("/"):
        rel += "index.html"
    r = rel.replace("\\", "/").lstrip("/")
    p = (c / r).resolve()
    if c.resolve() not in p.parents or any(x.startswith(".") for x in Path(r).parts):
        return None
    if p.is_dir():
        p = p / "index.html"
    return p if p.is_file() and p.suffix.lower() in ESTENSIONI else None


def anteprima(nome: str) -> str:
    """Apre l'anteprima nel browser di questo PC."""
    import webbrowser
    n = _nome(nome)
    cartella_anteprima(n)
    webbrowser.open(f"http://localhost:8000/anteprima/{n}/")
    return f"Ho aperto l'anteprima del sito '{n}' nel browser."
