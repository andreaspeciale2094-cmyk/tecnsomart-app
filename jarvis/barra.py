"""Barra in basso della schermata di Jarvis (come la barra di Windows quando Jarvis e' a tutto schermo): pulsante Start, app del Desktop,
finestre aperte, uscita dal tutto schermo. Solo Windows e solo dal PC (mai dal telefono). Titoli e icone restano in RAM: nessun registro."""
import base64
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import logs

NASCONDI = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_icone: dict[str, str | None] = {}      # percorso -> "data:image/png;base64,..." (solo in RAM)
_in_corso: set[str] = set()
_lock = threading.Lock()
IGNORA_EXE = {"textinputhost.exe"}
IGNORA_TITOLI = ("J.A.R.V.I.S.", "Program Manager", "Impostazioni di input")

_PS_ICONE = r"""
Add-Type -AssemblyName System.Drawing
$p = [Console]::In.ReadToEnd() | ConvertFrom-Json
$o = @{}
foreach ($f in $p) {
  try {
    $i = [System.Drawing.Icon]::ExtractAssociatedIcon($f)
    $b = New-Object System.Drawing.Bitmap 32,32
    $g = [System.Drawing.Graphics]::FromImage($b)
    $g.InterpolationMode = 'HighQualityBicubic'
    $g.DrawImage($i.ToBitmap(), 0, 0, 32, 32)
    $m = New-Object System.IO.MemoryStream
    $b.Save($m, [System.Drawing.Imaging.ImageFormat]::Png)
    $o[$f] = [Convert]::ToBase64String($m.ToArray())
  } catch {}
}
$o | ConvertTo-Json -Compress
"""


def disponibile() -> bool:
    return sys.platform == "win32"


def _estrai_icone(percorsi: list[str]):
    """Prende le icone vere dei programmi (una sola chiamata, in sottofondo) e le tiene in RAM."""
    nuovi = [p for p in percorsi if p not in _icone and p not in _in_corso]
    if not nuovi or not disponibile():
        return
    _in_corso.update(nuovi)

    def lavoro():
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", _PS_ICONE], input=json.dumps(nuovi), capture_output=True, text=True,
                                 timeout=40, creationflags=NASCONDI).stdout
            dati = json.loads(out or "{}") or {}
        except (OSError, ValueError, subprocess.SubprocessError):
            dati = {}
        for p in nuovi:
            b = dati.get(p)
            _icone[p] = f"data:image/png;base64,{b}" if b else None
            _in_corso.discard(p)

    threading.Thread(target=lavoro, daemon=True).start()


FILE_SCRIVANIA = Path(__file__).parent.parent / "memoria" / "desktop_jarvis.json"


def _salva(app: list[dict]):
    FILE_SCRIVANIA.parent.mkdir(parents=True, exist_ok=True)
    FILE_SCRIVANIA.write_text(json.dumps(app, ensure_ascii=False, indent=1), encoding="utf-8")


