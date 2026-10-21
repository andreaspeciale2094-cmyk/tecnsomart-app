"""Ascolto in stanza: Jarvis resta in ascolto e risponde SOLO se lo chiami ("Hey Jarvis", rilevatore locale gratuito openWakeWord).
Tre filtri: 1) rilevatore della parola, tutto sul PC e senza costi; 2) solo dopo il risveglio registra la frase e si ferma quando smetti
di parlare (rilevatore di voce locale); 3) solo allora trascrizione a pagamento e cervello. L'audio non viene mai scritto su disco ne' nei
registri: resta in memoria (RAM) il tempo della frase. Mentre Jarvis parla non ascolta (evita di svegliarsi con la propria voce)."""
import io
import os
import queue
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
    u.RegisterHotKey(None, 2, 0x0001 | 0x0002, ord("V"))  # Alt + Ctrl + V: apre Jarvis a tutto schermo, da qualunque programma
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312 and msg.wParam == 2:  # Ctrl+Alt+V: apre la finestra di Jarvis
            try:
                import subprocess
                from pathlib import Path

                subprocess.Popen(["wscript.exe", str(Path(__file__).parent.parent / "scripts" / "apri_jarvis.vbs")])
            except Exception:
                pass
        elif msg.message == 0x0312:  # WM_HOTKEY
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
        alias = f"jv{time.time_ns()}"
        try:
            mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
            mci(f"play {alias}", None, 0, None)
            fine = time.time() + 120  # mai oltre due minuti, anche se la scheda audio (cuffie bluetooth) si pianta
            buf = ctypes.create_unicode_buffer(32)
            time.sleep(0.15)
            while time.time() < fine:
                mci(f"status {alias} mode", buf, 31, None)
                if buf.value != "playing":
                    break
                time.sleep(0.1)
        finally:
            mci(f"stop {alias}", None, 0, None)
            mci(f"close {alias}", None, 0, None)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _bip():
    if sys.platform == "win32":
        import winsound

        winsound.Beep(880, 110)


_cache_frasi: dict[str, bytes] = {}


def parla(testo: str):
    global _parlando_fino
    testo = testo.strip()
    if len(testo) > 700:  # le risposte lunghe si leggono sulla pagina: a voce solo l'inizio
        testo = testo[:700].rsplit(".", 1)[0] + ". Il resto lo trovi sulla pagina."
    _parlando_fino = time.time() + 600
    try:
        if len(testo) <= 70:  # frasi brevi e ripetute (saluto, "Va bene."): si preparano una volta sola e poi partono subito
            if testo not in _cache_frasi:
                _cache_frasi[testo] = voice.synthesize(testo)
            _suona(_cache_frasi[testo])
        else:
            _suona(voice.synthesize(testo))
    except Exception as e:
        logs.log_voice("ascolto", e)
    finally:
        _parlando_fino = time.time() + 0.8  # un attimo di silenzio dopo la voce


_FRASE = re.compile(r"(.+?[.!?])(?:\s+|$)", re.S)


def parla_stream(frammenti, filler: str = "attesa3"):
    """Parla MENTRE Claude scrive: ogni frase completa va subito alla voce, e mentre una si sente le successive si preparano.
    Se la prima frase tarda piu' di 0,8 secondi parte una frase fissa gia' registrata ('Subito.'): mai silenzio."""
    global _parlando_fino
    _parlando_fino = time.time() + 600
    q_testi, q_audio = queue.Queue(), queue.Queue()
    primo = threading.Event()

    def sintetizza():
        while True:
            t = q_testi.get()
            if t is None:
                q_audio.put(None)
                return
            try:
                q_audio.put(voice.synthesize(t))
            except Exception as e:
                logs.log_voice("ascolto", e)

    def suona():
        while True:
            a = q_audio.get()
            if a is None:
                return
            try:
                _suona(a)
            except Exception as e:
                logs.log_voice("ascolto", e)

    def riempitivo():
        if not primo.is_set():
            try:
                q_audio.put(voice.fixed_audio(filler))
            except Exception:
                pass

    th = [threading.Thread(target=sintetizza, daemon=True), threading.Thread(target=suona, daemon=True)]
    for t in th:
        t.start()
    timer = threading.Timer(0.8, riempitivo)
    timer.daemon = True
    timer.start()
    buf, parlato = "", 0
    try:
        for pezzo in frammenti:
            buf += pezzo
            while True:
                m = _FRASE.match(buf)
                if not m or len(m.group(1)) < 12:
                    break
                frase, buf = m.group(1), buf[m.end():]
                if parlato < 700:
                    parlato += len(frase)
                    primo.set()
                    q_testi.put(frase)
        if buf.strip() and parlato < 700:
            primo.set()
            q_testi.put(buf.strip())
        if parlato >= 700:
            primo.set()
            q_testi.put("Il resto lo trovi sulla pagina.")
    finally:
        primo.set()
        timer.cancel()
        q_testi.put(None)
        th[1].join()
        _parlando_fino = time.time() + 0.8


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
        if parlato and silenzio >= config.ASCOLTO_PAUSA_FINE:  # silenzio di fine frase (0,7 s circa): ha finito
            return frames if voce >= 3 else None
        if time.time() - t0 > 15:
            return frames if parlato and voce >= 3 else None
        if not parlato and time.time() - t0 > attesa:
            return None


_CHIUSURA = re.compile(r"^\W*(?:ok\W+|va bene\W+)?(?:grazie(?: mille)?|basta(?: cos[iì])?|a dopo|ci sentiamo|per ora (?:basta|nient'altro)|nient'altro|puoi smettere|ciao)\W*$", re.IGNORECASE)
_INVENTATE = re.compile(r"sottotitoli|amara\.org|iscriviti|grazie a tutti|alla prossima|ci vediamo al prossimo|buona visione", re.IGNORECASE)  # frasi che Whisper inventa sul silenzio

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


