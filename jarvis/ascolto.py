"""Ascolto in stanza: Jarvis resta in ascolto e risponde SOLO se lo chiami ("Hey Jarvis", rilevatore locale gratuito openWakeWord).
Tre filtri: 1) rilevatore della parola, tutto sul PC e senza costi; 2) solo dopo il risveglio registra la frase e si ferma quando smetti
di parlare (rilevatore di voce locale); 3) solo allora trascrizione a pagamento e cervello. L'audio non viene mai scritto su disco ne' nei
registri: resta in memoria (RAM) il tempo della frase. Mentre Jarvis parla non ascolta (evita di svegliarsi con la propria voce)."""
import io
import os
import re
import sys
import tempfile
import threading
import time
import wave

from . import config, dialogo, logs, voice

SESSIONE = "ascolto"
RATE = 16000
BLOCCO = 1280  # 80 ms
PAROLA = "hey_jarvis"
stato = {"attivo": True, "risvegli": 0, "errore": "", "in_ascolto": False, "fase": "", "ultimo_errore_log": 0.0}


def _fase(f: str):
    stato["fase"] = f
_parlando_fino = 0.0


def imposta(attivo: bool):
    """Interruttore: spento, il microfono viene rilasciato (niente ascolto)."""
    stato["attivo"] = attivo
    logs.log_azione(f"ASCOLTO {'acceso' if attivo else 'spento'} (interruttore)")


def pausa(minuti: int) -> str:
    """Smette di ascoltare per un po' e riprende da solo (per riunioni e telefonate)."""
    minuti = max(1, min(int(minuti), 480))
    imposta(False)

    def riprendi():
        imposta(True)

    t = threading.Timer(minuti * 60, riprendi)
    t.daemon = True
    t.start()
    return f"Ascolto in pausa per {minuti} minuti: poi riprendo da solo. Per riprendere subito: Ctrl+Alt+J o 'ascolto on' su Telegram."


def _scorciatoia():
    """Ctrl+Alt+J accende/spegne l'ascolto (solo Windows). Un tono basso = spento, uno alto = acceso."""
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32
    if not u.RegisterHotKey(None, 1, 0x0001 | 0x0002, ord("J")):  # Alt + Ctrl + J
        logs.log_route("ASCOLTO: scorciatoia da tastiera non disponibile (gia' usata da un altro programma)")
        return
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            imposta(not stato["attivo"])
            try:
                import winsound

                winsound.Beep(880 if stato["attivo"] else 440, 150)
            except Exception:
                pass


# ---------------- uscita audio: la voce di Jarvis, senza finestre ----------------
def _suona(mp3: bytes):
    """Riproduce un mp3 con Windows (MCI), senza programmi esterni. Altrove non fa niente."""
    if sys.platform != "win32":
        return
    import ctypes

    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(mp3)
        mci = ctypes.windll.winmm.mciSendStringW
        mci(f'open "{path}" type mpegvideo alias jarvisvoce', None, 0, None)
        mci("play jarvisvoce wait", None, 0, None)
        mci("close jarvisvoce", None, 0, None)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _bip():
    if sys.platform == "win32":
        import winsound

        winsound.Beep(880, 110)


def parla(testo: str):
    global _parlando_fino
    testo = testo.strip()
    if len(testo) > 700:  # le risposte lunghe si leggono sulla pagina: a voce solo l'inizio
        testo = testo[:700].rsplit(".", 1)[0] + ". Il resto lo trovi sulla pagina."
    _parlando_fino = time.time() + 600
    try:
        _suona(voice.synthesize(testo))
    except Exception as e:
        logs.log_voice("ascolto", e)
    finally:
        _parlando_fino = time.time() + 0.8  # un attimo di silenzio dopo la voce


# ---------------- ascolto ----------------
def _wav(frames: list) -> bytes:
    import numpy as np

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.concatenate(frames).astype("int16").tobytes())
    return buf.getvalue()


def registra_frase(leggi, vad, attesa: float = 5.0) -> list | None:
    """Registra finche' non smetti di parlare. leggi() ritorna un blocco di 1280 campioni.
    None se nessuno parla entro `attesa` secondi, o se c'e' solo un rumore brevissimo."""
    frames, voce, silenzio, parlato, t0 = [], 0, 0, False, time.time()
    while True:
        blocco = leggi()
        frames.append(blocco)
        if float(vad.predict(blocco, 640)) > 0.5:
            voce += 1
            parlato, silenzio = voce >= 2, 0
        else:
            silenzio += 1
        if parlato and silenzio >= 14:  # circa 1,1 secondi di silenzio: ha finito
            return frames if voce >= 3 else None
        if time.time() - t0 > 15:
            return frames if parlato and voce >= 3 else None
        if not parlato and time.time() - t0 > attesa:
            return None


