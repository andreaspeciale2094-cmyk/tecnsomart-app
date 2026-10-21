"""Meteo per il riquadro dell'ora (Open-Meteo: gratuito, senza chiave). Serve solo il nome della citta' in .env (METEO_CITTA); non si salva niente."""
import httpx

from . import config

_posto: dict = {}

# codice meteo internazionale -> (parola, categoria per il disegno)
_CODICI = {0: ("sereno", "sole"), 1: ("quasi sereno", "sole"), 2: ("poco nuvoloso", "nuvole"), 3: ("coperto", "nuvole"), 45: ("nebbia", "nebbia"), 48: ("nebbia", "nebbia"),
           51: ("pioggerella", "pioggia"), 53: ("pioggerella", "pioggia"), 55: ("pioggerella", "pioggia"), 56: ("pioggia gelata", "pioggia"), 57: ("pioggia gelata", "pioggia"),
           61: ("pioggia debole", "pioggia"), 63: ("pioggia", "pioggia"), 65: ("pioggia forte", "pioggia"), 66: ("pioggia gelata", "pioggia"), 67: ("pioggia gelata", "pioggia"),
           71: ("neve debole", "neve"), 73: ("neve", "neve"), 75: ("neve forte", "neve"), 77: ("neve", "neve"), 80: ("rovesci", "pioggia"), 81: ("rovesci", "pioggia"),
           82: ("rovesci forti", "pioggia"), 85: ("rovesci di neve", "neve"), 86: ("rovesci di neve", "neve"), 95: ("temporale", "temporale"), 96: ("temporale e grandine", "temporale"),
           99: ("temporale e grandine", "temporale")}


def _trova(citta: str):
    if citta not in _posto:
        r = httpx.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": citta, "count": 1, "language": "it"}, timeout=8).json().get("results") or []
        _posto[citta] = (r[0]["latitude"], r[0]["longitude"], r[0]["name"]) if r else None
    return _posto[citta]


def oggi():
    """Temperatura adesso, minima/massima di oggi e probabilita' di pioggia. None se manca la citta' o internet."""
    if not config.METEO_CITTA:
        return None
    p = _trova(config.METEO_CITTA)
    if not p:
        return None
    d = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
        "latitude": p[0], "longitude": p[1], "timezone": "auto", "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max", "forecast_days": 1}).json()
    c, g = d["current"], d["daily"]
    parola, cat = _CODICI.get(int(c["weather_code"]), ("variabile", "nuvole"))
    return {"citta": p[2], "temp": round(c["temperature_2m"]), "cond": parola, "cat": cat, "min": round(g["temperature_2m_min"][0]), "max": round(g["temperature_2m_max"][0]),
            "pioggia": g["precipitation_probability_max"][0]}
