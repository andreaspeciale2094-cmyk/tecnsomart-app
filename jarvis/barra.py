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

_PS_ICONE_FINESTRE = r"""
Add-Type -AssemblyName System.Drawing
$p = [Console]::In.ReadToEnd() | ConvertFrom-Json
$o = @{}
foreach ($k in $p) {
  try {
    $h = [long]($k -split '\|')[1]
    $i = [System.Drawing.Icon]::FromHandle([IntPtr]$h)
    $b = New-Object System.Drawing.Bitmap 32,32
    $g = [System.Drawing.Graphics]::FromImage($b)
    $g.InterpolationMode = 'HighQualityBicubic'
    $g.DrawImage($i.ToBitmap(), 0, 0, 32, 32)
    $m = New-Object System.IO.MemoryStream
    $b.Save($m, [System.Drawing.Imaging.ImageFormat]::Png)
    $o[$k] = [Convert]::ToBase64String($m.ToArray())
  } catch {}
}
$o | ConvertTo-Json -Compress
"""

_PS_ICONE_APP = r"""
Add-Type -AssemblyName System.Drawing
$ids = [Console]::In.ReadToEnd() | ConvertFrom-Json
$o = @{}
$cart = @{ '{6D809377-6AF0-444B-8957-A3773F02200E}' = $env:ProgramFiles; '{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}' = ${env:ProgramFiles(x86)}; '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}' = [Environment]::SystemDirectory; '{F38BF404-1D43-42F2-9305-67DE0B28FC23}' = $env:windir }
function Png64($img) {
  $b = New-Object System.Drawing.Bitmap 64,64
  $g = [System.Drawing.Graphics]::FromImage($b); $g.InterpolationMode = 'HighQualityBicubic'; $g.DrawImage($img, 0, 0, 64, 64)
  $m = New-Object System.IO.MemoryStream; $b.Save($m, [System.Drawing.Imaging.ImageFormat]::Png); [Convert]::ToBase64String($m.ToArray())
}
foreach ($id in $ids) {
  try {
    if ($id -match '^(.+?)!(.+)$') {
      $pk = Get-AppxPackage | Where-Object { $_.PackageFamilyName -eq $matches[1] } | Select-Object -First 1
      $app = $matches[2]
      if ($pk) {
        [xml]$mf = Get-Content (Join-Path $pk.InstallLocation 'AppxManifest.xml')
        $a = $mf.Package.Applications.Application | Where-Object { $_.Id -eq $app } | Select-Object -First 1
        $rel = $a.VisualElements.Square44x44Logo; if (-not $rel) { $rel = $a.VisualElements.Square150x150Logo }
        $full = Join-Path $pk.InstallLocation $rel
        $dir = Split-Path $full; $base = [IO.Path]::GetFileNameWithoutExtension($full); $ext = [IO.Path]::GetExtension($full)
        $f = Get-ChildItem $dir -Filter ($base + '*' + $ext) -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch 'contrast|lightunplated' }
        $sc = $f | Where-Object { $_.Name -match 'targetsize-(48|64|96)_altform-unplated' } | Select-Object -First 1
        if (-not $sc) { $sc = $f | Where-Object { $_.Name -match 'targetsize-(48|64|96)' -and $_.Name -notmatch 'altform' } | Select-Object -First 1 }
        if (-not $sc) { $sc = $f | Where-Object { $_.Name -match 'scale-(200|400)' } | Select-Object -First 1 }
        if (-not $sc) { $sc = $f | Select-Object -First 1 }
        if ($sc) { $o[$id] = Png64([System.Drawing.Image]::FromFile($sc.FullName)) }
      }
    } else {
      $p = $id
      if ($id -match '^(\{[0-9A-Fa-f-]+\})\\(.*)$' -and $cart[$matches[1]]) { $p = Join-Path $cart[$matches[1]] $matches[2] }
      if (Test-Path $p) { $o[$id] = Png64([System.Drawing.Icon]::ExtractAssociatedIcon($p).ToBitmap()) }
    }
  } catch {}
}
$o | ConvertTo-Json -Compress
"""


