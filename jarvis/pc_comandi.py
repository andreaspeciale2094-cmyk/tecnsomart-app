"""Comandi vocali per il PC: aprire app e giochi ("apri FC 27"), volume, blocco, mostra desktop; spegni, riavvia, standby e chiudi app
solo dopo il si' di Andrea. Niente impostazioni di Windows toccate (solo tasti multimediali e comandi normali), niente PowerShell o
prompt dei comandi aperti su richiesta. Gli alias che gli insegni stanno in memoria/app_alias.json."""
import difflib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import uuid
from pathlib import Path

from . import logs, posta

ALIAS = Path(__file__).parent.parent / "memoria" / "app_alias.json"
VIETATE = ("powershell", "prompt dei comandi", "command prompt", "cmd", "terminale", "terminal", "regedit", "editor del registro",
           "registry", "gestione attivita", "task manager", "esegui", "run", "windows terminal", "wsl", "bash")
_indice: dict = {"t": 0.0, "app": []}
_in_attesa: dict[str, dict] = {}
NASCONDI = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class PcError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _parole_numeri() -> dict[str, str]:
    """ventisette -> 27 (il riconoscimento vocale a volte scrive i numeri in lettere)."""
    unita = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci", "undici", "dodici", "tredici",
             "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove"]
    decine = {2: "venti", 3: "trenta", 4: "quaranta", 5: "cinquanta", 6: "sessanta", 7: "settanta", 8: "ottanta", 9: "novanta"}
    out = {w: str(i) for i, w in enumerate(unita)}
    for d, nome in decine.items():
        out[nome] = str(d * 10)
        for u in range(1, 10):
            base = nome[:-1] if u in (1, 8) else nome
            out[base + unita[u]] = str(d * 10 + u)
    return out


_NUMERI = _parole_numeri()


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


