import time as _t
_T0 = _t.time()  # per misurare quanto ci mette ad accendersi
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
import json
import threading
import time

from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agenti, ascolto, auth, interazioni, vigile, voce_id, barra, benvenuto, meteo, tools, brain, config, fase, logs, pannello, memory, pulizia, scheduler, sessions, telegram_bot, voice, whatsapp


def _avvio_scaglionato():
    """Quando il PC si accende e' tutto occupato: se Jarvis caricasse insieme voce, ascolto, WhatsApp, Telegram e posta, la schermata arriverebbe piu' tardi.
    Prima si vede la pagina; gli altri pezzi partono a pochi secondi di distanza l'uno dall'altro."""
    passi = [
        (4, lambda: whatsapp.avvia_per_ricevere() if config.ENABLE_WHATSAPP_LEGGI else None),  # per ricevere i messaggi deve essere sempre acceso
        (5, benvenuto.avvia),
        (7, lambda: voice.prepare_fixed()),
        (9, ascolto.avvia),
        (11, tools.avvia_cache),  # agenda, posta e WhatsApp sempre pronti per i quadri veloci
        (13, telegram_bot.avvia),
        (14, pulizia.avvia),
        (15, vigile.avvia),
    ]
    t0 = _t.time()
    for quando, f in passi:
        attesa = quando - (_t.time() - t0)
        if attesa > 0:
            _t.sleep(attesa)
        try:
            f()
        except Exception as e:
            logs.log_error(e, "avvio a scaglioni")


@asynccontextmanager
async def lifespan(app):
    if config.ENABLE_AGENTS:
        scheduler.start()
    CHIUDI_TOKEN.parent.mkdir(parents=True, exist_ok=True)
    CHIUDI_TOKEN.write_text(secrets.token_hex(24), encoding="utf-8")
    pannello.scalda()  # i dati dei riquadri si preparano subito, in sottofondo
    threading.Thread(target=_avvio_scaglionato, daemon=True).start()  # il resto parte a scaglioni: prima la schermata, poi il resto
    logs.log_route(f"AVVIO: server pronto in {_t.time() - _T0:.1f} s (dall'inizio del caricamento dei programmi)")
    yield
    pulizia.alla_chiusura()


CHIUDI_TOKEN = Path(__file__).parent.parent / "memoria" / "chiudi.token"
app = FastAPI(title="Jarvis", lifespan=lifespan)
_sessions = sessions.histories
STATIC = Path(__file__).parent.parent / "static"
PUBLIC = {"/api/login", "/api/auth", "/api/chiudi", "/api/davanti", "/api/stato_ascolto"}  # /api/chiudi ha un controllo suo: solo dal PC e con chiave


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api") and request.url.path not in PUBLIC:
        if not auth.valid(request.cookies.get(auth.COOKIE)):
            return JSONResponse({"error": "login richiesto"}, status_code=401)
    risposta = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        risposta.headers["Cache-Control"] = "no-cache"  # il browser controlla sempre se la pagina e' cambiata: dopo una copia dei file si vede subito la versione nuova
    return risposta


@app.post("/api/chiudi")
def chiudi(request: Request):
    """Spegne Jarvis con calma (usato da spegni_jarvis.bat): solo da questo PC e con la chiave in memoria/chiudi.token."""
    chiave = CHIUDI_TOKEN.read_text(encoding="utf-8").strip() if CHIUDI_TOKEN.exists() else ""
    if (request.client.host if request.client else "") not in ("127.0.0.1", "::1") or not chiave or not secrets.compare_digest(request.headers.get("x-chiudi", ""), chiave):
        return JSONResponse({"error": "non autorizzato"}, status_code=403)

    def fine():
        try:
            (CHIUDI_TOKEN.parent / "spegnimento_voluto.flag").write_text("1", encoding="utf-8")  # dice al sorvegliante (se Jarvis e' al posto del desktop) che non e' un guasto
        except OSError:
            pass
        try:
            pulizia.alla_chiusura()
            whatsapp.chiudi_helper()
        finally:
            os._exit(0)

    threading.Timer(0.5, fine).start()
    return {"ok": True}


