from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
import json
import threading
import time

from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ascolto, auth, brain, config, logs, memory, pulizia, scheduler, sessions, telegram_bot, voice


@asynccontextmanager
async def lifespan(app):
    if config.ENABLE_AGENTS:
        scheduler.start()
    threading.Thread(target=voice.prepare_fixed, daemon=True).start()
    pulizia.avvia()
    telegram_bot.avvia()
    ascolto.avvia()
    yield
    pulizia.alla_chiusura()


app = FastAPI(title="Jarvis", lifespan=lifespan)
_sessions = sessions.histories
STATIC = Path(__file__).parent.parent / "static"
PUBLIC = {"/api/login", "/api/auth"}


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api") and request.url.path not in PUBLIC:
        if not auth.valid(request.cookies.get(auth.COOKIE)):
            return JSONResponse({"error": "login richiesto"}, status_code=401)
    return await call_next(request)


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
    return {"tts": voice.tts_available(), "stt": voice.stt_available(), "user": config.USER_NAME}


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