def disponibile() -> bool:
    return sys.platform == "win32"


def _estrai_icone(percorsi: list[str], script: str = "", prefisso: str = ""):
    """Prende le icone vere dei programmi (una sola chiamata, in sottofondo) e le tiene in RAM."""
    script = script or _PS_ICONE
    nuovi = [p for p in percorsi if prefisso + p not in _icone and prefisso + p not in _in_corso]
    if not nuovi or not disponibile():
        return
    _in_corso.update(prefisso + p for p in nuovi)

    def lavoro():
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", script], input=json.dumps(nuovi), capture_output=True, text=True,
                                 timeout=60, creationflags=NASCONDI).stdout
            dati = json.loads(out or "{}") or {}
        except (OSError, ValueError, subprocess.SubprocessError):
            dati = {}
        for p in nuovi:
            b = dati.get(p)
            _icone[prefisso + p] = f"data:image/png;base64,{b}" if b else None
            _in_corso.discard(prefisso + p)

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


PINNATE = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar"
FLAG_IMPORT = Path(__file__).parent.parent / "memoria" / "desktop_jarvis_importato.flag"


def _pinnate() -> list[dict]:
    """Le app fissate sulla barra di Windows (i loro collegamenti stanno in una cartella di Windows: si leggono soltanto)."""
    from . import pc_comandi
    out = []
    if PINNATE.is_dir():
        for f in sorted(PINNATE.glob("*.lnk")):
            if not pc_comandi._vietata(f.stem) and f.stem.strip().lower() not in ("jarvis", "spegni jarvis"):
                out.append({"nome": f.stem, "come": "file", "valore": str(f)})
    return out


def _unisci(app: list[dict], nuove: list[dict]) -> tuple[list[dict], int]:
    nomi = {a["nome"].lower() for a in app}
    aggiunte = [n for n in nuove if n["nome"].lower() not in nomi]
    return app + aggiunte, len(aggiunte)


def importa_barra_windows() -> str:
    """Mette sul desktop di Jarvis le app che hai fissato sulla barra di Windows (quelle gia' presenti non si duplicano)."""
    app = scrivania()
    nuove, n = _unisci(app, _pinnate())
    if not n:
        return "Non ho trovato altre app fissate sulla barra di Windows da aggiungere."
    with _lock:
        _salva(nuove)
    logs.log_azione(f"DESKTOP JARVIS: importate {n} app dalla barra di Windows")
    return f"Ho aggiunto {n} app prese dalla barra di Windows."