@app.post("/api/davanti")
def davanti(request: Request):
    """Porta Jarvis davanti a tutto (lo chiede il sorvegliante quando parte il desktop di Windows dietro di lui): solo da questo PC e con la chiave in memoria/chiudi.token."""
    chiave = CHIUDI_TOKEN.read_text(encoding="utf-8").strip() if CHIUDI_TOKEN.exists() else ""
    if (request.client.host if request.client else "") not in ("127.0.0.1", "::1") or not chiave or not secrets.compare_digest(request.headers.get("x-chiudi", ""), chiave):
        return JSONResponse({"error": "non autorizzato"}, status_code=403)
    return {"ok": barra.porta_jarvis_davanti()}


class Login(BaseModel):
    password: str


@app.get("/api/auth")
def auth_status(request: Request):
    return {"required": auth.enabled(), "ok": auth.valid(request.cookies.get(auth.COOKIE))}


@app.post("/api/login")
def login(body: Login, request: Request, response: Response):
    if not auth.check_password(body.password, request.client.host if request.client else "?"):
        return JSONResponse({"error": "password errata o troppi tentativi"}, status_code=401)
    response.set_cookie(auth.COOKIE, auth.token(), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return {"ok": True}


@app.get("/api/config")
def get_config():
    return {"tts": voice.tts_available(), "stt": voice.stt_available(), "user": config.USER_NAME, "ascolto_stanza": config.ENABLE_ASCOLTO}


@app.get("/api/stato_ascolto")
def stato_ascolto(request: Request):
    """Solo la fase dell'ascolto (nessun testo), per lo sfondo animato del PC: accessibile solo da questo computer, senza login."""
    if (request.client.host if request.client else "") not in ("127.0.0.1", "::1"):
        return JSONResponse({"error": "non autorizzato"}, status_code=403)
    return {"fase": ascolto.stato["fase"] or fase.leggi(), "in_ascolto": ascolto.stato["in_ascolto"], "attivo": ascolto.stato["attivo"]}


@app.get("/api/vigile")
def vigile_avvisi():
    """Gli avvisi dell'agente vigile non ancora letti (solo testo breve, in memoria)."""
    return {"avvisi": vigile.avvisi()}


class Letto(BaseModel):
    id: str


@app.post("/api/vigile/letto")
def vigile_letto(body: Letto):
    vigile.segna_letto(body.id)
    return {"ok": True}


@app.get("/api/agenti")
def agenti_stato():
    """Quali agenti stanno lavorando adesso (solo etichette): serve alla rete neurale per mostrarli."""
    return {"agenti": agenti.stato_pubblico()}


@app.get("/api/pannello")
def get_pannello():
    return pannello.dati()


def _dal_pc(request: Request) -> bool:
    """Vero solo se la richiesta arriva da questo PC (non dal telefono tramite Tailscale, che passa da 127.0.0.1 ma aggiunge queste intestazioni)."""
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1") and not any(
        h in request.headers for h in ("x-forwarded-for", "tailscale-user-login", "forwarded"))


@app.get("/api/barra")
def barra_dati(request: Request):
    """Barra in basso: finestre aperte. Solo sul PC Windows e solo dal PC."""
    if not (barra.disponibile() and _dal_pc(request)):
        return {"attiva": False}
    return {"attiva": True, "finestre": barra.finestre(), "shell_jarvis": not barra.explorer_attivo()}


@app.get("/api/desk")
def desk_dati(request: Request):
    """Icone del desktop di Jarvis (a sinistra). Solo dal PC."""
    if not (barra.disponibile() and _dal_pc(request)):
        return {"attiva": False}
    return {"attiva": True, "app": [{"nome": a["nome"], "icona": barra.icona_di(a)} for a in barra.scrivania()]}


@app.get("/api/desk/catalogo")
def desk_catalogo(request: Request):
    if not (barra.disponibile() and _dal_pc(request)):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    return {"nomi": barra.catalogo()}


@app.get("/api/cerca")
def cerca_pc(q: str, request: Request):
    if not (barra.disponibile() and _dal_pc(request)):
        return {"attiva": False, "voci": []}
    return {"attiva": True, **barra.cerca(q[:80])}


class Posizione(BaseModel):
    lat: float
    lon: float


