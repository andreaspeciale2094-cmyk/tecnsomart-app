"""Ascolto in stanza: Jarvis resta in ascolto e risponde SOLO se lo chiami ("Hey Jarvis", rilevatore locale gratuito openWakeWord).
Tre filtri: 1) rilevatore della parola, tutto sul PC e senza costi; 2) solo dopo il risveglio registra la frase e si ferma quando smetti
di parlare (rilevatore di voce locale); 3) solo allora trascrizione a pagamento e cervello. L'audio non viene mai scritto su disco ne' nei
registri: resta in memoria (RAM) il tempo della frase. Mentre Jarvis parla non ascolta (evita di svegliarsi con la propria voce)."""
import collections
import contextlib
import io
import os
import queue
import random
import re
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

from . import config, dialogo, logs, ritmo, voce_id, voice

SESSIONE = "ascolto"
RATE = 16000
BLOCCO = 1280  # 80 ms
PAROLA = "hey_jarvis"
stato = {"attivo": True, "risvegli": 0, "errore": "", "in_ascolto": False, "fase": "", "ultimo_errore_log": 0.0,
         "livello": 0.0, "punteggio": 0.0, "dispositivo": "", "riapri": False,
         "registra": None, "voce_punteggio": None, "voce_esito": ""}
FILE_MIC = Path(__file__).parent.parent / "memoria" / "ascolto_microfono.txt"  # microfono scelto dalla pagina (solo sul PC)
FILE_SOGLIA = Path(__file__).parent.parent / "memoria" / "ascolto_soglia.txt"  # sensibilita' scelta dalla pagina (vince su ASCOLTO_SOGLIA del .env)
_soglia = {"v": None}


def _fase(f: str):
    stato["fase"] = f
_parlando_fino = 0.0
_interrompi = threading.Event()  # alzata = la voce di Jarvis deve fermarsi subito (e le frasi gia' pronte vengono buttate)


def interrompi():
    """Ferma subito la voce di Jarvis, comprese le frasi gia' pronte che aspettano il loro turno."""
    global _parlando_fino
    _interrompi.set()
    _parlando_fino = min(_parlando_fino, time.time() + 0.3)


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
    u.RegisterHotKey(None, 3, 0x0001 | 0x0002, ord("S"))  # Alt + Ctrl + S: ferma subito la voce di Jarvis
    msg = wintypes.MSG()
    while u.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312 and msg.wParam == 3:  # Ctrl+Alt+S: stop alla voce
            interrompi()
        elif msg.message == 0x0312 and msg.wParam == 2:  # Ctrl+Alt+V: apre la finestra di Jarvis
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
    if sys.platform != "win32" or _interrompi.is_set():
        return
    import ctypes

    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(mp3)
        mci = ctypes.windll.winmm.mciSendStringW
        alias = f"jv{time.time_ns()}"
        env = ritmo.inviluppo(mp3)  # forza della voce, per far muovere la sfera a tempo
        try:
            mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
            mci(f"play {alias}", None, 0, None)
            ritmo.inizia(env)
            fine = time.time() + 120  # mai oltre due minuti, anche se la scheda audio (cuffie bluetooth) si pianta
            buf = ctypes.create_unicode_buffer(32)
            time.sleep(0.15)
            while time.time() < fine:
                if _interrompi.is_set():
                    break
                mci(f"status {alias} mode", buf, 31, None)
                if buf.value != "playing":
                    break
                time.sleep(0.1)
        finally:
            ritmo.fine()
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
    _interrompi.clear()
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


_taglio = {"detto": "", "intero": "", "quando": 0.0}  # cosa si e' sentito prima di un'interruzione (solo RAM, mai nei registri)