# ---------------- elenco di app e giochi ----------------
def _app_menu_start() -> list[dict]:
    """Tutto cio' che compare nel menu Start (app, giochi EA/Epic/Xbox, programmi classici)."""
    if sys.platform != "win32":
        return []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                             capture_output=True, text=True, timeout=25, creationflags=NASCONDI).stdout
        dati = json.loads(out or "[]")
        dati = dati if isinstance(dati, list) else [dati]
        return [{"nome": d["Name"], "come": "appid", "valore": d["AppID"]} for d in dati if d.get("Name") and d.get("AppID")]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _giochi_steam() -> list[dict]:
    out = []
    radici = [Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam" / "steamapps"]
    try:
        vdf = radici[0] / "libraryfolders.vdf"
        if vdf.exists():
            radici += [Path(p.replace("\\\\", "\\")) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore"))]
    except OSError:
        pass
    for r in dict.fromkeys(radici):
        for f in r.glob("appmanifest_*.acf") if r.exists() else []:
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
                nome, idg = re.search(r'"name"\s+"([^"]+)"', t), re.search(r'"appid"\s+"(\d+)"', t)
                if nome and idg and "Steamworks" not in nome.group(1):
                    out.append({"nome": nome.group(1), "come": "uri", "valore": f"steam://rungameid/{idg.group(1)}"})
            except OSError:
                pass
    return out


def _collegamenti_desktop() -> list[dict]:
    out = []
    for base in (Path(os.path.expanduser("~")) / "Desktop", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"):
        if base.exists():
            for f in list(base.glob("*.lnk")) + list(base.glob("*.url")):
                out.append({"nome": f.stem, "come": "file", "valore": str(f)})
    return out


def indice(forza: bool = False) -> list[dict]:
    if forza or time.time() - _indice["t"] > 600 or not _indice["app"]:
        _indice["app"] = _app_menu_start() + _giochi_steam() + _collegamenti_desktop()
        _indice["t"] = time.time()
    return _indice["app"]


def _alias() -> dict:
    try:
        return json.loads(ALIAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def alias_salva(parola: str, nome_app: str) -> str:
    a = _alias()
    a[_norm(parola)] = nome_app.strip()
    ALIAS.parent.mkdir(parents=True, exist_ok=True)
    ALIAS.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"Ricordato: quando dici '{parola}' apro {nome_app}."


def punteggio(richiesto: str, nome: str) -> float:
    q, n = _norm(richiesto), _norm(nome)
    q = " ".join(_NUMERI.get(t, t) for t in q.split())
    if not q or not n:
        return 0.0
    if q == n:
        return 1.5
    qt, nt = q.split(), n.split()
    if all(any(t == x or x.startswith(t) for x in nt) for t in qt):  # tutte le parole dette ci sono nel nome
        return 1.0 + 0.3 * len(qt) / max(len(nt), 1)
    return difflib.SequenceMatcher(None, q, n).ratio()


def cerca(richiesto: str, app: list[dict] | None = None) -> list[dict]:
    app = indice() if app is None else app
    richiesto = _alias().get(_norm(richiesto), richiesto)
    ordine = sorted(((punteggio(richiesto, a["nome"]), a) for a in app), key=lambda x: -x[0])
    buoni = [(p, a) for p, a in ordine if p >= 0.62]
    if not buoni:
        return []
    miglior = buoni[0][0]
    return [a for p, a in buoni if miglior - p < 0.05][:4]


def _vietata(nome: str) -> bool:
    n = _norm(nome)
    return any(re.search(rf"\b{re.escape(v)}\b", n) for v in VIETATE)


def apri(richiesto: str) -> str:
    trovate = cerca(richiesto)
    if not trovate:
        raise PcError(f"Non trovo nessuna app o gioco che somigli a '{richiesto}'. Se me la descrivi, la ricordo per la prossima volta.")
    nomi = list(dict.fromkeys(a["nome"] for a in trovate))
    if len(nomi) > 1:
        raise PcError("Ne ho trovate piu' di una: " + ", ".join(nomi) + ". Quale vuoi aprire?")
    a = trovate[0]
    if _vietata(a["nome"]):
        raise PcError("Per sicurezza non apro il terminale, PowerShell o il registro di sistema da comando vocale.")
    if sys.platform != "win32":
        raise PcError("Questo comando funziona solo sul PC Windows.")
    if a["come"] == "appid":
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{a['valore']}"], creationflags=NASCONDI)
    else:
        os.startfile(a["valore"])  # file di collegamento o indirizzo steam://
    logs.log_azione(f"PC: aperto '{a['nome']}'")
    return f"Apro {a['nome']}."


def elenco(filtro: str = "") -> str:
    nomi = sorted({a["nome"] for a in indice()})
    if filtro:
        nomi = [n for n in nomi if _norm(filtro) in _norm(n)]
    return ("App e giochi trovati: " + ", ".join(nomi[:60])) if nomi else "Non trovo niente."


# ---------------- tasti multimediali e comandi semplici (solo Windows) ----------------
def _tasto(codice: int, volte: int = 1):
    import ctypes

    for _ in range(volte):
        ctypes.windll.user32.keybd_event(codice, 0, 0, 0)
        ctypes.windll.user32.keybd_event(codice, 0, 2, 0)
        time.sleep(0.02)


def volume(azione: str, passi: int = 5) -> str:
    if sys.platform != "win32":
        raise PcError("Il volume si regola solo sul PC Windows.")
    mappa = {"su": 0xAF, "giu": 0xAE, "muto": 0xAD}
    if azione not in mappa:
        raise PcError("Per il volume dimmi: su, giu' oppure muto.")
    _tasto(mappa[azione], 1 if azione == "muto" else max(1, min(int(passi), 25)))
    return {"su": "Volume alzato.", "giu": "Volume abbassato.", "muto": "Fatto: audio acceso o spento."}[azione]


def mostra_desktop() -> str:
    if sys.platform != "win32":
        raise PcError("Funziona solo sul PC Windows.")
    import ctypes

    u = ctypes.windll.user32
    u.keybd_event(0x5B, 0, 0, 0)
    u.keybd_event(0x44, 0, 0, 0)
    u.keybd_event(0x44, 0, 2, 0)
    u.keybd_event(0x5B, 0, 2, 0)
    return "Ecco il desktop."


def blocca() -> str:
    if sys.platform != "win32":
        raise PcError("Funziona solo sul PC Windows.")
    import ctypes

    ctypes.windll.user32.LockWorkStation()
    return "PC bloccato."


# ---------------- azioni che chiedono il si' di Andrea ----------------
def _processi_aperti() -> list[str]:
    if sys.platform != "win32":
        return []
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, creationflags=NASCONDI).stdout
    return sorted({r.split('","')[0].strip('"') for r in out.splitlines() if r.strip()})


def prepara(azione: str, nome: str = "") -> str:
    """Prepara spegni / riavvia / standby / chiudi_app e aspetta il si' di Andrea in un messaggio SUCCESSIVO."""
    if azione not in ("spegni", "riavvia", "standby", "chiudi_app"):
        raise PcError("Azione sconosciuta.")
    bersaglio = ""
    if azione == "chiudi_app":
        if not nome.strip():
            raise PcError("Quale programma devo chiudere?")
        cand = [p for p in _processi_aperti() if punteggio(nome, p.rsplit(".", 1)[0]) >= 0.75]
        cand = [p for p in cand if p.lower() not in ("explorer.exe", "python.exe", "pythonw.exe", "wscript.exe", "node.exe", "svchost.exe", "csrss.exe", "winlogon.exe")]
        if not cand:
            raise PcError(f"Non vedo nessun programma aperto che somigli a '{nome}'.")
        bersaglio = cand[0]
    pid = uuid.uuid4().hex[:6]
    _in_attesa[pid] = {"azione": azione, "bersaglio": bersaglio, "turno": posta.turno()}
    cosa = {"spegni": "spegnere il PC", "riavvia": "riavviare il PC", "standby": "mettere il PC in standby", "chiudi_app": f"chiudere {bersaglio}"}[azione]
    return (f"AZIONE {pid} (non ancora eseguita): {cosa}. Chiedi ad Andrea: 'Vuoi che lo faccia? Il lavoro non salvato potrebbe andare perso.' "
            "Esegui solo dopo il suo si' chiaro.")


def conferma(pid: str) -> str:
    p = _in_attesa.get(pid)
    if not p:
        raise PcError("Non trovo quell'azione: riproviamo.")
    if p["turno"] == posta.turno():
        raise PcError("Prima Andrea deve dirmi di si': aspetta il suo messaggio.")
    if sys.platform != "win32":
        raise PcError("Funziona solo sul PC Windows.")
    del _in_attesa[pid]
    a = p["azione"]
    if a == "spegni":
        subprocess.Popen(["shutdown", "/s", "/t", "20"], creationflags=NASCONDI)
        msg = "Spengo il PC fra venti secondi. Per annullare dimmelo subito."
    elif a == "riavvia":
        subprocess.Popen(["shutdown", "/r", "/t", "20"], creationflags=NASCONDI)
        msg = "Riavvio il PC fra venti secondi. Per annullare dimmelo subito."
    elif a == "standby":
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], creationflags=NASCONDI)
        msg = "Metto il PC in standby."
    else:  # chiusura "gentile": il programma puo' chiedere di salvare
        subprocess.run(["taskkill", "/IM", p["bersaglio"]], capture_output=True, creationflags=NASCONDI)
        msg = f"Ho chiesto a {p['bersaglio']} di chiudersi."
    logs.log_azione(f"PC: {a} {p['bersaglio']}".strip())
    return msg


def annulla_spegnimento() -> str:
    if sys.platform != "win32":
        raise PcError("Funziona solo sul PC Windows.")
    subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=NASCONDI)
    return "Spegnimento annullato."
