"""Controllo del PC: disattivato di default (JARVIS_PC_CONTROL=true per abilitarlo)."""
import subprocess
from .. import config

_OFF = "Controllo del PC disattivato. Imposta JARVIS_PC_CONTROL=true nel file .env per abilitarlo."

SCHEMAS = [
    {
        "name": "run_shell",
        "description": "Esegue un comando shell nella cartella di lavoro (timeout 60s). Per azioni distruttive chiedi prima conferma all'utente.",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "read_file",
        "description": "Legge un file di testo dalla cartella di lavoro.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Scrive un file di testo nella cartella di lavoro.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
]


def _safe(path: str):
    config.WORKDIR.mkdir(parents=True, exist_ok=True)
    p = (config.WORKDIR / path).resolve()
    if config.WORKDIR not in p.parents and p != config.WORKDIR:
        raise ValueError("Percorso fuori dalla cartella di lavoro")
    return p


def run_shell(command: str) -> str:
    if not config.PC_CONTROL:
        return _OFF
    config.WORKDIR.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(command, shell=True, cwd=config.WORKDIR, capture_output=True, text=True, timeout=60)
    return f"exit={r.returncode}\n{r.stdout}\n{r.stderr}".strip()


def read_file(path: str) -> str:
    return _OFF if not config.PC_CONTROL else _safe(path).read_text()


def write_file(path: str, content: str) -> str:
    if not config.PC_CONTROL:
        return _OFF
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Scritto {p}"


HANDLERS = {"run_shell": run_shell, "read_file": read_file, "write_file": write_file}