def nota_interruzione() -> str:
    """Se Andrea ha appena interrotto Jarvis, una nota per il cervello: cosa era stato detto e cosa mancava. Si usa una volta sola."""
    t = dict(_taglio)
    _taglio.update(detto="", intero="", quando=0.0)
    if not t["intero"] or time.time() - t["quando"] > 120:
        return ""
    return ("[Andrea ti ha interrotto mentre parlavi. Ha sentito solo: «" + (t["detto"].strip() or "niente") + "». Aveva ancora da sentire: «"
            + t["intero"][len(t["detto"]):].strip()[:600] + "». Rispondi prima a quello che dice ora; se serve riprendi da dove sei stato interrotto "
            "senza ripetere cio' che ha gia' sentito, altrimenti lascia perdere il resto.]\n")


def parla_stream(frammenti, filler: str = ""):
    """Parla MENTRE Claude scrive: ogni frase completa va subito alla voce, e mentre una si sente le successive si preparano.
    Se la prima frase tarda piu' di ASCOLTO_ATTESA secondi (predefinito 2,5) parte una frase fissa gia' registrata, scelta a caso: mai silenzio, ma senza ripetere sempre la stessa."""
    global _parlando_fino
    _interrompi.clear()
    _parlando_fino = time.time() + 600
    q_testi, q_audio = queue.Queue(), queue.Queue()
    primo = threading.Event()
    frasi, dette = [], []  # tutte le frasi previste e quelle arrivate in fondo alla voce

    def sintetizza():
        while True:
            t = q_testi.get()
            if t is None:
                q_audio.put(None)
                return
            if _interrompi.is_set():
                continue  # interrotto: le frasi che mancano non si dicono
            try:
                q_audio.put((t, voice.synthesize(t)))
            except Exception as e:
                logs.log_voice("ascolto", e)

    def suona():
        while True:
            x = q_audio.get()
            if x is None:
                return
            if _interrompi.is_set():
                continue
            try:
                if isinstance(x, tuple):
                    _suona(x[1])
                    if not _interrompi.is_set():
                        dette.append(x[0])  # la frase tagliata a meta' non conta come sentita
                else:
                    _suona(x)  # frase fissa d'attesa
            except Exception as e:
                logs.log_voice("ascolto", e)

    def riempitivo():
        if not primo.is_set():
            try:
                q_audio.put(voice.fixed_audio(filler or random.choice(("attesa1", "attesa2", "attesa3", "attesa4"))))
            except Exception:
                pass

    th = [threading.Thread(target=sintetizza, daemon=True), threading.Thread(target=suona, daemon=True)]
    for t in th:
        t.start()
    timer = threading.Timer(config.ASCOLTO_ATTESA, riempitivo)
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
                    frasi.append(frase)
                    q_testi.put(frase)
        if buf.strip() and parlato < 700:
            primo.set()
            frasi.append(buf.strip())
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
        if _interrompi.is_set() and frasi:
            _taglio.update(detto=" ".join(dette), intero=" ".join(frasi), quando=time.time())


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


def registra_frase(leggi, vad, attesa: float = 5.0, breve: bool = False) -> list | None:
    """Registra finche' non smetti di parlare. leggi() ritorna un blocco di 1280 campioni.
    None se nessuno parla entro `attesa` secondi, o se c'e' solo un rumore brevissimo.
    breve=True: accetta anche una parola sola (un "si'" dura meno di mezzo secondo): serve quando Jarvis aspetta una conferma."""
    minimo = 2 if breve else 3
    frames, voce, silenzio, parlato, t0, t_voce = [], 0, 0, False, time.time(), None
    while True:
        blocco = leggi()
        frames.append(blocco)
        if float(vad.predict(blocco, 640)) > (0.35 if breve else 0.5):
            voce += 1
            parlato, silenzio = voce >= (1 if breve else 2), 0
            if parlato and t_voce is None:
                t_voce = time.time()  # da qui si contano i 15 secondi massimi di una frase
        else:
            silenzio += 1
        if parlato and silenzio >= config.ASCOLTO_PAUSA_FINE:  # silenzio di fine frase (0,7 s circa): ha finito
            return frames if voce >= minimo else None
        if t_voce is not None and time.time() - t_voce > 15:  # una frase non dura piu' di 15 s (prima il limite partiva dall'inizio dell'attesa: la conversazione aperta si chiudeva dopo 15 s invece che dopo ASCOLTO_FINESTRA)
            return frames if parlato and voce >= minimo else None
        if not parlato and time.time() - t0 > attesa:
            return None


