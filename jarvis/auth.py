import hashlib
import hmac
import time
from collections import defaultdict

from . import config

COOKIE = "jarvis_auth"
_attempts: dict[str, list[float]] = defaultdict(list)


def enabled() -> bool:
    return bool(config.PASSWORD)


def token() -> str:
    return hmac.new(config.PASSWORD.encode(), b"jarvis-session", hashlib.sha256).hexdigest()


def valid(cookie: str | None) -> bool:
    return not enabled() or (cookie is not None and hmac.compare_digest(cookie, token()))


def check_password(pw: str, ip: str) -> bool:
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < 60]
    if len(_attempts[ip]) >= 5:
        return False  # troppi tentativi
    _attempts[ip].append(now)
    return hmac.compare_digest(pw.encode(), config.PASSWORD.encode())
