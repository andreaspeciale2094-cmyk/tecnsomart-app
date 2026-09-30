"""Embedding per la memoria semantica.
Con OPENAI_API_KEY usa text-embedding-3-small; altrimenti un embedding locale a n-grammi di caratteri
(nessuna dipendenza, funziona bene per sinonimi morfologici ma non per sinonimi puri)."""
import hashlib
import math
import re

import httpx
from . import config

DIM = 512
KIND = "openai" if config.OPENAI_API_KEY else "hash"
THRESHOLD = 0.30 if KIND == "openai" else 0.22


def _hash_embed(text: str) -> list[float]:
    t = re.sub(r"\s+", " ", text.lower().strip())
    grams = [t[i : i + 3] for i in range(max(1, len(t) - 2))] + t.split()
    v = [0.0] * DIM
    for g in grams:
        h = int(hashlib.md5(g.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0 if (h >> 64) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str]) -> list[list[float]]:
    if KIND == "openai":
        try:
            r = httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                json={"model": "text-embedding-3-small", "input": texts},
                timeout=30,
            )
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]
        except Exception:
            pass
    return [_hash_embed(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / ((math.sqrt(sum(x * x for x in a)) or 1) * (math.sqrt(sum(y * y for y in b)) or 1))
