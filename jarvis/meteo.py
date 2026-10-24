"""Meteo per il riquadro dell'ora (Open-Meteo: gratuito, senza chiave). La posizione viene dal PC (la pagina la chiede al browser, con il tuo permesso);
se manca, dall'indirizzo internet (solo la citta', approssimata); METEO_CITTA in .env, se c'e', vince su tutto. Posizione solo sul PC (memoria/posizione.json),
arrotondata a circa 1 km, mai nei registri ne' in GitHub."""
import json
from pathlib import Path

import httpx

from . import config

FILE_POS = Path(__file__).parent.parent / "memoria" / "posizione.json"
_posto: dict = {}
_pos: dict = {}      # {"lat":..,"lon":..,"citta":..} dal browser
_ip: dict = {}       # ricavata dall'indirizzo internet, rifatta ogni tanto

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


def imposta_posizione(lat: float, lon: float):
    """Posizione data dal browser del PC (con permesso): arrotondata, salvata solo in locale."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("posizione non valida")
    _pos.clear()
    _pos.update({"lat": round(lat, 2), "lon": round(lon, 2)})
    try:
        FILE_POS.parent.mkdir(parents=True, exist_ok=True)
        FILE_POS.write_text(json.dumps(_pos), encoding="utf-8")
    except OSError:
        pass


def _carica():
    if not _pos and FILE_POS.exists():
        try:
            _pos.update(json.loads(FILE_POS.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass


def _nome_luogo(lat: float, lon: float) -> str:
    chiave = f"{lat},{lon}"
    if chiave not in _posto:
        try:
            r = httpx.get("https://api.bigdatacloud.net/data/reverse-geocode-client", params={"latitude": lat, "longitude": lon, "localityLanguage": "it"}, timeout=8).json()
            _posto[chiave] = r.get("city") or r.get("locality") or r.get("principalSubdivision") or "qui"
        except (httpx.HTTPError, ValueError):
            return "qui"
    return _posto[chiave]


def _da_internet():
    """Ripiego: citta' approssimata dall'indirizzo internet (non e' preciso, ma non chiede permessi)."""
    if "lat" not in _ip:
        r = httpx.get("https://ipwho.is/", timeout=8).json()
        if r.get("success") is False or "latitude" not in r:
            return None
        _ip.update({"lat": r["latitude"], "lon": r["longitude"], "citta": r.get("city") or "qui"})
    return _ip


def _dove():
    if config.METEO_CITTA:
        p = _trova(config.METEO_CITTA)
        return (p[0], p[1], p[2]) if p else None
    _carica()
    if "lat" in _pos:
        return (_pos["lat"], _pos["lon"], _nome_luogo(_pos["lat"], _pos["lon"]))
    ip = _da_internet()
    return (ip["lat"], ip["lon"], ip["citta"]) if ip else None


def oggi():
    """Temperatura adesso, minima/massima di oggi e probabilita' di pioggia. None se non si sa dove sei o manca internet."""
    p = _dove()
    if not p:
        return None
    d = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
        "latitude": p[0], "longitude": p[1], "timezone": "auto", "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max", "forecast_days": 1}).json()
    c, g = d["current"], d["daily"]
    parola, cat = _CODICI.get(int(c["weather_code"]), ("variabile", "nuvole"))
    return {"citta": p[2], "temp": round(c["temperature_2m"]), "cond": parola, "cat": cat, "min": round(g["temperature_2m_min"][0]), "max": round(g["temperature_2m_max"][0]),
            "pioggia": g["precipitation_probability_max"][0]}


def domani():
    """Domani: parola, minima/massima, probabilita' di pioggia e temperatura alle 7 e alle 13 (per chi parte presto). None se non si sa dove sei o manca internet."""
    p = _dove()
    if not p:
        return None
    d = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
        "latitude": p[0], "longitude": p[1], "timezone": "auto", "forecast_days": 2,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max", "hourly": "temperature_2m,precipitation_probability"}).json()
    g, h = d["daily"], d["hourly"]
    parola, _ = _CODICI.get(int(g["weather_code"][1]), ("variabile", "nuvole"))
    ore = {t[11:13]: i for i, t in enumerate(h["time"]) if t[:10] == g["time"][1]}
    def alle(ora: str):
        i = ore.get(ora)
        return (round(h["temperature_2m"][i]), h["precipitation_probability"][i]) if i is not None else None
    return {"citta": p[2], "cond": parola, "min": round(g["temperature_2m_min"][1]), "max": round(g["temperature_2m_max"][1]),
            "pioggia": g["precipitation_probability_max"][1], "alle7": alle("07"), "alle13": alle("13")}


def frase_domani() -> str:
    """Una frase per l'agente 'domani': se piove, gradi alla partenza presto, parola del tempo. Vuota se non c'e' il meteo."""
    try:
        m = domani()
    except Exception:
        return ""
    if not m:
        return ""
    parti = [f"Domani {m['cond']}, {m['min']} gradi di minima e {m['max']} di massima"]
    if m["pioggia"] >= 40:
        parti.append(f"pioggia probabile ({m['pioggia']}%): porta l'ombrello")
    elif m["alle7"] and m["alle7"][1] >= 50:
        parti.append("alle 7 potrebbe piovere")
    elif m["alle7"] and m["alle7"][0] <= 5:
        parti.append(f"alle 7 fa freddo, {m['alle7'][0]} gradi")
    return ", ".join(parti) + "."
