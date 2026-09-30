from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import brain, config, memory

app = FastAPI(title="Jarvis")
_sessions: dict[str, list] = {}
STATIC = Path(__file__).parent.parent / "static"


class Chat(BaseModel):
    session: str = "default"
    message: str


@app.post("/api/chat")
def chat(body: Chat):
    history = _sessions.setdefault(body.session, [])
    history.append({"role": "user", "content": body.message})
    reply, log = brain.think(history)
    # Limita la storia senza spezzare coppie tool_use/tool_result: tieni solo i turni "testuali" iniziali.
    if len(history) > config.MAX_HISTORY:
        cut = len(history) - config.MAX_HISTORY
        while cut < len(history) and not (
            history[cut]["role"] == "user" and isinstance(history[cut]["content"], str)
        ):
            cut += 1
        del history[:cut]
    return {"reply": reply, "tools": log}


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
