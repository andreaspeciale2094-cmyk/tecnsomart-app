"""Memoria viva: un file piccolo (memoria/viva.md) sempre letto da Jarvis a ogni richiesta.
Contiene solo l'essenziale e duraturo: chi e' Andrea, regole, orari, persone importanti.
Tutto il resto sta nell'archivio (memory.py), cercato solo quando serve. Il file e' di testo: Andrea lo puo' leggere e correggere."""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
CORE_DIR = ROOT / "memoria"
CORE_FILE = CORE_DIR / "viva.md"
TEMPLATE = ROOT / "docs" / "memoria_viva_esempio.md"
MAX_CHARS = 3000      # il file deve restare piccolo: viene letto a ogni richiesta
MAX_LINE = 220


def _ensure() -> None:
    CORE_DIR.mkdir(exist_ok=True)
    if not CORE_FILE.exists():
        if TEMPLATE.exists():
            shutil.copy(TEMPLATE, CORE_FILE)
        else:
            CORE_FILE.write_text("# Memoria viva di Jarvis (sempre letta)\n", encoding="utf-8")


def read() -> str:
    _ensure()
    return CORE_FILE.read_text(encoding="utf-8").strip()


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def numbered() -> list[tuple[int, str]]:
    """Le righe-ricordo (quelle che iniziano con '- '), numerate 1, 2, 3..."""
    return [(i + 1, l[2:].strip()) for i, l in enumerate([l for l in read().splitlines() if l.startswith("- ")])]


def add(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return "Niente da salvare."
    if len(text) > MAX_LINE:
        return f"Troppo lungo ({len(text)} caratteri, massimo {MAX_LINE}): riassumilo in una riga."
    if any(_norm(t) == _norm(text) for _, t in numbered()):
        return "Lo sapevo gia'."
    if len(read()) + len(text) + 3 > MAX_CHARS:
        return "La memoria viva e' piena: togli qualcosa che non serve piu' (core_remove) oppure usa `remember` per l'archivio."
    with open(CORE_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n- {text}")
    return "Aggiunto alla memoria viva."


def remove(number: int) -> str:
    lines = read().splitlines()
    bullets = [i for i, l in enumerate(lines) if l.startswith("- ")]
    if not 1 <= number <= len(bullets):
        return "Numero non valido."
    removed = lines.pop(bullets[number - 1])
    CORE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"Tolto dalla memoria viva: {removed[2:].strip()}"