_CHIUSURA = re.compile(r"^\W*(?:ok\W+|va bene\W+)?(?:grazie(?: mille)?|basta(?: cos[iì])?|a dopo|ci sentiamo|per ora (?:basta|nient'altro)|nient'altro|puoi smettere|ciao)\W*$", re.IGNORECASE)
_STOP_VOCE = re.compile(r"^\W*(?:stop|basta|zitto|zitta|fermati|ferma|silenzio|aspetta|un attimo|un momento)\W*$", re.IGNORECASE)
_INVENTATE = re.compile(r"sottotitoli|amara\.org|iscriviti|grazie a tutti|alla prossima|ci vediamo al prossimo|buona visione", re.IGNORECASE)  # frasi che Whisper inventa sul silenzio

_CHIAMATA = re.compile(r"^\W*(?:(?:hey|hei|ehi|ei|ehi|ciao|ok|okay)\W+)?(?:jarvis|j\.a\.r\.v\.i\.s\.?|giarvis|garvis|giarvi[sz])\b\W*", re.IGNORECASE)


def togli_chiamata(testo: str) -> str:
    """Toglie 'Hey Jarvis' dall'inizio della frase trascritta."""
    return _CHIAMATA.sub("", testo.strip(), count=1).strip()


class VoceNonRiconosciuta(Exception):
    """Chi ha parlato non e' Andrea (solo se il riconoscimento della voce e' acceso)."""


def _controlla_voce(blocchi: list):
    """Confronta la voce con l'impronta di Andrea. Registra solo il punteggio (mai l'audio ne' le parole)."""
    ok, p = voce_id.verifica(blocchi)
    if p is not None:
        stato["voce_punteggio"] = p
        stato["voce_esito"] = "ok" if ok else "no"
        if not ok:
            logs.log_route(f"ASCOLTO: voce non riconosciuta (somiglianza {p}, serve {voce_id.soglia()})")
    else:
        stato["voce_esito"] = ""
    if ok is False:
        raise VoceNonRiconosciuta()


def _ascolta(leggi, vad, attesa: float, pre=None) -> str | None:
    _fase("ti ascolto")
    frames = registra_frase(leggi, vad, attesa, breve=bool(_chiamata_pronta["id"] or _chiamata_scelta["nomi"]))  # se aspetta un 'si'' per una chiamata, basta anche una parola brevissima
    blocchi = list(pre or []) + list(frames or [])
    if blocchi:
        _controlla_voce(blocchi)  # la prima volta si controlla anche "Hey Jarvis" detto un attimo prima
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


_RIEMPITIVI = r"(?:ok|okay|senti|dai|scusa|ehi|jarvis|puoi|potresti|riesci a|vorrei|voglio|devo|fammi|mi|fai|farmi|per favore|per piacere|adesso|ora|subito)"
_CHIAMA = re.compile(r"^\W*(?:" + _RIEMPITIVI + r"\W+){0,4}(?:chiama(?:re|mi|lo|la)?|telefona(?:re)?(?:\s+a)?|(?:una\s+)?(?:telefonata|chiamata)\s+a)\W+(?:a\s+|il\s+|la\s+|l'\s*)?(.+?)\W*$", re.IGNORECASE)
_CODA_CHIAMA = re.compile(r"(?:\s+(?:al|sul|dal|col|con il|con|sul mio|dal mio|con il mio)\s+(?:mio\s+)?(?:cellulare|telefono|smartphone))?(?:\s+(?:per favore|per piacere|grazie|subito|adesso|ora))*$", re.IGNORECASE)
_AFFERMA = {"si", "sì", "certo", "ok", "okay", "vai", "esatto", "conferma", "confermo", "procedi", "chiama", "chiamalo", "chiamala", "pure", "dai", "assolutamente", "yes", "perfetto", "va", "bene", "subito", "ora", "grazie", "per", "favore", "piacere", "avanti", "fallo", "fai", "partire"}
_NEGA = {"no", "non", "aspetta", "ferma", "fermati", "annulla", "stop", "basta", "lascia", "stare", "mai", "niente", "nessuno"}


