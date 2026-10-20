"""Conto personale di Andrea in SOLA LETTURA, tramite Enable Banking (open banking).
Il permesso chiesto alla banca e' solo 'informazioni sul conto': pagare e' impossibile. Chiave privata e sessione stanno solo
sul PC (memoria/banca/). I movimenti non vengono salvati su disco ne' scritti nei registri: si leggono quando servono."""
import json
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import httpx

from . import config

API = "https://api.enablebanking.com"
CARTELLA = Path(__file__).parent.parent / "memoria" / "banca"
SESSIONE = CARTELLA / "sessione.json"
GIORNI_PERMESSO = 90
FINESTRA = 89  # le banche non danno piu' di 90 giorni di storico senza una nuova autorizzazione
VALIDITA_CACHE = 60 * 60  # secondi: la banca limita le richieste al giorno, quindi si legge una volta e si riusa
_cache: dict = {}  # solo in memoria (RAM): niente viene scritto su disco
avviso = ""  # se i dati sono vecchi perche' la banca ha detto 'troppe richieste'
  # la banca chiede di rinnovare il permesso circa ogni 90 giorni


class BancaError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _chiave() -> bytes:
    f = Path(config.BANCA_CHIAVE) if config.BANCA_CHIAVE else CARTELLA / "chiave.pem"
    if not config.BANCA_APP_ID or not f.exists():
        raise BancaError("Manca il collegamento con il servizio della banca: nel .env servono ENABLE_BANKING_APP_ID e il file della chiave in memoria\\banca\\chiave.pem.")
    return f.read_bytes()


def _token() -> str:
    import jwt  # PyJWT (con cryptography)
    ora = int(time.time())
    return jwt.encode({"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": ora, "exp": ora + 3600}, _chiave(),
                      algorithm="RS256", headers={"typ": "JWT", "kid": config.BANCA_APP_ID})


_psu: dict = {}


def _intestazioni_presente() -> dict:
    """Quando Andrea e' davanti a Jarvis, la banca va avvisata che l'utente e' presente (intestazioni PSU): le richieste
    'con utente presente' non hanno il limite di circa 4 al giorno. Se la banca ne chiede una che non possiamo dare
    sinceramente (es. posizione), non si manda niente."""
    if not config.BANCA_PRESENTE:
        return {}
    if "h" in _psu:
        return _psu["h"]
    h: dict = {}
    try:
        nome = _sessione().get("banca", "Intesa Sanpaolo")
        banca = next((b for b in _chiama("GET", "/aspsps", params={"country": "IT"}).get("aspsps", []) if b.get("name") == nome), {})
        richieste = [x.lower() for x in (banca.get("required_psu_headers") or ["psu-ip-address", "psu-user-agent"])]
        ip = httpx.get("https://api.ipify.org", timeout=5).text.strip()
        valori = {"psu-ip-address": ip, "psu-user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis/1.0",
                  "psu-accept": "application/json", "psu-accept-charset": "utf-8", "psu-accept-encoding": "gzip, deflate",
                  "psu-accept-language": "it-IT", "psu-http-method": "GET", "psu-referer": config.BANCA_RITORNO}
        h = {k: valori[k] for k in richieste if k in valori} if all(k in valori for k in richieste) else {}
    except (httpx.HTTPError, BancaError):
        h = {}
    _psu["h"] = h
    return h


