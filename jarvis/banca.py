"""Conto personale di Andrea in SOLA LETTURA, tramite Enable Banking (open banking).
Il permesso chiesto alla banca e' solo 'informazioni sul conto': pagare e' impossibile. Chiave privata e sessione stanno solo
sul PC (memoria/banca/). I movimenti non vengono salvati su disco ne' scritti nei registri: si leggono quando servono."""
import json
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from . import config

API = "https://api.enablebanking.com"
CARTELLA = Path(__file__).parent.parent / "memoria" / "banca"
SESSIONE = CARTELLA / "sessione.json"
GIORNI_PERMESSO = 90  # la banca chiede di rinnovare il permesso circa ogni 90 giorni


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


def _chiama(metodo: str, percorso: str, **kw) -> dict:
    try:
        r = httpx.request(metodo, API + percorso, headers={"Authorization": f"Bearer {_token()}"}, timeout=40, **kw)
    except httpx.HTTPError:
        raise BancaError("Non riesco a raggiungere il servizio della banca. Controlla internet o riprova tra poco.")
    if r.status_code in (401, 403):
        raise BancaError("Il servizio della banca ha rifiutato la richiesta: controlla l'ID e la chiave nel .env, oppure il permesso e' scaduto.")
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
    codice = (parse_qs(urlparse(t).query).get("code") or [""])[0] if "code=" in t else t
    if not codice:
        raise BancaError("Non trovo il codice: incolla tutto l'indirizzo che compare in alto nel browser, quello con 'code=' dentro.")
    r = _chiama("POST", "/sessions", json={"code": codice})
    conti = [a.get("uid") for a in r.get("accounts", []) if a.get("uid")]
    if not conti:
        raise BancaError("La banca non ha dato nessun conto da leggere.")
    CARTELLA.mkdir(parents=True, exist_ok=True)
    SESSIONE.write_text(json.dumps({"session_id": r.get("session_id"), "conti": conti, "creata": date.today().isoformat(),
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
def saldi() -> list[dict]:
    out = []
    for uid in _sessione()["conti"]:
        for b in _chiama("GET", f"/accounts/{uid}/balances").get("balances", []):
            a = b.get("balance_amount", {})
            out.append({"tipo": b.get("balance_type"), "importo": float(a.get("amount", 0)), "valuta": a.get("currency", "EUR")})
    return out


def movimenti(giorni: int = 30) -> list[dict]:
    """Movimenti registrati degli ultimi `giorni`: {data, importo (negativo = uscita), controparte, descrizione}."""
    dal = (date.today() - timedelta(days=max(1, min(giorni, 365)))).isoformat()
    out = []
    for uid in _sessione()["conti"]:
        chiave = None
        for _ in range(20):  # pagine
            params = {"date_from": dal, **({"continuation_key": chiave} if chiave else {})}
            r = _chiama("GET", f"/accounts/{uid}/transactions", params=params)
            for t in r.get("transactions", []):
                if t.get("status") not in (None, "BOOK"):
                    continue
                imp = float((t.get("transaction_amount") or {}).get("amount", 0))
                if t.get("credit_debit_indicator") == "DBIT":
                    imp = -abs(imp)
                parte = (t.get("creditor") or {}).get("name") if imp < 0 else (t.get("debtor") or {}).get("name")
                reg = t.get("booking_date") or t.get("value_date") or ""
                desc = " ".join(t.get("remittance_information") or []) or t.get("note") or (t.get("bank_transaction_code") or {}).get("description") or ""
                out.append({"data": t.get("transaction_date") or t.get("value_date") or reg,  # giorno in cui hai pagato, se la banca lo da'
                            "registrata": reg, "importo": imp, "controparte": (parte or "").strip(), "descrizione": " ".join(str(desc).split())[:80]})
            chiave = r.get("continuation_key")
            if not chiave:
                break
    return sorted(out, key=lambda m: m["data"])


def elenco(giorni: int = 7, tutti: bool = False) -> str:
    """Movimenti uno per uno, ordinati per giorno di pagamento (la banca a volte li registra dopo)."""
    mov = movimenti(giorni)
    if not mov:
        return f"Negli ultimi {giorni} giorni non ci sono movimenti registrati."
    mov = sorted(mov, key=lambda m: m["data"])
    uscite = [m for m in mov if tutti or m["importo"] < 0]
    righe = [f"Movimenti degli ultimi {giorni} giorni (data di pagamento; tra parentesi il giorno di registrazione se diverso). "
             f"Dove manca il nome, la banca non l'ha dato."]
    for m in uscite[-120:]:
        nome = m["controparte"] or m["descrizione"] or "(nome non dato dalla banca)"
        reg = f" (reg. {m['registrata']})" if m["registrata"] and m["registrata"] != m["data"] else ""
        righe.append(f"{m['data']}{reg} {_eur(m['importo'])} {nome}")
    if len(uscite) > 120:
        righe.append(f"... mostrati gli ultimi 120 di {len(uscite)}.")
    return "\n".join(righe)


def _eur(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " euro"


def riepilogo(giorni: int = 30) -> str:
    """Testo per il cervello: saldo, entrate/uscite, dove vanno i soldi, spese ripetute (abbonamenti), spese grosse."""
    mov = movimenti(giorni)
    righe = []
    try:
        disp = [s for s in saldi() if s["tipo"] in ("CLAV", "ITAV", "CLBD", "ITBD", "XPCD")]
        if disp:
            righe.append(f"Saldo: {_eur(disp[0]['importo'])}.")
    except BancaError:
        pass
    if not mov:
        return "\n".join(righe + [f"Negli ultimi {giorni} giorni non ci sono movimenti registrati."])
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
    return "\n".join(righe)