_CHIAMATA = re.compile(r"^\W*(?:(?:hey|hei|ehi|ei|ehi|ciao|ok|okay)\W+)?(?:jarvis|j\.a\.r\.v\.i\.s\.?|giarvis|garvis|giarvi[sz])\b\W*", re.IGNORECASE)


def togli_chiamata(testo: str) -> str:
    """Toglie 'Hey Jarvis' dall'inizio della frase trascritta."""
    return _CHIAMATA.sub("", testo.strip(), count=1).strip()


def _ascolta(leggi, vad, attesa: float) -> str | None:
    _fase("ti ascolto")
    frames = registra_frase(leggi, vad, attesa)
    if not frames:
        logs.log_route("ASCOLTO: nessuna frase captata (silenzio o voce troppo bassa)")
        return None
    _fase("capisco")
    logs.log_route(f"ASCOLTO: frase registrata ({len(frames) * 80 // 1000} s)")
    if not voice.stt_available():
        logs.log_route("ASCOLTO: manca il riconoscimento vocale (chiave Groq o OpenAI)")
        parla("Non riesco a capirti: manca il riconoscimento vocale.")
        return None
    try:
        testo = voice.transcribe(_wav(frames), "audio/wav").strip()
    except Exception as e:
        logs.log_error(e, "ascolto: trascrizione")
        return None
    logs.log_route(f"ASCOLTO: capito {len(testo)} caratteri")
    return testo if len(testo) >= 2 else None


def _scarta_audio_della_voce(leggi):
    """Dopo che Jarvis ha parlato, butta l'audio registrato mentre parlava (la sua stessa voce)."""
    while time.time() < _parlando_fino:
        leggi()


def gestisci_chiamata(leggi, vad):
    """Dopo il risveglio: ascolta, risponde a voce, e RESTA in conversazione: finche' continui a parlare entro qualche secondo
    non serve ripetere 'Hey Jarvis'. Se dici solo 'Hey Jarvis', risponde 'Dimmi'."""
    stato["risvegli"] += 1
    _bip()
    primo = True
    while True:
        testo = _ascolta(leggi, vad, 5.0 if primo else 7.0)  # dopo una risposta aspetta un po' di piu'
        if testo is None:
            _fase("")
            return
        resto = togli_chiamata(testo)
        if primo and not resto:  # ha detto solo il nome
            parla("Dimmi.")
            _scarta_audio_della_voce(leggi)
            primo = False
            continue
        _fase("penso")
        risposta = dialogo.rispondi(SESSIONE, resto or testo)
        _fase("parlo")
        parla(risposta)
        _scarta_audio_della_voce(leggi)
        primo = False


def _ciclo():
    try:
        _ciclo_vero()
    except Exception as e:  # per esempio componenti non installati: si vede nella pagina e nel registro
        stato["errore"] = "non parte: " + type(e).__name__
        stato["in_ascolto"] = False
        logs.log_error(e, "ascolto: avvio")


def _ciclo_vero():
    global _parlando_fino
    import numpy as np
    import sounddevice as sd
    from ._oww import VAD, Model, download_models

    try:
        model = Model(wakeword_models=[PAROLA], inference_framework="onnx")
    except Exception:  # primo avvio: scarica i modelli (pochi MB, una volta)
        download_models([PAROLA])
        model = Model(wakeword_models=[PAROLA], inference_framework="onnx")
    vad = VAD()
    ultimo = 0.0
    while True:
        if not stato["attivo"]:
            stato["in_ascolto"] = False
            time.sleep(1)
            continue
        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCCO, device=config.ASCOLTO_DISPOSITIVO or None) as s:
                stato["errore"] = ""
                stato["in_ascolto"] = True
                leggi = lambda: s.read(BLOCCO)[0][:, 0].copy()
                while stato["attivo"]:
                    blocco = leggi()
                    if time.time() < _parlando_fino:  # Jarvis sta parlando: non si ascolta
                        continue
                    if model.predict(blocco).get(PAROLA, 0) >= config.ASCOLTO_SOGLIA and time.time() - ultimo > 2:
                        gestisci_chiamata(leggi, vad)
                        model.reset()
                        ultimo = time.time()
            stato["in_ascolto"] = False
        except Exception as e:  # microfono scollegato o occupato (con le cuffie bluetooth capita al cambio audio): riprova subito
            stato["in_ascolto"] = False
            stato["errore"] = type(e).__name__
            if time.time() - stato["ultimo_errore_log"] > 60:
                stato["ultimo_errore_log"] = time.time()
                logs.log_error(e, "ascolto: microfono")
            time.sleep(2)


def avvia():
    if config.ENABLE_ASCOLTO:
        threading.Thread(target=_ciclo, daemon=True).start()
        if sys.platform == "win32":
            threading.Thread(target=_scorciatoia, daemon=True).start()