def scrivania() -> list[dict]:
    """Le icone sul desktop di Jarvis (lista tua in memoria/desktop_jarvis.json, solo sul PC). Si aggiungono e si tolgono quando vuoi.
    La prima volta parte dal Desktop di Windows e dalle app fissate sulla barra di Windows."""
    with _lock:
        if not FILE_SCRIVANIA.exists():
            _salva(_da_windows())
        try:
            app = json.loads(FILE_SCRIVANIA.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            app = []
        if not FLAG_IMPORT.exists():
            FLAG_IMPORT.parent.mkdir(parents=True, exist_ok=True)
            app, n = _unisci(app, _pinnate())
            if n:
                _salva(app)
            FLAG_IMPORT.write_text("1", encoding="utf-8")
    _estrai_icone([a["valore"] for a in app if a.get("come") == "file"])
    _estrai_icone([a["valore"] for a in app if a.get("come") == "appid"], _PS_ICONE_APP, "appid:")  # app del menu Start (anche del Microsoft Store)
    return app


def icona_di(a: dict):
    if a.get("come") == "file":
        return _icone.get(a["valore"])
    return _icone.get("appid:" + a["valore"]) if a.get("come") == "appid" else None


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


# programmi che mostrano tante app diverse: l'icona vera e' quella della finestra, non quella del programma
DA_FINESTRA = {"applicationframehost.exe", "chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"}


def _icona_finestra(hwnd, ctypes, wintypes, u) -> int:
    """L'icona che la finestra stessa mostra (per le app dello Store e le app-sito di Chrome). Ritorna l'handle o 0."""
    try:
        u.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        u.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        u.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetClassLongPtrW.restype = ctypes.c_size_t
        r = ctypes.c_size_t(0)
        for quale in (1, 2, 0):  # grande, piccola (sistema), piccola
            r.value = 0
            u.SendMessageTimeoutW(hwnd, 0x7F, quale, 0, 2, 150, ctypes.byref(r))
            if r.value:
                return int(r.value)
        return int(u.GetClassLongPtrW(hwnd, -14) or 0)
    except Exception:
        return 0


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
            hic = _icona_finestra(hwnd, ctypes, wintypes, u) if os.path.basename(exe).lower() in DA_FINESTRA or not exe else 0
            out.append({"id": int(hwnd or 0), "titolo": titolo, "exe": exe, "attiva": hwnd == davanti, "ridotta": bool(u.IsIconic(hwnd)), "hicon": hic})
        except Exception:
            pass
        return True

    u.EnumWindows(passo, 0)
    _estrai_icone([f["exe"] for f in out if f["exe"] and not f["hicon"]])
    _estrai_icone([f"{f['id']}|{f['hicon']}" for f in out if f["hicon"]], _PS_ICONE_FINESTRE)
    for f in out:
        chiave = f"{f['id']}|{f['hicon']}"
        f["icona"] = _icone.get(chiave) if f["hicon"] else None
        if not f["icona"]:
            f["icona"] = _icone.get(f["exe"])
        f["nome"] = Path(f["exe"]).stem.capitalize() if f["exe"] else f["titolo"]
        f.pop("hicon", None)
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


_explorer = {"t": 0.0, "v": True}


def explorer_attivo() -> bool:
    """Vero se c'e' il desktop normale di Windows (explorer.exe); falso se al suo posto c'e' Jarvis. Controllato al massimo ogni 10 secondi."""
    if not disponibile():
        return True
    if time.time() - _explorer["t"] > 10:
        try:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq explorer.exe", "/NH"], capture_output=True, text=True, timeout=8, creationflags=NASCONDI).stdout
            _explorer["v"] = "explorer.exe" in out.lower()
        except (OSError, subprocess.SubprocessError):
            _explorer["v"] = True
        _explorer["t"] = time.time()
    return _explorer["v"]


def desktop_windows() -> str:
    """Fa comparire il desktop normale di Windows (barra, menu Start, icone) accanto a Jarvis."""
    if not disponibile():
        raise ValueError("Funziona solo sul PC Windows.")
    subprocess.Popen(["explorer.exe"])
    _explorer["t"] = 0.0
    logs.log_azione("BARRA: avviato il desktop di Windows")
    return "ok"


def porta_jarvis_davanti() -> bool:
    """Porta davanti la finestra di Jarvis (a tutto schermo): serve quando parte il desktop di Windows dietro di lei."""
    if not disponibile():
        return False
    ctypes, wintypes, u, k = _api()
    trovata = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def passo(hwnd, _):
        try:
            if u.IsWindowVisible(hwnd):
                n = u.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hwnd, buf, n + 1)
                    if "J.A.R.V.I.S." in buf.value:
                        trovata.append(int(hwnd or 0))
        except Exception:
            pass
        return True

    u.EnumWindows(passo, 0)
    if not trovata:
        return False
    if u.IsIconic(trovata[0]):
        u.ShowWindow(trovata[0], 9)
    _tasto(0x12)
    u.SetForegroundWindow(trovata[0])
    return True


def trova_finestra(parola: str) -> int | None:
    """Cerca al volo (senza icone ne' altro di pesante) una finestra visibile col nome nel titolo: ritorna l'id oppure None."""
    if not disponibile():
        return None
    ctypes, wintypes, u, k = _api()
    trovata: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def passo(hwnd, _):
        try:
            if u.IsWindowVisible(hwnd):
                n = u.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hwnd, buf, n + 1)
                    if parola.lower() in buf.value.lower() and "J.A.R.V.I.S." not in buf.value:
                        trovata.append(int(hwnd or 0))
        except Exception:
            pass
        return True

    u.EnumWindows(passo, 0)
    return trovata[0] if trovata else None


