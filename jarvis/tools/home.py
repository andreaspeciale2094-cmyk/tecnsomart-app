"""Domotica via Home Assistant REST API."""
import httpx
from .. import config

SCHEMAS = [
    {
        "name": "home_state",
        "description": "Stato di un dispositivo Home Assistant (es. light.salotto). Senza entity_id elenca tutte le entita'.",
        "input_schema": {"type": "object", "properties": {"entity_id": {"type": "string"}}},
    },
    {
        "name": "home_call",
        "description": "Chiama un servizio Home Assistant, es. domain=light, service=turn_on, entity_id=light.salotto.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "service": {"type": "string"},
                "entity_id": {"type": "string"},
                "data": {"type": "object"},
            },
            "required": ["domain", "service", "entity_id"],
        },
    },
]


def _req(method, path, **kw):
    if not (config.HA_URL and config.HA_TOKEN):
        return "Home Assistant non configurato (HA_URL / HA_TOKEN nel .env)."
    r = httpx.request(method, f"{config.HA_URL}/api/{path}", headers={"Authorization": f"Bearer {config.HA_TOKEN}"}, timeout=15, **kw)
    r.raise_for_status()
    return r.json()


def home_state(entity_id: str = ""):
    res = _req("GET", f"states/{entity_id}" if entity_id else "states")
    if isinstance(res, list):
        return [f"{s['entity_id']}: {s['state']}" for s in res][:300]
    return res


def home_call(domain: str, service: str, entity_id: str, data: dict | None = None):
    _req("POST", f"services/{domain}/{service}", json={"entity_id": entity_id, **(data or {})})
    return "Fatto."


HANDLERS = {"home_state": home_state, "home_call": home_call}
