"""Riconoscimento della voce di Andrea: Jarvis risponde solo se la voce somiglia alla sua "impronta vocale".
Tutto avviene sul PC (nessun servizio a pagamento, niente internet tranne il download una tantum del modello, ~26 MB).
L'impronta vocale e' un dato personale: sta SOLO in memoria/voce_andrea.npz (mai su GitHub, mai nei registri; nei registri solo il punteggio di somiglianza).
Modello: eres2net inglese (sherpa-onnx), scelto perche' nelle prove separava meglio la stessa persona dalle altre.
Il controllo e' un livello in piu', non un lucchetto: le azioni delicate restano comunque con il si' di Andrea."""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import httpx

try:
    import numpy as np
except ImportError:  # senza numpy il riconoscimento della voce resta spento e Jarvis parte lo stesso
    np = None

from . import logs

CARTELLA = Path(__file__).parent.parent / "memoria"
MODELLI = CARTELLA / "modelli"
NOME_MODELLO = "3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx"
URL_MODELLO = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/" + NOME_MODELLO
FILE_IMPRONTA = CARTELLA / "voce_andrea.npz"
FILE_SOGLIA = CARTELLA / "voce_soglia.txt"
FILE_SPENTO = CARTELLA / "voce_spento.flag"
RATE = 16000
BLOCCO = 1280
MIN_VOCE_S = 1.0          # sotto questa durata di voce non si riesce a giudicare: si lascia passare
MIN_REGISTRAZIONE_S = 2.5  # una registrazione per imparare la voce deve avere almeno tanta voce
SOGLIA_PREDEFINITA = 0.30
MAX_CAMPIONI = 40


class VoceError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


_estr = {"e": None}
_lock = threading.Lock()
_in_attesa: list = []   # registrazioni appena fatte, non ancora salvate (solo RAM)
_ultimo_errore_log = {"t": 0.0}


# ---------------- programma e modello ----------------
def libreria_presente() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
        return np is not None
    except Exception:
        return False


def modello_pronto() -> bool:
    f = MODELLI / NOME_MODELLO
    return f.exists() and f.stat().st_size > 20_000_000


def prepara() -> None:
    """Controlla che ci sia il programma e, se manca, scarica il modello (una volta sola, ~26 MB)."""
    if not libreria_presente():
        raise VoceError("Manca il programma per riconoscere la voce: fai doppio clic su installa_riconoscimento_voce.bat nella cartella di Jarvis, poi riprova.")
    if modello_pronto():
        return
    MODELLI.mkdir(parents=True, exist_ok=True)
    parziale = MODELLI / (NOME_MODELLO + ".part")
    try:
        with httpx.stream("GET", URL_MODELLO, follow_redirects=True, timeout=httpx.Timeout(30.0, read=120.0)) as r:
            r.raise_for_status()
            with open(parziale, "wb") as f:
                for pezzo in r.iter_bytes(1 << 20):
                    f.write(pezzo)
        if parziale.stat().st_size < 20_000_000:
            raise VoceError("Il file scaricato non e' completo: riprova.")
        parziale.replace(MODELLI / NOME_MODELLO)
    except httpx.HTTPError:
        raise VoceError("Non riesco a scaricare il modello (serve internet, una volta sola): riprova tra poco.")
    finally:
        if parziale.exists():
            try:
                parziale.unlink()
            except OSError:
                pass


def _estrattore():
    with _lock:
        if _estr["e"] is None:
            import sherpa_onnx
            cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODELLI / NOME_MODELLO), num_threads=2, debug=False, provider="cpu")
            _estr["e"] = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
        return _estr["e"]


# ---------------- audio -> impronta ----------------
def solo_voce(blocchi: list) -> np.ndarray:
    """Dai blocchi del microfono (int16, 1280 campioni) tiene i blocchi in cui si parla (soglia adattiva sul volume): silenzio e rumore lento non servono."""
    if not blocchi:
        return np.zeros(0, dtype=np.float32)
    b = [np.asarray(x, dtype=np.int16) for x in blocchi]
    rms = np.array([float(np.sqrt(np.mean(x.astype(np.float32) ** 2)) + 1e-6) for x in b])
    soglia = max(120.0, 0.25 * float(np.percentile(rms, 90)))
    tenuti = [x for x, v in zip(b, rms) if v >= soglia]
    if not tenuti:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(tenuti).astype(np.float32) / 32768.0


def durata(x: np.ndarray) -> float:
    return len(x) / RATE