def _e_un_si(testo: str) -> bool:
    """'si'', 'si' certo', 'ok vai', 'si' chiama pure': un si' detto in modo naturale, di poche parole e senza negazioni."""
    parole = re.findall(r"[\wàèéìòù']+", testo.lower())
    if not parole or len(parole) > 5 or any(p in _NEGA for p in parole):
        return False
    return parole[0] in _AFFERMA and all(p in _AFFERMA for p in parole)


_chiamata_pronta = {"id": "", "nome": "", "t": 0.0}
VALIDITA_CONFERMA = 120  # secondi in cui la chiamata preparata aspetta il si' (a voce o con il clic sulla pagina)
_chiamata_scelta = {"nomi": [], "t": 0.0}   # piu' persone con lo stesso nome: aspetta che dica quale
_ORDINALI = {"primo": 0, "prima": 0, "uno": 0, "secondo": 1, "seconda": 1, "due": 1, "terzo": 2, "terza": 2, "tre": 2, "quarto": 3, "quarta": 3, "quattro": 3}


def chiamata_in_attesa() -> dict | None:
    """La chiamata che aspetta il si' (per la scheda con i pulsanti sulla pagina), oppure None."""
    p = _chiamata_pronta
    if not p["id"] or time.time() - p["t"] >= VALIDITA_CONFERMA:
        return None
    return {"id": p["id"], "nome": __import__("jarvis.chiamate", fromlist=["x"]).parlabile(p["nome"]), "eta": round(time.time() - p["t"], 1)}


def conferma_da_pagina(cid: str, si: bool) -> str:
    """Il clic su 'Si', chiama' (o 'No') della scheda sulla pagina vale come risposta. Solo dal PC."""
    from . import chiamate

    p = chiamata_in_attesa()
    if not p or p["id"] != cid:
        raise chiamate.ChiamataError("Quella chiamata non e' piu' in attesa.")
    if time.time() - _chiamata_pronta["t"] < 1.0:
        raise chiamate.ChiamataError("Un attimo: leggi prima a chi stai chiamando.")
    nome = _chiamata_pronta["nome"]
    _chiamata_pronta.update(id="", nome="", t=0.0)
    if not si:
        return "Va bene, non chiamo."
    chiamate.avvia(cid, da_voce=True)
    return f"Faccio partire la chiamata a {chiamate.parlabile(nome)}."