def _da_windows() -> list[dict]:
    """Prima volta: parte dai collegamenti che hai sul Desktop di Windows (tuo e pubblico)."""
    trovati = {}
    for base in (Path(os.path.expanduser("~")) / "Desktop", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Desktop"):
        if base.exists():
            for f in sorted(list(base.glob("*.lnk")) + list(base.glob("*.url"))):
                if f.stem.strip().lower() not in ("jarvis", "spegni jarvis"):
                    trovati.setdefault(f.stem, {"nome": f.stem, "come": "file", "valore": str(f)})
    return list(trovati.values())


def scrivania() -> list[dict]:
    """Le icone sul desktop di Jarvis (lista tua in memoria/desktop_jarvis.json, solo sul PC). Si aggiungono e si tolgono quando vuoi."""
    with _lock:
        if not FILE_SCRIVANIA.exists():
            _salva(_da_windows())
        try:
            app = json.loads(FILE_SCRIVANIA.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            app = []
    _estrai_icone([a["valore"] for a in app if a.get("come") == "file"])
    return app


def icona_di(a: dict):
    return _icone.get(a["valore"]) if a.get("come") == "file" else None


def catalogo() -> list[str]:
    """Tutte le app e i giochi che si possono aggiungere (menu Start, Steam, Desktop), senza terminale e simili."""
    from . import pc_comandi
    gia = {a["nome"] for a in scrivania()}
    nomi = {x["nome"] for x in pc_comandi.indice() if not pc_comandi._vietata(x["nome"])}
    return sorted(nomi - gia, key=str.lower)


def aggiungi(nome: str) -> str:
    """Aggiunge un'app al desktop di Jarvis (non cambia nulla in Windows). Il nome deve corrispondere a una sola app."""
    from . import pc_comandi
    nome = (nome or "").strip()
    app = scrivania()
    if any(a["nome"].lower() == nome.lower() for a in app):
        return f"{nome} e' gia' sul desktop di Jarvis."
    trovate = pc_comandi.cerca(nome)
    nomi = list(dict.fromkeys(x["nome"] for x in trovate))
    if not trovate:
        raise ValueError(f"Non trovo nessuna app che somigli a '{nome}'.")
    if len(nomi) > 1:
        raise ValueError("Ne ho trovate piu' di una: " + ", ".join(nomi) + ". Quale vuoi?")
    x = trovate[0]
    if pc_comandi._vietata(x["nome"]):
        raise ValueError("Per sicurezza il terminale e simili non vanno sul desktop.")
    with _lock:
        _salva(app + [{"nome": x["nome"], "come": x["come"], "valore": x["valore"]}])
    logs.log_azione(f"DESKTOP JARVIS: aggiunta '{x['nome']}'")
    return f"Ho messo {x['nome']} sul desktop di Jarvis."


def togli(nome: str) -> str:
    """Toglie un'icona dal desktop di Jarvis. Non cancella niente: l'app resta dov'e' in Windows."""
    app = scrivania()
    resto = [a for a in app if a["nome"].lower() != (nome or "").strip().lower()]
    if len(resto) == len(app):
        raise ValueError(f"'{nome}' non e' sul desktop di Jarvis.")
    with _lock:
        _salva(resto)
    logs.log_azione(f"DESKTOP JARVIS: tolta '{nome}'")
    return f"Ho tolto {nome} dal desktop di Jarvis (l'app resta sul PC)."


def apri_desktop(nome: str) -> str:
    """Apre un'icona del desktop di Jarvis: solo una di quelle della lista, mai un percorso scelto da fuori."""
    for a in scrivania():
        if a["nome"] == nome:
            if a["come"] == "appid":
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{a['valore']}"], creationflags=NASCONDI)
            else:
                os.startfile(a["valore"])
            logs.log_azione(f"DESKTOP JARVIS: aperto '{nome}'")
            return nome
    raise ValueError("Questa icona non c'e' piu'.")


# ---------------- finestre aperte (solo Windows) ----------------
def _api():
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetWindow.restype = wintypes.HWND
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.GetForegroundWindow.restype = wintypes.HWND
    k = ctypes.windll.kernel32
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return ctypes, wintypes, u, k


def _exe_di(hwnd, ctypes, wintypes, u, k) -> str:
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        return buf.value if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
    finally:
        k.CloseHandle(h)


def finestre() -> list[dict]:
    """Le finestre aperte adesso (quelle che comparirebbero nella barra di Windows)."""
    if not disponibile():
        return []
    ctypes, wintypes, u, k = _api()
    dwm = ctypes.windll.dwmapi
    davanti = u.GetForegroundWindow()
    out: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def passo(hwnd, _):
        try:
            if not u.IsWindowVisible(hwnd) or u.GetWindow(hwnd, 4) or (u.GetWindowLongW(hwnd, -20) & 0x80):  # con proprietario o finestra-strumento
                return True
            nascosta = wintypes.DWORD(0)
            dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(nascosta), 4)  # DWMWA_CLOAKED (desktop virtuali, app UWP sospese)
            n = u.GetWindowTextLengthW(hwnd)
            if nascosta.value or not n:
                return True
            buf = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(hwnd, buf, n + 1)
            titolo = buf.value
            if any(t in titolo for t in IGNORA_TITOLI):
                return True
            exe = _exe_di(hwnd, ctypes, wintypes, u, k)
            if os.path.basename(exe).lower() in IGNORA_EXE:
                return True
            out.append({"id": int(hwnd or 0), "titolo": titolo, "exe": exe, "attiva": hwnd == davanti, "ridotta": bool(u.IsIconic(hwnd))})
        except Exception:
            pass
        return True

    u.EnumWindows(passo, 0)
    _estrai_icone([f["exe"] for f in out if f["exe"]])
    for f in out:
        f["icona"] = _icone.get(f["exe"])
        f["nome"] = Path(f["exe"]).stem.capitalize() if f["exe"] else f["titolo"]
    return out


def porta_davanti(hwnd: int) -> str:
    """Porta davanti una finestra aperta (solo una di quelle dell'elenco)."""
    if not disponibile():
        raise ValueError("Funziona solo sul PC Windows.")
    ctypes, wintypes, u, k = _api()
    if hwnd not in {f["id"] for f in finestre()}:
        raise ValueError("Quella finestra non c'e' piu'.")
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)  # SW_RESTORE
    _tasto(0x12)  # un tocco su Alt: Windows altrimenti non lascia passare in primo piano un'altra app
    u.SetForegroundWindow(hwnd)
    return "ok"


def _tasto(codice: int):
    import ctypes
    ctypes.windll.user32.keybd_event(codice, 0, 0, 0)
    ctypes.windll.user32.keybd_event(codice, 0, 2, 0)


def apri_start() -> str:
    """Apre il menu Start di Windows (tasto Windows)."""
    if not disponibile():
        raise ValueError("Funziona solo sul PC Windows.")
    _tasto(0x5B)
    return "ok"