_APRI = re.compile(r"^\W*(?:apri|avvia|lancia|fammi partire)(?:mi)?\W+(?:l[ao']\s*|il\s+|un[ao]?\s+|gli\s+)?(.+?)\W*$", re.IGNORECASE)
_VOLUME = re.compile(r"^\W*(?:(?:alza|aumenta|metti piu' alto)\s+(?:il\s+)?volume|volume\s+(?:su|piu'? alto)|(?:abbassa|diminuisci)\s+(?:il\s+)?volume|volume\s+(?:giu'?|piu'? basso)|muto|togli l'audio|metti il muto)\W*$", re.IGNORECASE)


def comando_veloce(testo: str) -> str | None:
    """Comandi semplici e innocui (apri un'app, volume, blocca, desktop): partono subito, senza aspettare il cervello.
    Ritorna cosa dire, oppure None se non e' un comando semplice."""
    if not config.ENABLE_PC_COMANDI:
        return None
    from . import pc_comandi as pc

    t = testo.strip()
    try:
        m = _APRI.match(t)
        if m:
            nome = re.sub(r"\s+(?:per favore|per piacere|grazie|subito|adesso|ora)$", "", m.group(1).strip(), flags=re.IGNORECASE)
            return pc.apri(nome)
        if _VOLUME.match(t):
            tl = t.lower()
            return pc.volume("muto" if ("muto" in tl or "audio" in tl) else "su" if any(w in tl for w in ("alza", "aumenta", "alto", "su")) else "giu")
        if re.match(r"^\W*(?:mostra(?:mi)? il desktop|minimizza tutto)\W*$", t, re.IGNORECASE):
            return pc.mostra_desktop()
        if re.match(r"^\W*blocca(?: il)?(?: pc| computer| schermo)?\W*$", t, re.IGNORECASE):
            return pc.blocca()
    except pc.PcError as e:
        return str(e)
    return None


def saluto(ora=None) -> str:
    """'Buongiorno Andrea, dimmi cosa posso fare per te.' (di mattina) oppure 'Buonasera ...' (dopo le 18)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    h = (ora or datetime.now(ZoneInfo(config.FUSO))).hour
    parte = "Buongiorno" if 5 <= h < 18 else "Buonasera"
    nome = f" {config.USER_NAME}" if config.USER_NAME else ""
    return f"{parte}{nome}, dimmi cosa posso fare per te."


def gestisci_chiamata(leggi, vad):
    """Dopo il risveglio: ascolta, risponde a voce, e RESTA in conversazione: finche' continui a parlare entro qualche secondo
    non serve ripetere 'Hey Jarvis'. Se dici solo 'Hey Jarvis', saluta e chiede cosa serve."""
    stato["risvegli"] += 1
    _bip()
    primo = True
    while True:
        if primo:
            testo = _ascolta(leggi, vad, 1.6)  # subito dopo il nome: se non aggiungi niente, ti saluta
            if testo is None:
                parla(saluto())
                _scarta_audio_della_voce(leggi)
                primo = False
                continue
        else:
            testo = _ascolta(leggi, vad, float(config.ASCOLTO_FINESTRA))  # dopo una risposta resta in conversazione a lungo
            if testo is None:
                _fase("")
                return
        if not primo and _INVENTATE.search(testo) and len(testo) < 60:
            continue  # frase inventata dal riconoscimento sul silenzio o sul rumore: la scarta e continua ad ascoltare
        resto = togli_chiamata(testo)
        if not primo and _CHIUSURA.match(resto or testo):  # "grazie", "basta cosi'", "a dopo": chiude la conversazione
            parla("Va bene.")
            _scarta_audio_della_voce(leggi)
            _fase("")
            return
        if primo and not resto:  # ha detto solo il nome: lo saluta e aspetta il comando
            parla(saluto())
            _scarta_audio_della_voce(leggi)
            primo = False
            continue
        rapido = comando_veloce(resto or testo)
        if rapido is not None:
            parla(rapido)
            _scarta_audio_della_voce(leggi)
            primo = False
            continue
        _fase("rispondo")
        risposta = dialogo.rispondi_stream(SESSIONE, resto or testo)
        parla_stream(risposta)
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
                        try:
                            gestisci_chiamata(leggi, vad)
                        except sd.PortAudioError:
                            raise  # il microfono e' saltato: lo riapre il ciclo esterno
                        except Exception as e:  # un errore nella conversazione non deve spegnere l'ascolto
                            _fase("")
                            logs.log_error(e, "ascolto: conversazione")
                        model.reset()
                        ultimo = time.time()
            stato["in_ascolto"] = False
        except Exception as e:  # microfono scollegato o occupato (con le cuffie bluetooth capita al cambio audio): riprova subito
            stato["in_ascolto"] = False
            stato["errore"] = type(e).__name__
            if time.time() - stato["ultimo_errore_log"] > 60:
                stato["ultimo_errore_log"] = time.time()
                logs.log_error(e, "ascolto: microfono")
            try:  # le cuffie bluetooth cambiano numero di dispositivo: si rilegge l'elenco prima di riprovare
                sd._terminate()
                sd._initialize()
            except Exception:
                pass
            time.sleep(2)


def avvia():
    if config.ENABLE_ASCOLTO:
        threading.Thread(target=_ciclo, daemon=True).start()
        if sys.platform == "win32":
            threading.Thread(target=_scorciatoia, daemon=True).start()
