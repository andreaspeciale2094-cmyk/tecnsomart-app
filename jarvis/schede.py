"""Schede dei ragazzi: un file di testo per ragazzo in memoria/schede/ (solo sul PC di Andrea, mai su GitHub).
Ogni riga ha la data. Non c'e' cancellazione definitiva: una scheda tolta va in memoria/_da_eliminare/.
Il contenuto non viene scritto nei registri ne' nella memoria viva o nell'archivio."""
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent / "memoria"
CARTELLA = ROOT / "schede"
SEZIONI = {
    "va_bene": "Cosa va bene",
    "debole": "Punti deboli",
    "provato": "Cosa e' gia' stato provato",
    "esito": "Com'e' andata dopo",
}


class SchedaError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _slug(nome: str) -> str:
    t = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _file(nome: str) -> Path:
    s = _slug(nome)
    if not s:
        raise SchedaError("Dimmi il nome del ragazzo.")
    return CARTELLA / f"{s}.md"


def _cerca(nome: str) -> Path | None:
    """Trova la scheda anche con il nome scritto in modo un po' diverso, se e' una sola."""
    if not CARTELLA.exists() or not _slug(nome):
        return None
    s = _slug(nome)
    esatta = CARTELLA / f"{s}.md"
    if esatta.exists():
        return esatta
    simili = [f for f in CARTELLA.glob("*.md") if s in f.stem or f.stem in s]
    return simili[0] if len(simili) == 1 else None


def leggi(nome: str) -> str | None:
    f = _cerca(nome)
    return f.read_text(encoding="utf-8") if f else None


def elenco() -> list[str]:
    return sorted(f.stem for f in CARTELLA.glob("*.md")) if CARTELLA.exists() else []


def aggiungi(nome: str, sezione: str, testo: str) -> str:
    if sezione not in SEZIONI:
        raise SchedaError("La sezione deve essere una di: " + ", ".join(SEZIONI))
    testo = " ".join(testo.split())
    if not testo:
        raise SchedaError("Manca il testo da scrivere.")
    f = _cerca(nome) or _file(nome)
    CARTELLA.mkdir(parents=True, exist_ok=True)
    if f.exists():
        righe = f.read_text(encoding="utf-8").splitlines()
    else:
        righe = [f"# {nome.strip().title()}"] + [x for s in SEZIONI.values() for x in ("", f"## {s}")]
    titolo = f"## {SEZIONI[sezione]}"
    if titolo not in righe:
        righe += ["", titolo]
    i = righe.index(titolo) + 1
    while i < len(righe) and not righe[i].startswith("## "):
        i += 1
    while i > 0 and not righe[i - 1].strip():
        i -= 1
    righe.insert(i, f"- {date.today().isoformat()}: {testo}")
    f.write_text("\n".join(righe).rstrip() + "\n", encoding="utf-8")
    return f"Scritto nella scheda di {nome.strip().title()}, sezione '{SEZIONI[sezione]}'."


def togli(nome: str) -> str:
    """Sposta la scheda in memoria/_da_eliminare (mai cancellazione definitiva)."""
    f = _cerca(nome)
    if not f:
        raise SchedaError(f"Non trovo una scheda per '{nome}'.")
    dest = ROOT / "_da_eliminare"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(f), str(dest / f"{f.stem}-{date.today().isoformat()}.md"))
    return "Scheda spostata in memoria\\_da_eliminare (non e' cancellata: puoi recuperarla)."
