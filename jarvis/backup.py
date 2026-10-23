"""Copia di sicurezza settimanale di cio' che non si puo' rifare (schede, rubrica a mano, promemoria, turni, target dei negozi, impostazioni): un file .zip
in memoria/_backup, SOLO sul PC (mai su internet). Restano le ultime 4 copie; le piu' vecchie vanno in memoria/_da_eliminare (niente si cancella).
NON entrano: chiavi, la chiave e la sessione della banca, i dati di collegamento e l'archivio cifrato di WhatsApp, l'impronta della voce, modelli e programmi."""
from __future__ import annotations

import shutil
import threading
import time
import zipfile
from datetime import date, datetime
from pathlib import Path

from . import config, logs

MEMORIA = Path(__file__).parent.parent / "memoria"
CARTELLA = MEMORIA / "_backup"
ESCLUDI_CARTELLE = {"whatsapp", "banca", "modelli", "node22", "finestra_jarvis", "_backup", "_da_eliminare", "__pycache__"}
ESCLUDI_NOMI = ("token", "chiave", "rubrica_url", "voce_andrea")
ESCLUDI_FINALI = (".pem", ".key", ".flag", ".npz", ".onnx", ".tmp")
GIORNI = 7
TENERE = 4
_stato = {"ultimo": ""}


def _incluso(p: Path) -> bool:
    rel = p.relative_to(MEMORIA)
    if any(part in ESCLUDI_CARTELLE for part in rel.parts[:-1]):
        return False
    nome = p.name.lower()
    return not (any(x in nome for x in ESCLUDI_NOMI) or nome.endswith(ESCLUDI_FINALI))


def crea() -> str:
    """Fa una copia adesso. Ritorna il nome del file."""
    CARTELLA.mkdir(parents=True, exist_ok=True)
    nome = f"backup_{datetime.now().strftime('%Y-%m-%d_%H%M')}.zip"
    n = 0
    with zipfile.ZipFile(CARTELLA / nome, "w", zipfile.ZIP_DEFLATED) as z:
        for p in MEMORIA.rglob("*"):
            if p.is_file() and _incluso(p):
                try:
                    z.write(p, p.relative_to(MEMORIA).as_posix())
                    n += 1
                except OSError:
                    continue  # un file occupato non blocca tutta la copia
    if n == 0:
        (CARTELLA / nome).unlink()
        raise RuntimeError("niente da copiare")
    vecchi = sorted(CARTELLA.glob("backup_*.zip"))[:-TENERE]
    if vecchi:
        scarto = MEMORIA / "_da_eliminare"
        scarto.mkdir(parents=True, exist_ok=True)
        for v in vecchi:
            shutil.move(str(v), str(scarto / v.name))
    logs.log_route(f"BACKUP: creato ({n} file)")
    return nome


def _ultima_copia() -> date | None:
    zips = sorted(CARTELLA.glob("backup_*.zip")) if CARTELLA.exists() else []
    if not zips:
        return None
    try:
        return datetime.strptime(zips[-1].name[7:17], "%Y-%m-%d").date()
    except ValueError:
        return None


def serve() -> bool:
    u = _ultima_copia()
    return u is None or (date.today() - u).days >= GIORNI


def _ciclo():
    time.sleep(300)  # prima si lascia partire tutto
    while True:
        try:
            if serve():
                crea()
        except Exception as e:
            logs.log_error(e, "backup")
        time.sleep(6 * 3600)


def avvia():
    if config.ENABLE_BACKUP:
        threading.Thread(target=_ciclo, daemon=True).start()