_fuori_schermo: dict[int, tuple[int, int, int, int]] = {}  # finestre messe fuori dallo schermo (x, y, larghezza, altezza) da rimettere al loro posto


def _metti_fuori_schermo(hwnd: int):
    """Sposta la finestra lontano dallo schermo senza ridurla (cosi' l'app non si addormenta) e ricorda dov'era."""
    ctypes, wintypes, u, k = _api()
    r = wintypes.RECT()
    u.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r))
    if r.left <= -20000:
        return
    _fuori_schermo[hwnd] = (r.left, r.top, max(r.right - r.left, 700), max(r.bottom - r.top, 500))
    u.SetWindowPos(wintypes.HWND(hwnd), None, -32000, -32000, 0, 0, 0x0001 | 0x0004 | 0x0010)  # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE


def _rimetti_al_posto(hwnd: int):
    if hwnd not in _fuori_schermo:
        return
    ctypes, wintypes, u, k = _api()
    x, y, w, h = _fuori_schermo.pop(hwnd)
    larghezza_schermo, altezza_schermo = u.GetSystemMetrics(0), u.GetSystemMetrics(1)
    x = min(max(x, 0), max(larghezza_schermo - 300, 0))
    y = min(max(y, 0), max(altezza_schermo - 200, 0))
    u.SetWindowPos(wintypes.HWND(hwnd), None, x, y, w, h, 0x0004 | 0x0010)  # SWP_NOZORDER | SWP_NOACTIVATE


def porta_davanti_veloce(hwnd: int):
    """Porta davanti una finestra gia' trovata con trova_finestra (senza ricontrollare l'elenco, che e' lento)."""
    ctypes, wintypes, u, k = _api()
    _rimetti_al_posto(hwnd)
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)  # SW_RESTORE
    _tasto(0x12)  # un tocco su Alt: Windows altrimenti non lascia passare in primo piano un'altra app
    u.SetForegroundWindow(hwnd)


def porta_davanti_per_nome(parola: str, attesa: float = 8.0) -> bool:
    """Se la finestra c'e' gia' la porta davanti subito; altrimenti aspetta che compaia (dopo aver aperto un'app) e poi la porta davanti."""
    t0 = time.time()
    while True:
        try:
            h = trova_finestra(parola)
            if h:
                porta_davanti_veloce(h)
                from . import logs
                logs.log_route(f"APP: {parola} portata davanti dopo {time.time() - t0:.1f} s")
                return True
        except Exception:
            pass
        if time.time() - t0 >= attesa:
            return False
        time.sleep(0.1)


def precarica_app(uri: str, parola: str, attesa: float = 40.0) -> bool:
    """Accende un'app all'avvio di Jarvis e la lascia DIETRO la sua finestra a tutto schermo (non ridotta: le app dello Store ridotte
    si addormentano e ci mettono secondi a svegliarsi). Al clic basta portarla davanti, all'istante. Solo Windows."""
    if not disponibile():
        return False
    from . import logs
    if trova_finestra(parola):
        logs.log_route(f"APP: {parola} era gia' aperta")
        return True
    os.startfile(uri)  # type: ignore[attr-defined]
    t0 = time.time()
    while time.time() - t0 < attesa:
        h = trova_finestra(parola)
        if h:
            logs.log_route(f"APP: {parola} precaricata, finestra comparsa dopo {time.time() - t0:.1f} s")
            time.sleep(2.5)  # il tempo di finire di caricare
            try:
                _metti_fuori_schermo(h)  # non si vede piu' neanche per un attimo, ma l'app resta sveglia
            except Exception as e:
                logs.log_error(e, "app fuori schermo")
            porta_jarvis_davanti()
            return True
        time.sleep(0.4)
    logs.log_route(f"APP: {parola} NON ha mostrato nessuna finestra in {attesa:.0f} s (precaricamento fallito)")
    porta_jarvis_davanti()
    return False


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