def chiamata_veloce(testo: str) -> str | None:
    """'Chiama Marco' senza passare dal cervello: prima chiede 'Chiamo Marco?', e solo con un 'si'' detto DOPO (frase successiva) fa partire la chiamata dal telefono.
    Ritorna cosa dire, oppure None se non e' una chiamata (e allora si va avanti come sempre)."""
    if not config.ENABLE_CHIAMATE:
        return None
    from . import chiamate

    t = testo.strip()
    if _chiamata_scelta["nomi"]:  # aveva chiesto 'Quale?': la risposta sceglie tra le persone elencate
        nomi, attesa = list(_chiamata_scelta["nomi"]), time.time() - _chiamata_scelta["t"]
        _chiamata_scelta.update(nomi=[], t=0.0)
        if attesa < 45:
            parole = chiamate._parole(t)
            scelti = [nomi[_ORDINALI[p]] for p in parole if p in _ORDINALI and _ORDINALI[p] < len(nomi)][:1] or \
                     [k for k in nomi if parole and set(parole) <= set(chiamate._parole(k))]
            if len(scelti) == 1:
                cid, nome_vero = chiamate.prepara_veloce("", chiave=scelti[0])
                _chiamata_pronta.update(id=cid, nome=nome_vero, t=time.time())
                return f"Chiamo {chiamate.parlabile(nome_vero)}?"
            if len(scelti) > 1:
                _chiamata_scelta.update(nomi=scelti, t=time.time())
                return "Ancora piu' di uno: " + "; ".join(chiamate.parlabile(k) for k in scelti) + ". Quale?"
    if _chiamata_pronta["id"]:
        cid, nome, attesa = _chiamata_pronta["id"], _chiamata_pronta["nome"], time.time() - _chiamata_pronta["t"]
        _chiamata_pronta.update(id="", nome="", t=0.0)  # una conferma vale una volta sola: qualunque cosa si dica dopo la azzera
        logs.log_route("CHIAMATA: risposta alla conferma " + ("scaduta (troppo tardi)" if attesa >= VALIDITA_CONFERMA else "capita come si" if _e_un_si(t) else "NON capita come si"))
        if attesa < VALIDITA_CONFERMA and _e_un_si(t):
            try:
                chiamate.avvia(cid, da_voce=True)
                return f"Faccio partire la chiamata a {chiamate.parlabile(nome)}."
            except chiamate.ChiamataError as e:
                return str(e).replace("Errore: ", "")
        if attesa < VALIDITA_CONFERMA and re.match(r"^\W*(?:no|annulla|lascia stare|fermati|stop|aspetta)\W*$", t, re.IGNORECASE):
            return "Va bene, non chiamo."
    m = _CHIAMA.match(t)
    if not m:
        return None
    logs.log_route("CHIAMATA: richiesta a voce riconosciuta")
    nome = _CODA_CHIAMA.sub("", m.group(1).strip()).strip()
    try:
        cid, nome_vero = chiamate.prepara_veloce(nome)
    except chiamate.ChiamataAmbigua as e:
        _chiamata_scelta.update(nomi=e.nomi[:4], t=time.time())
        return "Quale? " + "; ".join(chiamate.parlabile(k) for k in e.nomi[:4]) + "."
    except chiamate.ChiamataError as e:
        logs.log_route("CHIAMATA: persona non trovata in rubrica")
        return str(e)
    _chiamata_pronta.update(id=cid, nome=nome_vero, t=time.time())
    return f"Chiamo {chiamate.parlabile(nome_vero)}?"


_NEGOZI = re.compile(r"\b(?:negozi|punti vendita)\b", re.IGNORECASE)
_NEGOZI_CHIEDE = re.compile(r"(?:\bcome (?:sono|stanno|vanno)|\bandat[aoie]\b|\bnumeri\b|\bdati\b|\briepilogo\b|\bresoconto\b|\brisultati\b|\bsituazione\b|\bandamento\b|\brun\b)", re.IGNORECASE)


def negozi_veloce(testo: str) -> str | None:
    """'Come sono andati i negozi?', 'i numeri dei negozi': i numeri sono gia' pronti (li prepara l'agente negozi), si dicono subito senza passare dal cervello."""
    if not config.ENABLE_NEGOZI or len(testo) > 90:
        return None
    try:
        from . import negozi, vigile
        if not _NEGOZI.search(testo):  # 'cosa ha inserito il Ducale?': un solo negozio, nominato
            if re.search(r"\b(?:inserit|dati|numeri|com'?\s*(?:e'|è)|come (?:sta|e'|è|va)|andat|risultat|fatto|vendut)", testo, re.IGNORECASE):
                nome = negozi.trova_negozio(testo)
                if nome:
                    return negozi.parlato_negozio(nome)
            return None
        if not _NEGOZI_CHIEDE.search(testo):
            return None
        return vigile.negozi_pronto()
    except Exception as e:
        logs.log_error(e, "negozi veloce")
        return None


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