def incorpora(x: np.ndarray) -> np.ndarray:
    e = _estrattore()
    s = e.create_stream()
    s.accept_waveform(sample_rate=RATE, waveform=x.astype(np.float32))
    s.input_finished()
    v = np.array(e.compute(s), dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


# ---------------- impronta salvata ----------------
def carica_impronta():
    if not FILE_IMPRONTA.exists():
        return None
    try:
        return np.load(FILE_IMPRONTA)["emb"].astype(np.float32)
    except Exception:
        return None


def _salva_impronta(emb: np.ndarray):
    CARTELLA.mkdir(parents=True, exist_ok=True)
    np.savez(FILE_IMPRONTA, emb=emb.astype(np.float32))


def azzera() -> str:
    """Ricomincia da capo: l'impronta vecchia va in memoria/_da_eliminare (non si cancella)."""
    _in_attesa.clear()
    if FILE_IMPRONTA.exists():
        dest = CARTELLA / "_da_eliminare"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(FILE_IMPRONTA), str(dest / f"voce_andrea-{time.strftime('%Y%m%d-%H%M%S')}.npz"))
        logs.log_azione("VOCE: impronta vocale messa da parte (memoria/_da_eliminare)")
    return "Ho messo da parte la tua impronta vocale: puoi registrarla da capo."


def soglia() -> float:
    try:
        return float(FILE_SOGLIA.read_text(encoding="utf-8").strip()) if FILE_SOGLIA.exists() else SOGLIA_PREDEFINITA
    except (OSError, ValueError):
        return SOGLIA_PREDEFINITA


def imposta_soglia(v: float):
    if not 0.12 <= v <= 0.7:
        raise VoceError("Severita' non valida.")
    CARTELLA.mkdir(parents=True, exist_ok=True)
    FILE_SOGLIA.write_text(str(round(v, 2)), encoding="utf-8")


def interruttore(attivo: bool):
    CARTELLA.mkdir(parents=True, exist_ok=True)
    if attivo:
        if FILE_SPENTO.exists():
            FILE_SPENTO.unlink()
    else:
        FILE_SPENTO.write_text("1", encoding="utf-8")


def attiva() -> bool:
    """Il controllo e' in funzione: c'e' un'impronta, non e' stato spento e il programma c'e'."""
    return FILE_IMPRONTA.exists() and not FILE_SPENTO.exists() and libreria_presente() and modello_pronto()


def stato() -> dict:
    e = carica_impronta()
    return {"programma": libreria_presente(), "modello": modello_pronto(), "campioni": 0 if e is None else int(len(e)), "in_attesa": len(_in_attesa),
            "spento": FILE_SPENTO.exists(), "attivo": attiva(), "soglia": soglia()}


# ---------------- imparare la voce ----------------
def aggiungi_registrazione(blocchi: list) -> dict:
    """Una registrazione fatta dalla pagina: se c'e' abbastanza voce ne ricava un'impronta e la tiene in attesa (si salva con `conferma`)."""
    prepara()
    x = solo_voce(blocchi)
    s = durata(x)
    if s < MIN_REGISTRAZIONE_S:
        return {"ok": False, "voce_s": round(s, 1), "in_attesa": len(_in_attesa)}
    _in_attesa.append(incorpora(x))
    return {"ok": True, "voce_s": round(s, 1), "in_attesa": len(_in_attesa)}


def conferma() -> int:
    """Salva le registrazioni in attesa AGGIUNGENDOLE a quelle gia' salvate (cosi' puoi imparare la voce da raffreddato e poi da sano)."""
    if len(_in_attesa) < 3:
        raise VoceError("Servono almeno 3 registrazioni buone: ne ho solo " + str(len(_in_attesa)) + ".")
    vecchie = carica_impronta()
    tutte = np.vstack(([vecchie] if vecchie is not None else []) + [np.vstack(_in_attesa)])
    tutte = tutte[-MAX_CAMPIONI:]
    _salva_impronta(tutte)
    _in_attesa.clear()
    FILE_SPENTO.unlink(missing_ok=True)  # appena impara la voce, il controllo si accende
    logs.log_azione("VOCE: impronta vocale salvata (solo sul PC)")
    return int(len(tutte))


def annulla():
    _in_attesa.clear()


# ---------------- controllo ----------------
def punteggio_di(emb: np.ndarray, impronta: np.ndarray) -> float:
    centro = impronta.mean(axis=0)
    centro = centro / (np.linalg.norm(centro) + 1e-9)
    return float(max(emb @ centro, (impronta @ emb).max()))


def verifica(blocchi: list) -> tuple:
    """(esito, punteggio): esito True = e' la voce di Andrea, False = no, None = non si puo' giudicare (controllo spento, poca voce, errore): in quel caso si lascia passare."""
    try:
        if not attiva():
            return None, None
        x = solo_voce(blocchi)
        if durata(x) < MIN_VOCE_S:
            return None, None
        impronta = carica_impronta()
        if impronta is None:
            return None, None
        p = punteggio_di(incorpora(x), impronta)
        return p >= soglia(), round(p, 2)
    except Exception as e:
        if time.time() - _ultimo_errore_log["t"] > 120:
            _ultimo_errore_log["t"] = time.time()
            logs.log_error(e, "riconoscimento voce")
        return None, None