def _chiama(metodo: str, percorso: str, presente: bool = False, **kw) -> dict:
    intest = {"Authorization": f"Bearer {_token()}"}
    if presente:
        intest.update(_intestazioni_presente())
    try:
        r = httpx.request(metodo, API + percorso, headers=intest, timeout=40, **kw)
        if presente and len(intest) > 1 and r.status_code in (400, 422):  # la banca non ha gradito le intestazioni: riprova senza
            _psu["h"] = {}
            r = httpx.request(metodo, API + percorso, headers={"Authorization": intest["Authorization"]}, timeout=40, **kw)
    except httpx.HTTPError:
        raise BancaError("Non riesco a raggiungere il servizio della banca. Controlla internet o riprova tra poco.")
    if r.status_code in (401, 403):
        raise BancaError("Il servizio della banca ha rifiutato la richiesta: controlla l'ID e la chiave nel .env, oppure il permesso e' scaduto.")
    if r.status_code == 429:
        raise BancaError("La banca ha un limite di richieste al giorno (circa 4 per conto, e' una regola europea): ho finito quelle di adesso. Riprova piu' tardi o domani.")
    if r.status_code == 422 or r.status_code == 400:
        raise BancaError("La banca non ha accettato la richiesta (codice " + str(r.status_code) + ").")
    if r.status_code >= 400:
        raise BancaError(f"Il servizio della banca ha dato un errore (codice {r.status_code}). Riprova tra poco.")
    return r.json()


# ---------------- collegamento (si fa una volta, poi ogni circa 90 giorni) ----------------
def avvia_collegamento(nome_banca: str = "Intesa Sanpaolo") -> str:
    """Restituisce l'indirizzo da aprire nel browser per autorizzare la lettura con l'app della banca."""
    banche = _chiama("GET", "/aspsps", params={"country": "IT"}).get("aspsps", [])
    scelte = [b for b in banche if nome_banca.lower() in b.get("name", "").lower() and "personal" in (b.get("psu_types") or ["personal"])]
    scelte = [b for b in scelte if "business" not in b.get("name", "").lower()] or scelte
    if not scelte:
        raise BancaError(f"Non trovo la banca '{nome_banca}' nell'elenco del servizio.")
    scadenza = datetime.now(timezone.utc) + timedelta(days=GIORNI_PERMESSO)
    r = _chiama("POST", "/auth", json={
        "access": {"valid_until": scadenza.isoformat()},
        "aspsp": {"name": scelte[0]["name"], "country": "IT"},
        "state": "jarvis",
        "redirect_url": config.BANCA_RITORNO,
        "psu_type": "personal",
    })
    return r["url"]


def completa_collegamento(indirizzo_o_codice: str) -> str:
    """Prende l'indirizzo (o il solo codice) su cui la banca ti riporta e apre la sessione di lettura."""
    t = indirizzo_o_codice.strip()
    codice = (parse_qs(t.split("?", 1)[-1].split("#")[0]).get("code") or [""])[0] if "code=" in t else t
    if not codice:
        raise BancaError("Non trovo il codice: incolla tutto l'indirizzo che compare in alto nel browser, quello con 'code=' dentro.")
    r = _chiama("POST", "/sessions", json={"code": codice})
    conti = [a.get("uid") for a in r.get("accounts", []) if a.get("uid")]
    if not conti:
        raise BancaError("La banca non ha dato nessun conto da leggere.")
    CARTELLA.mkdir(parents=True, exist_ok=True)
    SESSIONE.write_text(json.dumps({"session_id": r.get("session_id"), "banca": (r.get("aspsp") or {}).get("name", "Intesa Sanpaolo"), "conti": conti, "creata": date.today().isoformat(),
                                    "scade": (date.today() + timedelta(days=GIORNI_PERMESSO)).isoformat()}), encoding="utf-8")
    return f"Collegato: {len(conti)} conto/i in sola lettura. Il permesso va rinnovato fra circa {GIORNI_PERMESSO} giorni."


def _sessione() -> dict:
    if not SESSIONE.exists():
        raise BancaError("La banca non e' ancora collegata a Jarvis. Va fatto il collegamento (scripts\\collega_banca.py).")
    s = json.loads(SESSIONE.read_text(encoding="utf-8"))
    if s.get("scade") and s["scade"] < date.today().isoformat():
        raise BancaError("Il permesso della banca e' scaduto: va rinnovato con scripts\\collega_banca.py (un minuto, con l'app della banca).")
    return s


# ---------------- lettura ----------------
def _fresco(chiave: str):
    c = _cache.get(chiave)
    return c["dati"] if c and time.time() - c["t"] < VALIDITA_CACHE else None


def _tieni(chiave: str, dati):
    _cache[chiave] = {"t": time.time(), "dati": dati}
    return dati