@app.post("/api/posizione")
def posizione(body: Posizione, request: Request):
    """La posizione del PC (la manda la pagina, col permesso del browser) serve solo per il meteo. Dal telefono non si accetta."""
    if not _dal_pc(request):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        meteo.imposta_posizione(body.lat, body.lon)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    pannello.azzera("meteo")
    return {"ok": True}


class Voce(BaseModel):
    tipo: str
    id: str


@app.post("/api/cerca/apri")
def cerca_apri(body: Voce, request: Request):
    if not (barra.disponibile() and _dal_pc(request)):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        barra.apri_voce(body.tipo, body.id)
    except (ValueError, OSError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


class BarraAzione(BaseModel):
    nome: str = ""
    id: int = 0


@app.post("/api/desk/{azione}")
def desk_azione(azione: str, body: BarraAzione, request: Request):
    if not (barra.disponibile() and _dal_pc(request)):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        {"apri": barra.apri_desktop, "aggiungi": barra.aggiungi, "togli": barra.togli}[azione](body.nome)
    except KeyError:
        return JSONResponse({"error": "azione sconosciuta"}, status_code=404)
    except (ValueError, OSError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


@app.post("/api/barra/{azione}")
def barra_azione(azione: str, body: BarraAzione, request: Request):
    if not (barra.disponibile() and _dal_pc(request)):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        if azione == "porta":
            barra.porta_davanti(body.id)
        elif azione == "start":
            barra.apri_start()
        elif azione == "schermo":
            barra.schermo_intero_alterna()
        elif azione == "windows":
            barra.desktop_windows()
        else:
            return JSONResponse({"error": "azione sconosciuta"}, status_code=404)
    except (ValueError, OSError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


def _pc_o_errore(request: Request):
    return None if _dal_pc(request) else JSONResponse({"error": "Questa funzione e' disponibile solo dal PC."}, status_code=403)


def _chiama(f, *a):
    """Esegue una funzione dei riquadri cliccabili e traduce gli errori in messaggi semplici."""
    try:
        return f(*a)
    except (whatsapp.WhatsAppError, voce_id.VoceError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except ValueError as e:
        return JSONResponse({"error": str(e) or "Dati non validi."}, status_code=400)


@app.get("/api/impegni")
def api_impegni(request: Request, data: str = ""):
    return _pc_o_errore(request) or _chiama(interazioni.impegni, data)


@app.get("/api/whatsapp/rubrica")
def api_wa_rubrica(request: Request):
    return _pc_o_errore(request) or {"nomi": interazioni.rubrica_nomi()}


@app.get("/api/whatsapp/chat")
def api_wa_chat(request: Request):
    return _pc_o_errore(request) or _chiama(lambda: {"chat": interazioni.chat_lista()})


@app.get("/api/whatsapp/messaggi")
def api_wa_messaggi(request: Request, id: str):
    return _pc_o_errore(request) or _chiama(interazioni.chat_messaggi, id)


@app.post("/api/whatsapp/app")
def api_wa_app(request: Request):
    """Apre l'app WhatsApp del PC e la porta davanti (solo la apre: non invia niente). Se l'app non c'e', apre WhatsApp Web."""
    def apri():
        try:
            os.startfile("whatsapp://")  # type: ignore[attr-defined]
            threading.Thread(target=barra.porta_davanti_per_nome, args=("whatsapp",), daemon=True).start()
        except (OSError, AttributeError):
            import webbrowser
            webbrowser.open("https://web.whatsapp.com/")
        return {"ok": True}
    return _pc_o_errore(request) or _chiama(apri)


class WaPrepara(BaseModel):
    a: str
    testo: str


@app.post("/api/whatsapp/prepara")
def api_wa_prepara(body: WaPrepara, request: Request):
    return _pc_o_errore(request) or _chiama(interazioni.prepara, body.a[:60], body.testo[:1000])


class WaInvia(BaseModel):
    pid: str


@app.post("/api/whatsapp/invia")
def api_wa_invia(body: WaInvia, request: Request):
    """Parte solo dal pulsante 'Invia' dopo che Andrea ha visto il testo."""
    return _pc_o_errore(request) or _chiama(lambda: {"messaggio": interazioni.invia_dopo_si(body.pid)})


class WaSalva(BaseModel):
    chat_id: str
    nome: str


@app.post("/api/whatsapp/salva")
def api_wa_salva(body: WaSalva, request: Request):
    return _pc_o_errore(request) or _chiama(lambda: {"messaggio": interazioni.salva_da_chat(body.chat_id, body.nome)})


class Fase(BaseModel):
    fase: str = ""


@app.post("/api/fase")
def imposta_fase(body: Fase):
    """La pagina dice cosa sta facendo (ti ascolto, penso, parlo), cosi' lo sfondo del PC si muove anche per la voce della pagina."""
    fase.imposta(body.fase)
    return {"ok": True}


@app.get("/api/ascolto")
def ascolto_stato():
    """Stato vero dell'ascolto in stanza (il programma che sente 'Hey Jarvis' anche a pagina chiusa)."""
    return {"abilitato": config.ENABLE_ASCOLTO, "in_ascolto": ascolto.stato["in_ascolto"], "attivo": ascolto.stato["attivo"],
            "risvegli": ascolto.stato["risvegli"], "errore": ascolto.stato["errore"], "stt": voice.stt_available(), "fase": ascolto.stato["fase"],
            "livello": round(ascolto.stato["livello"], 2), "punteggio": round(ascolto.stato["punteggio"], 2), "dispositivo": ascolto.stato["dispositivo"], "soglia": ascolto.soglia(),
            "voce_attiva": voce_id.attiva(), "voce_campioni": voce_id.stato()["campioni"], "voce_punteggio": ascolto.stato["voce_punteggio"], "voce_esito": ascolto.stato["voce_esito"],
            "voce_soglia": voce_id.soglia()}


@app.get("/api/ascolto/microfoni")
def ascolto_microfoni(request: Request):
    if not _dal_pc(request):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        return {"nomi": ascolto.microfoni(), "scelto": ascolto.stato["dispositivo"]}
    except Exception:
        return JSONResponse({"error": "non riesco a leggere i microfoni"}, status_code=500)


class Sensibilita(BaseModel):
    valore: float


@app.post("/api/ascolto/soglia")
def ascolto_soglia(body: Sensibilita, request: Request):
    """Cambia quanto e' facile svegliare Jarvis con 'Hey Jarvis' (solo dal PC)."""
    if not _dal_pc(request):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        ascolto.imposta_soglia(body.valore)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True, "soglia": ascolto.soglia()}


def _voce(f):
    """Esegue un'operazione sulla voce: gli imprevisti diventano un messaggio semplice (e un rigo nel registro degli errori, senza audio)."""
    try:
        return f()
    except (voce_id.VoceError, ValueError, whatsapp.WhatsAppError):
        raise
    except Exception as e:
        logs.log_error(e, "riconoscimento voce")
        raise voce_id.VoceError("Il riconoscimento della voce ha avuto un problema: riprova.")


@app.get("/api/voce")
def api_voce(request: Request):
    return _pc_o_errore(request) or voce_id.stato()


@app.post("/api/voce/prepara")
def api_voce_prepara(request: Request):
    """Controlla il programma e scarica il modello (una volta, ~26 MB)."""
    def f():
        voce_id.prepara()
        voce_id._estrattore()  # lo carica ora: la prima registrazione non aspetta
        return voce_id.stato()
    return _pc_o_errore(request) or _chiama(_voce, f)


class VoceRegistra(BaseModel):
    secondi: float = 6


@app.post("/api/voce/registra")
def api_voce_registra(body: VoceRegistra, request: Request):
    """Registra la voce di Andrea dal microfono dell'ascolto e ne ricava un'impronta (tenuta in attesa finche' non si salva)."""
    return _pc_o_errore(request) or _chiama(_voce, lambda: voce_id.aggiungi_registrazione(ascolto.registra_secondi(body.secondi)))


@app.post("/api/voce/salva")
def api_voce_salva(request: Request):
    return _pc_o_errore(request) or _chiama(_voce, lambda: {"campioni": voce_id.conferma()})


@app.post("/api/voce/annulla")
def api_voce_annulla(request: Request):
    return _pc_o_errore(request) or _chiama(lambda: (voce_id.annulla(), {"ok": True})[1])


@app.post("/api/voce/azzera")
def api_voce_azzera(request: Request):
    return _pc_o_errore(request) or _chiama(lambda: {"messaggio": voce_id.azzera()})


class VoceInterruttore(BaseModel):
    attivo: bool


@app.post("/api/voce/interruttore")
def api_voce_interruttore(body: VoceInterruttore, request: Request):
    return _pc_o_errore(request) or _chiama(lambda: (voce_id.interruttore(body.attivo), {"attivo": voce_id.attiva()})[1])


class VoceSoglia(BaseModel):
    valore: float


@app.post("/api/voce/soglia")
def api_voce_soglia(body: VoceSoglia, request: Request):
    return _pc_o_errore(request) or _chiama(lambda: (voce_id.imposta_soglia(body.valore), {"soglia": voce_id.soglia()})[1])


class Microfono(BaseModel):
    nome: str = ""


@app.post("/api/ascolto/microfono")
def ascolto_microfono(body: Microfono, request: Request):
    """Sceglie il microfono dell'ascolto in stanza (solo dal PC)."""
    if not _dal_pc(request):
        return JSONResponse({"error": "non disponibile"}, status_code=403)
    try:
        ascolto.scegli_microfono(body.nome)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True}


class Chat(BaseModel):
    session: str = "default"
    message: str


@app.post("/api/chat")
def chat(body: Chat):
    history, before = sessions.start_request(body.session, body.message)
    try:
        reply, log = brain.think(history, summary=sessions.summaries.get(body.session, ""))
    except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
        del history[before:]
        return {"reply": logs.handle(e), "tools": [], "error": True}
    sessions.compact_in_background(body.session)
    return {"reply": reply, "tools": log}


@app.post("/api/chat_stream")
def chat_stream(body: Chat):
    """Risposta a pezzi (una riga JSON per evento), cosi' la voce parte alla prima frase."""
    history, before = sessions.start_request(body.session, body.message)

    def events():
        t0, first = time.time(), None
        try:
            for ev in brain.think_stream(history, summary=sessions.summaries.get(body.session, "")):
                if ev["type"] == "text" and first is None:
                    first = time.time() - t0
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
            del history[before:]
            yield json.dumps({"type": "error", "message": logs.handle(e)}, ensure_ascii=False) + "\n"
            return
        logs.log_latency(first, time.time() - t0)
        sessions.compact_in_background(body.session)

    return StreamingResponse(events(), media_type="application/x-ndjson")


class Speak(BaseModel):
    text: str


@app.post("/api/tts")
def tts(body: Speak):
    if not voice.tts_available():
        return JSONResponse({"error": "TTS non configurato"}, status_code=404)
    return Response(voice.synthesize(body.text), media_type="audio/mpeg")


class Note(BaseModel):
    tag: str
    detail: str = ""


@app.post("/api/note")
def note(body: Note):
    """La pagina scrive nel registro cosa ha fatto (solo etichette note, mai il testo delle conversazioni)."""
    if body.tag in ("frasi", "fissa", "stato", "stato_mancante"):
        logs.log_page(body.tag, body.detail)
    return {"ok": True}


@app.get("/api/fixed")
def fixed_list():
    return {"phrases": list(voice.FIXED_PHRASES) if voice.tts_available() else []}


@app.get("/api/fixed/{key}")
def fixed_audio(key: str):
    if key not in voice.FIXED_PHRASES:
        return JSONResponse({"error": "frase sconosciuta"}, status_code=404)
    try:
        return Response(voice.fixed_audio(key), media_type="audio/mpeg")
    except Exception:
        return JSONResponse({"error": "voce non disponibile"}, status_code=503)


@app.post("/api/stt")
async def stt(request: Request):
    if not voice.stt_available():
        return JSONResponse({"error": "STT non configurato"}, status_code=404)
    return {"text": voice.transcribe(await request.body(), request.headers.get("content-type", "audio/webm"))}


@app.get("/api/inbox")
def inbox():
    return scheduler.get_inbox()


class Ids(BaseModel):
    ids: list[int]


@app.post("/api/inbox/read")
def inbox_read(body: Ids):
    scheduler.mark_read(body.ids)
    return {"ok": True}


@app.get("/api/tasks")
def tasks():
    return scheduler.list_jobs()


@app.get("/api/memory")
def get_memory():
    return memory.recall(limit=200)


@app.delete("/api/memory/{fact_id}")
def del_memory(fact_id: int):
    return {"deleted": memory.forget(fact_id)}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