def gestisci_chiamata(leggi, vad, pre=None):
    """Dopo il risveglio: ascolta, risponde a voce, e RESTA in conversazione: finche' continui a parlare entro qualche secondo
    non serve ripetere 'Hey Jarvis'. Se dici solo 'Hey Jarvis', saluta e chiede cosa serve."""
    stato["risvegli"] += 1
    _bip()
    primo = True
    while True:
        try:
            if primo:
                testo = _ascolta(leggi, vad, 1.6, pre)  # subito dopo il nome: se non aggiungi niente, ti saluta
            else:
                testo = _ascolta(leggi, vad, float(config.ASCOLTO_FINESTRA))  # dopo una risposta resta in conversazione a lungo
        except VoceNonRiconosciuta:
            if primo:  # ha chiamato qualcun altro: niente risposta
                _fase("")
                return
            continue  # dentro la conversazione parla un'altra voce: la ignora e resta in ascolto di Andrea
        if primo:
            if testo is None:
                parla(saluto())
                _scarta_audio_della_voce(leggi)
                primo = False
                continue
        else:
            if testo is None:
                _fase("")
                return
        if not primo and _INVENTATE.search(testo) and len(testo) < 60:
            continue  # frase inventata dal riconoscimento sul silenzio o sul rumore: la scarta e continua ad ascoltare
        resto = togli_chiamata(testo)
        if _STOP_VOCE.match(resto or testo):  # "stop", "basta", "zitto"...: ferma la voce e resta in ascolto, senza rispondere
            interrompi()
            _fase("")
            _scarta_audio_della_voce(leggi)
            primo = False
            continue
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
        rapido = chiamata_veloce(resto or testo)
        if rapido is None:
            rapido = negozi_veloce(resto or testo)
        if rapido is None:
            rapido = comando_veloce(resto or testo)
        if rapido is not None:
            parla(rapido)
            _scarta_audio_della_voce(leggi)
            primo = False
            continue
        _fase("rispondo")
        risposta = dialogo.rispondi_stream(SESSIONE, nota_interruzione() + (resto or testo))
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


def soglia() -> float:
    """Quanto deve somigliare a 'Hey Jarvis' per svegliarsi: quella scelta dalla pagina, altrimenti ASCOLTO_SOGLIA."""
    if _soglia["v"] is None:
        try:
            _soglia["v"] = float(FILE_SOGLIA.read_text(encoding="utf-8").strip()) if FILE_SOGLIA.exists() else config.ASCOLTO_SOGLIA
        except (OSError, ValueError):
            _soglia["v"] = config.ASCOLTO_SOGLIA
    return _soglia["v"]


def imposta_soglia(valore: float):
    if not 0.15 <= valore <= 0.9:
        raise ValueError("Sensibilita' non valida.")
    FILE_SOGLIA.parent.mkdir(parents=True, exist_ok=True)
    FILE_SOGLIA.write_text(str(round(valore, 2)), encoding="utf-8")
    _soglia["v"] = round(valore, 2)


def registra_secondi(secondi: float) -> list:
    """Registra dal microfono dell'ascolto per `secondi` (serve a imparare la voce con lo STESSO microfono che poi la riconoscera')."""
    if not stato["in_ascolto"]:
        raise ValueError("L'ascolto non e' attivo: accendilo e riprova.")
    if stato["registra"] is not None:
        raise ValueError("Sto gia' registrando.")
    stato["registra"] = []
    try:
        time.sleep(max(1.0, min(float(secondi), 12.0)))
    finally:
        bloc, stato["registra"] = stato["registra"], None
    return bloc