def _o_vecchio(chiave: str, leggi_dati):
    """Dati freschi dalla banca; se la banca rifiuta per il limite giornaliero, usa quelli gia' letti (avvisando)."""
    global avviso
    dati = _fresco(chiave)
    if dati is not None:
        return dati
    try:
        avviso = ""
        return _tieni(chiave, leggi_dati())
    except BancaError as e:
        if chiave in _cache:
            avviso = "Attenzione: dati non aggiornati (" + str(e) + ")"
            return _cache[chiave]["dati"]
        raise


def saldi() -> list[dict]:
    def leggi():
        out = []
        for uid in _sessione()["conti"]:
            for b in _chiama("GET", f"/accounts/{uid}/balances", presente=True).get("balances", []):
                a = b.get("balance_amount", {})
                out.append({"tipo": b.get("balance_type"), "importo": float(a.get("amount", 0)), "valuta": a.get("currency", "EUR")})
        return out
    return _o_vecchio("saldi", leggi)


def _converti(t: dict, attesa: bool) -> dict:
    imp = float((t.get("transaction_amount") or {}).get("amount", 0))
    if t.get("credit_debit_indicator") == "DBIT":
        imp = -abs(imp)
    parte = (t.get("creditor") or {}).get("name") if imp < 0 else (t.get("debtor") or {}).get("name")
    reg = t.get("booking_date") or t.get("value_date") or ""
    desc = " ".join(t.get("remittance_information") or []) or t.get("note") or (t.get("bank_transaction_code") or {}).get("description") or ""
    return {"data": t.get("transaction_date") or t.get("value_date") or reg,  # giorno in cui hai pagato, se la banca lo da'
            "registrata": reg, "importo": imp, "controparte": (parte or "").strip(), "descrizione": " ".join(str(desc).split())[:80],
            "attesa": attesa}


def _scarica_movimenti() -> list[dict]:
    dal = (date.today() - timedelta(days=FINESTRA)).isoformat()
    out = []
    for uid in _sessione()["conti"]:
        chiave = None
        for _ in range(20):  # pagine
            params = {"date_from": dal, **({"continuation_key": chiave} if chiave else {})}
            r = _chiama("GET", f"/accounts/{uid}/transactions", presente=True, params=params)
            out += [_converti(t, False) for t in r.get("transactions", []) if t.get("status") in (None, "BOOK")]
            chiave = r.get("continuation_key")
            if not chiave:
                break
        try:  # pagamenti non ancora registrati: non tutte le banche li danno
            r = _chiama("GET", f"/accounts/{uid}/transactions", presente=True,
                        params={"date_from": (date.today() - timedelta(days=15)).isoformat(), "transaction_status": "PDNG"})
            out += [_converti(t, True) for t in r.get("transactions", []) if t.get("status") in (None, "PDNG")]
        except BancaError:
            pass
    return sorted(out, key=lambda m: m["data"])


def movimenti(giorni: int = 30) -> list[dict]:
    """Movimenti degli ultimi `giorni` (massimo 89): {data, importo (negativo = uscita), controparte, descrizione}.
    Si legge dalla banca una volta sola per 89 giorni e poi si filtra: cosi' si usano poche richieste."""
    dal = (date.today() - timedelta(days=max(1, min(giorni, FINESTRA)))).isoformat()
    return [m for m in _o_vecchio("movimenti", _scarica_movimenti) if m["data"] >= dal]


def elenco(giorni: int = 7, tutti: bool = False) -> str:
    """Movimenti uno per uno, ordinati per giorno di pagamento (la banca a volte li registra dopo)."""
    giorni = min(giorni, FINESTRA)
    mov = movimenti(giorni)
    if not mov:
        return f"Negli ultimi {giorni} giorni non ci sono movimenti registrati."
    mov = sorted(mov, key=lambda m: m["data"])
    uscite = [m for m in mov if tutti or m["importo"] < 0]
    righe = [f"Movimenti degli ultimi {giorni} giorni (data di pagamento; tra parentesi il giorno di registrazione se diverso). "
             f"Dove manca il nome, la banca non l'ha dato."]
    for m in uscite[-120:]:
        nome = m["controparte"] or m["descrizione"] or "(nome non dato dalla banca)"
        reg = " (IN ATTESA, non ancora registrato)" if m.get("attesa") else (f" (reg. {m['registrata']})" if m["registrata"] and m["registrata"] != m["data"] else "")
        righe.append(f"{m['data']}{reg} {_eur(m['importo'])} {nome}")
    if len(uscite) > 120:
        righe.append(f"... mostrati gli ultimi 120 di {len(uscite)}.")
    return "\n".join(([avviso] if avviso else []) + righe)


