"""Tabellone in tempo reale del sito ufficiale Trenord (sola lettura, nessun dato personale): partenze di una stazione con ritardo o cancellazione.
Si legge la stessa pagina che il sito usa per 'Arrivi e partenze' (station-details?mirCode=...). Il formato non e' documentato: si cercano i blocchi 'Partenza alle HH:MM'
e dentro ognuno parole come ritardo / soppresso / cancellato. Se la pagina cambia e non si trova niente, lo si dice (e si salva la pagina in memoria/trenord_ultima.html per sistemarlo)."""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from pathlib import Path

import httpx

BASE = "https://www.trenord.it/rest/render"
CODICI_NOTI = {"gaggiano": "S01063"}   # visto dal sito (23/10); gli altri si cercano con l'elenco stazioni
ULTIMA = Path(__file__).parent.parent / "memoria" / "trenord_ultima.html"
_cache: dict[str, tuple[float, object]] = {}
_INTEST = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept-Language": "it-IT,it;q=0.9"}


class TrenordError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


class _Testo(HTMLParser):
    def __init__(self):
        super().__init__()
        self.righe: list[str] = []
        self._salta = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._salta += 1
        if tag in ("br", "p", "div", "li", "tr", "td", "span", "h1", "h2", "h3", "h4", "a", "section", "article"):
            self.righe.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._salta:
            self._salta -= 1

    def handle_data(self, data):
        if not self._salta and data.strip():
            self.righe.append(data.strip())


def righe_di(html: str) -> list[str]:
    p = _Testo()
    p.feed(html)
    testo = " ".join(p.righe).replace(" \n ", "\n")
    out = []
    for r in re.split(r"\s*\n\s*", testo):
        r = re.sub(r"\s+", " ", r).strip()
        if r:
            out.append(r)
    return out


def _get(percorso: str, durata: float = 0.0) -> str:
    if durata and percorso in _cache and time.time() - _cache[percorso][0] < durata:
        return _cache[percorso][1]  # type: ignore[return-value]
    try:
        r = httpx.get(BASE + percorso, headers=_INTEST, timeout=20, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError:
        raise TrenordError("Non riesco a leggere il sito Trenord adesso: controlla internet o riprova tra poco.")
    _cache[percorso] = (time.time(), r.text)
    return r.text


def codice_stazione(nome: str) -> str:
    n = nome.strip().lower()
    if n in CODICI_NOTI:
        return CODICI_NOTI[n]
    testo = _get(f"/stationslist?query={nome.strip()}&template=discovery", durata=86400)
    for m in re.finditer(r"S\d{5}", testo):
        vicino = testo[max(0, m.start() - 300): m.end() + 300].lower()
        if n in vicino:
            return m.group(0)
    raise TrenordError(f"Non trovo la stazione '{nome}' sul sito Trenord.")


_PARTENZA = re.compile(r"\bpartenza\s+alle\s+(\d{1,2}):(\d{2})", re.I)
_ARRIVO = re.compile(r"\barrivo\s+alle\s+(\d{1,2}):(\d{2})", re.I)
_RITARDO = re.compile(r"ritardo[^\d]{0,20}(\d{1,3})|(\d{1,3})\s*(?:min|minuti)\s*(?:di\s*)?ritardo", re.I)
_CANC = re.compile(r"soppress|cancellat|non effettuat", re.I)


_SEPARA = re.compile(r"vedi dettagli|mostra altri|treni in (?:partenza|arrivo)", re.I)
_LINEA = re.compile(r"^([A-Z]{1,3}\d{0,2})\s+(\d{3,6})$")


def analizza(html: str) -> list[dict]:
    """Le partenze: ogni treno e' una 'scheda' (es. 'S9 24948 | Diretto a SARONNO | Partenza alle 13:12 | Vedi dettagli'); le schede sono separate da 'Vedi dettagli'.
    Ritorna [{'compOrarioPartenza','destinazione','ritardo','provvedimento','numeroTreno','linea','binario...','testo'}] (stessa forma di ViaggiaTreno). Gli arrivi si scartano."""
    righe = righe_di(html)
    schede, cur = [], []
    for r in righe:
        if _SEPARA.search(r):
            if cur:
                schede.append(cur)
            cur = []
        else:
            cur.append(r)
    if cur:
        schede.append(cur)
    risultato = []
    for sc in schede:
        testo = " | ".join(sc)
        m = _PARTENZA.search(testo)
        if not m or _ARRIVO.search(testo):
            continue
        linea, num = "", ""
        for r in sc:
            ml = _LINEA.match(r)
            if ml:
                linea, num = ml.group(1), ml.group(2)
                break
        if not num:
            mn = re.search(r"\b(\d{4,6})\b", testo)
            num = mn.group(1) if mn else ""
        dest = re.search(r"diretto\s+a\s+([^|]+)", testo, re.I)
        rit = _RITARDO.search(testo)
        bin_ = re.search(r"binario\s*:?\s*(\w+)", testo, re.I)
        risultato.append({"compOrarioPartenza": f"{int(m.group(1)):02d}:{m.group(2)}", "destinazione": (dest.group(1).strip() if dest else "")[:60], "ritardo": int(rit.group(1) or rit.group(2)) if rit else 0,
                          "provvedimento": 1 if _CANC.search(testo) else 0, "numeroTreno": num, "linea": linea,
                          "binarioProgrammatoPartenzaDescrizione": bin_.group(1) if bin_ else "", "testo": testo[:200]})
    return risultato


def partenze(nome_stazione: str) -> list[dict]:
    codice = codice_stazione(nome_stazione)
    html = _get(f"/station-details?mirCode={codice}&mxp=false&L=0&map_zoom=", durata=45)
    ris = analizza(html)
    if not ris:
        try:
            ULTIMA.parent.mkdir(parents=True, exist_ok=True)
            ULTIMA.write_text(html[:200000], encoding="utf-8")
        except OSError:
            pass
        raise TrenordError("Il sito Trenord ha risposto ma non riesco a leggere le partenze (la pagina potrebbe essere cambiata).")
    return ris