def microfoni() -> list[str]:
    """Nomi dei microfoni del PC, senza doppioni tra i vari sistemi audio di Windows (si preferisce MME: Windows adatta da solo la frequenza,
    e' quello che funziona meglio con le cuffie bluetooth)."""
    import sounddevice as sd
    try:
        mme = next((i for i, h in enumerate(sd.query_hostapis()) if "MME" in h["name"]), None)
    except Exception:
        mme = None
    visti, out = set(), []
    for pref in ([mme] if mme is not None else []) + [None]:
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and (pref is None or d["hostapi"] == pref):
                chiave = d["name"][:30].lower()
                if chiave not in visti:
                    visti.add(chiave)
                    out.append(d["name"])
        if out:
            break
    return out


def scegli_microfono(nome: str):
    """Sceglie il microfono dell'ascolto (ricordato in memoria/ascolto_microfono.txt) e riapre l'ascolto subito. Nome vuoto = quello predefinito."""
    if nome and nome not in microfoni():
        raise ValueError("Microfono non trovato.")
    FILE_MIC.parent.mkdir(parents=True, exist_ok=True)
    FILE_MIC.write_text(nome, encoding="utf-8")
    stato["riapri"] = True


def _dispositivo(sd):
    """Il microfono da usare: quello scelto dalla pagina, poi ASCOLTO_DISPOSITIVO (numero o nome), altrimenti quello predefinito di Windows."""
    voluto = ""
    try:
        voluto = FILE_MIC.read_text(encoding="utf-8").strip() if FILE_MIC.exists() else ""
    except OSError:
        pass
    voluto = voluto or str(config.ASCOLTO_DISPOSITIVO or "").strip()
    if not voluto:
        return None
    if voluto.isdigit():
        return int(voluto)  # il numero scritto nel .env e' testo: va trasformato, altrimenti si cercherebbe un microfono con quel nome
    for i, d in enumerate(sd.query_devices()):  # per nome: il primo microfono che comincia cosi' (i nomi cambiano un po' tra i sistemi audio)
        if d["max_input_channels"] > 0 and d["name"].lower().startswith(voluto[:30].lower()):
            return i
    return None


@contextlib.contextmanager
def _apri_microfono(sd, dispositivo):
    """Apre il microfono a 16000 Hz; se non si puo' (cuffie bluetooth) lo apre alla sua frequenza: poi _leggi_blocco converte."""
    rate = RATE
    try:
        s = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCCO, device=dispositivo)
        s.start()
    except sd.PortAudioError as primo:
        try:
            info = sd.query_devices(dispositivo if dispositivo is not None else sd.default.device[0])
            rate = int(info["default_samplerate"])
        except Exception:
            raise primo
        if rate == RATE:
            raise primo
        logs.log_route(f"ASCOLTO: il microfono non accetta {RATE} Hz, lo apro a {rate} Hz e converto")
        s = sd.InputStream(samplerate=rate, channels=1, dtype="int16", blocksize=int(BLOCCO * rate / RATE), device=dispositivo)
        s.start()
    try:
        yield s, rate
    finally:
        try:
            s.stop()
        finally:
            s.close()


_PAROLE_CUFFIE = ("headset", "hands-free", "handsfree", "bluetooth", "cuffie", "auricolari", "buds", "airpods")


