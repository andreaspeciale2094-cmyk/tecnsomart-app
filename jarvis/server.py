from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, brain, config, logs, memory, scheduler, voice


@asynccontextmanager
async def lifespan(app):
    if config.ENABLE_AGENTS:
        scheduler.start()
    yield


app = FastAPI(title="Jarvis", lifespan=lifespan)
_sessions: dict[str, list] = {}
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
    history = _sessions.setdefault(body.session, [])
    before = len(history)
    history.append({"role": "user", "content": body.message})
    try:
        reply, log = brain.think(history)
    except Exception as e:  # errore chiaro in italiano; la storia torna com'era prima
        del history[before:]
        return {"reply": logs.handle(e), "tools": [], "error": True}
    if len(history) > config.MAX_HISTORY:
        # Conversazione lunga: ripartiamo da una storia pulita con solo gli ultimi scambi in testo.
        # (Togliere pezzi dall'inizio invaliderebbe i "pensieri" di Claude e darebbe errore.)
        recent = []
        for m in history:
            if isinstance(m["content"], str):
                recent.append({"role": m["role"], "content": m["content"]})
            elif m["role"] == "assistant":
                txt = "".join(getattr(b, "text", "") for b in m["content"] if getattr(b, "type", None) == "text").strip()
                if txt:
                    recent.append({"role": "assistant", "content": txt})
        recent = recent[-10:]
        while recent and recent[0]["role"] != "user":
            recent.pop(0)
        history[:] = recent
    return {"reply": reply, "tools": log}


class Speak(BaseModel):
    text: str


@app.post("/api/tts")
def tts(body: Speak):
    if not voice.tts_available():
        return JSONResponse({"error": "TTS non configurato"}, status_code=404)
    return Response(voice.synthesize(body.text), media_type="audio/mpeg")


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
