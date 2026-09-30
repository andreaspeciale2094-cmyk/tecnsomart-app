import re
import httpx

SCHEMAS = [
    {
        "name": "fetch_url",
        "description": "Scarica una pagina web e ne restituisce il testo. Per ricerche usa anche web_search se disponibile.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
]


def fetch_url(url: str) -> str:
    r = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "Mozilla/5.0 Jarvis"})
    r.raise_for_status()
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", r.text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:15000]


HANDLERS = {"fetch_url": fetch_url}