def _leggi_blocco(s, rate, np, guadagno=1.0):
    """Un blocco di BLOCCO campioni a 16000 Hz, comunque sia aperto il microfono. Le cuffie bluetooth hanno il microfono piano: guadagno."""
    if rate == RATE:
        x = s.read(BLOCCO)[0][:, 0].astype(np.float32)
    else:
        grezzo = s.read(int(round(BLOCCO * rate / RATE)))[0][:, 0].astype(np.float32)
        x = np.interp(np.linspace(0, len(grezzo) - 1, BLOCCO), np.arange(len(grezzo)), grezzo)
    if guadagno != 1.0:
        x = x * guadagno
    return np.clip(x, -32768, 32767).astype(np.int16)


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
            dispositivo = _dispositivo(sd)
            with _apri_microfono(sd, dispositivo) as (s, rate):
                stato["errore"] = ""
                stato["in_ascolto"] = True
                stato["riapri"] = False
                try:
                    stato["dispositivo"] = sd.query_devices(dispositivo if dispositivo is not None else sd.default.device[0])["name"]
                except Exception:
                    stato["dispositivo"] = ""
                con_cuffie = any(p in str(stato["dispositivo"]).lower() for p in _PAROLE_CUFFIE)
                interruzione = {"true": True, "false": False}.get(str(config.ASCOLTO_INTERRUZIONE).strip().lower(), True)  # "Hey Jarvis" mentre parla lo ferma (soglia piu' alta); con le casse non si usa la sola voce, che farebbe sentire a Jarvis se stesso
                voce_sopra = 0  # blocchi di voce di fila mentre Jarvis parla (solo cuffie: nessun rischio di sentire se stesso)
                guadagno = 3.0 if any(p in str(stato["dispositivo"]).lower() for p in _PAROLE_CUFFIE) else 1.0  # microfono delle cuffie bluetooth: piano, lo si alza
                leggi = lambda: _leggi_blocco(s, rate, np, guadagno)
                ring = collections.deque(maxlen=26)  # gli ultimi ~2 secondi: dentro c'e' "Hey Jarvis", servono per riconoscere chi lo ha detto
                while stato["attivo"] and not stato["riapri"]:
                    blocco = leggi()
                    if stato["registra"] is not None:  # la pagina sta registrando la voce di Andrea (impara la mia voce)
                        stato["registra"].append(blocco)
                        continue
                    stato["livello"] = 0.5 * stato["livello"] + 0.5 * min(1.0, float(np.abs(blocco.astype(np.int32)).max()) / 12000)  # per l'indicatore nella pagina
                    parlando = time.time() < _parlando_fino
                    if parlando and not interruzione:  # Jarvis sta parlando: senza cuffie non si ascolta (sentirebbe se stesso)
                        continue
                    ring.append(blocco)
                    if parlando and str(config.ASCOLTO_INTERRUZIONE).strip().lower() != "false" and (con_cuffie or voce_id.attiva()):
                        # Parli sopra la voce di Jarvis: con le cuffie basta ~0,3 s di voce; con le casse la voce deve essere QUELLA DI ANDREA (impronta), controllata ogni ~1,2 s di voce
                        voce_sopra = voce_sopra + 1 if float(vad.predict(blocco, 640)) > 0.6 else voce_sopra
                        if voce_sopra >= (4 if con_cuffie else 15):
                            voce_sopra = 0
                            if con_cuffie:
                                e_lui = True
                            else:
                                e_lui, p_voce = voce_id.verifica(list(ring))
                                if not e_lui:
                                    logs.log_route(f"ASCOLTO: voce sopra Jarvis non e' la tua (somiglianza {p_voce})")
                            if e_lui:
                                interrompi()
                                logs.log_route("ASCOLTO: interrotto parlando sopra (" + ("cuffie" if con_cuffie else "voce riconosciuta") + ")")
                                try:
                                    gestisci_chiamata(leggi, vad, list(ring))
                                except sd.PortAudioError:
                                    raise
                                except Exception as e:
                                    _fase("")
                                    logs.log_error(e, "ascolto: conversazione")
                                model.reset()
                                ultimo = time.time()
                                continue
                    else:
                        voce_sopra = 0
                    punteggio = float(model.predict(blocco).get(PAROLA, 0))
                    stato["punteggio"] = max(punteggio, stato["punteggio"] * 0.97)
                    if punteggio >= (max(soglia() + 0.25, 0.6) if parlando else soglia()) and time.time() - ultimo > 2:
                        if parlando:  # "Hey Jarvis" detto mentre parla: si ferma e ascolta
                            interrompi()
                            logs.log_route("ASCOLTO: interrotto a voce")
                        try:
                            gestisci_chiamata(leggi, vad, list(ring))
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