def schermo_intero_alterna() -> str:
    """Esce dal tutto schermo (o ci rientra) con il tasto F11 sulla finestra di Jarvis, che e' quella davanti perche' hai appena cliccato qui."""
    if not disponibile():
        raise ValueError("Funziona solo sul PC Windows.")
    _tasto(0x7A)
    return "ok"


# ---------------- ricerca nel PC (app, giochi, file, cartelle) ----------------
CARTELLE_RICERCA = ("Desktop", "Documents", "Documenti", "Downloads", "Download", "Pictures", "Immagini", "Videos", "Video", "Music", "Musica")
NON_APRIRE = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".msi", ".scr", ".com", ".reg", ".hta", ".jar", ".lnk", ".dll", ".sys"}
SALTA = {"node_modules", ".git", "__pycache__", "appdata", "$recycle.bin", "_da_eliminare"}
_file: dict = {"voci": [], "t": 0.0, "pronto": False, "lavora": False}


def _costruisci_indice_file():
    voci = []
    casa = Path(os.path.expanduser("~"))
    radici = []
    for base in (casa, casa / "OneDrive"):
        radici += [base / c for c in CARTELLE_RICERCA if (base / c).is_dir()]
    for radice in dict.fromkeys(radici):
        base_livello = len(radice.parts)
        for cur, dirs, files in os.walk(radice):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in SALTA]
            if len(Path(cur).parts) - base_livello >= 4:
                dirs[:] = []
            for d in dirs:
                voci.append((d, str(Path(cur) / d), True))
            for f in files:
                if not f.startswith(".") and Path(f).suffix.lower() not in NON_APRIRE:
                    voci.append((f, str(Path(cur) / f), False))
            if len(voci) > 250000:
                break
    _file["voci"] = voci
    _file["t"] = time.time()
    _file["pronto"] = True
    _file["lavora"] = False


def _prepara_file():
    if _file["lavora"] or (_file["pronto"] and time.time() - _file["t"] < 900):
        return
    _file["lavora"] = True
    threading.Thread(target=_costruisci_indice_file, daemon=True).start()


def cerca(q: str) -> dict:
    """Cerca per nome tra app e giochi (menu Start, Steam, Desktop) e tra i file e le cartelle di Desktop, Documenti, Download, Immagini, Video, Musica.
    Nomi solo in RAM. Gli eseguibili e gli script non si aprono da qui."""
    from . import pc_comandi
    _prepara_file()
    qn = pc_comandi._norm(q)
    if not qn:
        return {"voci": [], "file_pronti": _file["pronto"]}
    parole = qn.split()
    app_ok, visti = [], set()
    for a in pc_comandi.indice():
        n = pc_comandi._norm(a["nome"])
        if a["nome"] in visti or pc_comandi._vietata(a["nome"]):
            continue
        if all(t in n for t in parole):
            visti.add(a["nome"])
            app_ok.append((0 if n.startswith(qn) else 1, len(n), a["nome"]))
    for a in pc_comandi.cerca(q):  # anche i nomi che il riconoscimento o gli alias correggono
        if a["nome"] not in visti and not pc_comandi._vietata(a["nome"]):
            visti.add(a["nome"])
            app_ok.append((2, len(a["nome"]), a["nome"]))
    voci = [{"tipo": "app", "nome": n, "id": n} for _, _, n in sorted(app_ok)[:6]]
    trovati = []
    for nome, perc, cartella in _file["voci"]:
        nn = pc_comandi._norm(nome)
        if all(t in nn for t in parole):
            trovati.append((0 if nn.startswith(qn) else 1, 0 if cartella else 1, len(nn), nome, perc, cartella))
    for _, _, _, nome, perc, cartella in sorted(trovati)[:8]:
        voci.append({"tipo": "cartella" if cartella else "file", "nome": nome, "id": perc, "dove": str(Path(perc).parent.name)})
    return {"voci": voci, "file_pronti": _file["pronto"]}


def apri_voce(tipo: str, id_: str) -> str:
    """Apre il risultato scelto: solo cio' che la ricerca ha davvero trovato (mai un percorso o un nome inventato da fuori)."""
    from . import pc_comandi
    if tipo == "app":
        for a in pc_comandi.indice():
            if a["nome"] == id_ and not pc_comandi._vietata(a["nome"]):
                if a["come"] == "appid":
                    subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{a['valore']}"], creationflags=NASCONDI)
                else:
                    os.startfile(a["valore"])
                logs.log_azione(f"RICERCA: aperta app '{a['nome']}'")
                return a["nome"]
        raise ValueError("Non trovo piu' questa app.")
    if tipo in ("file", "cartella"):
        if any(perc == id_ and cart == (tipo == "cartella") for _, perc, cart in _file["voci"]) and os.path.exists(id_):
            os.startfile(id_)
            logs.log_azione(f"RICERCA: aperto un {tipo}")  # il nome del file resta fuori dai registri
            return Path(id_).name
        raise ValueError("Non trovo piu' questo elemento.")
    raise ValueError("Tipo sconosciuto.")