def _eur(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " euro"


PREFERENZA_SALDO = ["CLAV", "ITAV", "XPCD", "ITBD", "CLBD"]


def riepilogo(giorni: int = 30) -> str:
    """Testo per il cervello: saldo, entrate/uscite, dove vanno i soldi, spese ripetute (abbonamenti), spese grosse."""
    giorni = min(giorni, FINESTRA)  # la banca da' al massimo circa 90 giorni
    tutti = movimenti(giorni)
    mov = [m for m in tutti if not m.get("attesa")]
    attesa = [m for m in tutti if m.get("attesa")]
    righe = []
    try:
        per_tipo = {s["tipo"]: s for s in saldi()}
        for t in PREFERENZA_SALDO:
            if t in per_tipo:
                righe.append(f"Saldo ({'disponibile' if t in ('CLAV', 'ITAV', 'XPCD') else 'contabile'}, secondo l'ultima lettura della banca): {_eur(per_tipo[t]['importo'])}.")
                if attesa:
                    righe.append(f"Se i pagamenti in attesa verranno addebitati, il saldo scende a circa {_eur(per_tipo[t]['importo'] + sum(m['importo'] for m in attesa))}.")
                break
    except BancaError:
        pass
    if attesa:
        righe.append(f"In attesa di registrazione ({len(attesa)} movimenti, {_eur(-sum(m['importo'] for m in attesa))} in uscita): "
                     + "; ".join(f"{m['data']} {_eur(m['importo'])} {m['controparte'] or m['descrizione'] or 'nome non dato'}" for m in attesa[:10]))
    else:
        righe.append("Pagamenti in attesa: la banca non ne mostra (o non li fornisce a Jarvis).")
    if not mov:
        return "\n".join(([avviso] if avviso else []) + righe + [f"Negli ultimi {giorni} giorni non ci sono movimenti registrati."])
    entrate = sum(m["importo"] for m in mov if m["importo"] > 0)
    uscite = -sum(m["importo"] for m in mov if m["importo"] < 0)
    righe.append(f"Ultimi {giorni} giorni ({len(mov)} movimenti): entrate {_eur(entrate)}, uscite {_eur(uscite)}, differenza {_eur(entrate - uscite)}.")
    per = defaultdict(lambda: [0.0, 0, set()])
    for m in mov:
        if m["importo"] < 0:
            k = (m["controparte"] or m["descrizione"] or "senza nome")[:40]
            per[k][0] += -m["importo"]; per[k][1] += 1; per[k][2].add(m["data"][:7])
    top = sorted(per.items(), key=lambda kv: -kv[1][0])[:12]
    righe.append("Dove vanno i soldi (uscite per destinatario): " + "; ".join(f"{k} {_eur(v[0])} ({v[1]}x)" for k, v in top))
    ricorrenti = [k for k, v in per.items() if len(v[2]) >= 2 and v[1] >= 2]
    if ricorrenti:
        righe.append("Spese che si ripetono su piu' mesi (possibili abbonamenti): " + "; ".join(ricorrenti[:10]))
    grosse = sorted((m for m in mov if m["importo"] < 0), key=lambda m: m["importo"])[:5]
    righe.append("Uscite piu' grosse: " + "; ".join(f"{m['data']} {m['controparte'] or m['descrizione'] or 'senza nome'} {_eur(-m['importo'])}" for m in grosse))
    return "\n".join(([avviso] if avviso else []) + righe)
