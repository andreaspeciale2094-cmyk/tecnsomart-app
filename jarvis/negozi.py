"""Riepilogo dei negozi TecnoSmart: legge i numeri dall'app (indirizzo di sola lettura) e li confronta con i target
con le STESSE regole dell'app (passo giornaliero, giorni rimasti, soglie verde/giallo/rosso).
I target stanno solo sul PC di Andrea, in memoria/negozi.json (mai su GitHub). I dati dei negozi non vengono salvati."""
import json
import math
import time
from datetime import date, datetime
from pathlib import Path

import httpx

from . import config

CONFIG_FILE = Path(__file__).parent.parent / "memoria" / "negozi.json"


class NegoziError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise NegoziError("Manca il file memoria\\negozi.json con i negozi e i target. Chiedi a Claude o a Cowork di crearlo.")
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except ValueError as e:
        raise NegoziError(f"Il file memoria\\negozi.json non e' valido ({e}).")


_ram: dict = {"giorno": "", "dati": {}}  # ultime risposte dell'app, SOLO in RAM: si buttano allo scattare del giorno dopo e con svuota()


def svuota():
    """Butta via tutti i dati dell'app tenuti in memoria (mezzanotte, o quando serve)."""
    _ram.update(giorno="", dati={})


def fetch(url: str, day: str = "", azione: str = "jarvis", fresco: float = 0.0, **extra) -> dict:
    """Legge l'app. Con fresco > 0 usa la copia in memoria se ha meno di quei secondi (l'agente negozi la tiene aggiornata); senza, legge sempre."""
    oggi = date.today().isoformat()
    if _ram["giorno"] != oggi:
        _ram.update(giorno=oggi, dati={})
    chiave = (azione, day, tuple(sorted((k, str(v)) for k, v in extra.items())))
    c = _ram["dati"].get(chiave)
    if fresco and c and time.time() - c[0] < fresco:
        return c[1]
    dati = _fetch_rete(url, day, azione, **extra)
    _ram["dati"][chiave] = (time.time(), dati)
    return dati


def _fetch_rete(url: str, day: str = "", azione: str = "jarvis", **extra) -> dict:
    if not config.TECNOSMART_TOKEN:
        raise NegoziError("Manca la chiave TECNOSMART_TOKEN nel file .env.")
    try:
        r = httpx.get(url, params={"azione": azione, "token": config.TECNOSMART_TOKEN, **({"data": day} if day else {}), **extra}, follow_redirects=True, timeout=40)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError:
        raise NegoziError("Non riesco a raggiungere l'app dei negozi. Controlla internet o riprova tra poco.")
    except ValueError:
        raise NegoziError("L'app dei negozi ha risposto in modo strano: probabilmente il collegamento di Jarvis non e' ancora attivo.")
    if not data.get("ok"):
        raise NegoziError("L'app dei negozi ha rifiutato la richiesta: la chiave potrebbe essere diversa da quella dell'app.")
    return data


# ---------------- calcolo, uguale a quello dell'app ----------------
def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def month_cfg(run_cfg: dict, month: str) -> dict | None:
    return (run_cfg.get("mesi") or {}).get(month)


def cycle_days(run_cfg: dict, mcfg: dict | None) -> int:
    return int(mcfg["ciclo"]) if mcfg else int(run_cfg.get("cicloPredefinito", 26))


def store_month_target(run_cfg: dict, mcfg: dict | None, store: dict, cat: dict, ciclo: int) -> float:
    if mcfg:  # mese con target specifici: se la voce manca vale 0
        return _num((mcfg.get("negozi", {}).get(store["slug"]) or {}).get(cat["key"], 0))
    return _num(cat["targetGruppo"]) * ciclo * _num(store.get("quota", 0))  # mese senza target specifici


def group_stores(run_cfg: dict) -> list[dict]:
    return [s for s in run_cfg["negozi"] if not s.get("fuoriGruppo")]


def group_month_target(run_cfg, mcfg, cat, ciclo) -> float:
    if mcfg:
        return sum(store_month_target(run_cfg, mcfg, s, cat, ciclo) for s in group_stores(run_cfg))
    return _num(cat["targetGruppo"]) * ciclo


def group_daily_target(run_cfg, mcfg, cat, ciclo) -> float:
    """Target giornaliero di gruppo: con target del mese e' il target mensile diviso i giorni del ciclo, arrotondato per eccesso."""
    return math.ceil(group_month_target(run_cfg, mcfg, cat, ciclo) / ciclo - 1e-9) if mcfg else _num(cat["targetGruppo"])


def remaining_days(day: date, ciclo: int) -> int:
    """Giorni rimasti nel ciclo, oggi compreso. Dopo la chiusura del ciclo vale 1."""
    return max(1, ciclo - min(max(day.day, 1), ciclo) + 1)


def color(value: float, target: float) -> str | None:
    """Soglie del totale di gruppo nell'app: verde >= target, giallo >= 50%, rosso sotto. Nessun colore se il valore e' 0."""
    if value <= 0:
        return None
    if value >= target:
        return "verde"
    return "giallo" if value >= target * 0.5 else "rosso"


def run_color(run: float, target: float) -> str:
    """Soglie del 'passo da fare' di gruppo: verde <= target, giallo <= 130%, rosso oltre."""
    if run <= target:
        return "verde"
    return "giallo" if run <= target * 1.3 else "rosso"


def analyze(run_cfg: dict, raw: dict, day: date) -> dict:
    """raw: {slug: {oggi:{cat:v}, mese:{cat:v}, giorni:n, haOggi:bool}} (mese comprende oggi)."""
    month = day.strftime("%Y-%m")
    mcfg = month_cfg(run_cfg, month)
    ciclo = cycle_days(run_cfg, mcfg)
    resta = remaining_days(day, ciclo)
    giorno_ciclo = min(day.day, ciclo)
    atteso = giorno_ciclo / ciclo
    cats = run_cfg["categorie"]
    out = {"giorno": giorno_ciclo, "ciclo": ciclo, "atteso_pct": round(100 * atteso), "mese_con_target": bool(mcfg), "negozi": [], "gruppo": []}

    def val(slug, kind, key):
        return _num(((raw.get(slug) or {}).get(kind) or {}).get(key, 0))

    for cat in cats:
        total_today = sum(val(s["slug"], "oggi", cat["key"]) for s in group_stores(run_cfg))
        accumulated = sum(val(s["slug"], "mese", cat["key"]) - val(s["slug"], "oggi", cat["key"]) for s in group_stores(run_cfg))
        mt, gt = group_month_target(run_cfg, mcfg, cat, ciclo), group_daily_target(run_cfg, mcfg, cat, ciclo)
        if mt <= 0:
            continue
        passo = max(0.0, (mt - accumulated) / resta - total_today)
        out["gruppo"].append({"categoria": cat["nome"], "oggi": total_today, "target_giorno": gt, "stato": color(total_today, gt) or "nessun colore",
                              "passo_da_fare": math.ceil(passo - 1e-9), "stato_passo": run_color(passo, gt),
                              "mese": accumulated + total_today, "target_mese": mt})

    for store in run_cfg["negozi"]:
        slug = store["slug"]
        info = {"negozio": store["nome"], "nel_gruppo": not store.get("fuoriGruppo"), "dati_oggi": bool((raw.get(slug) or {}).get("haOggi")),
                "giorni_con_dati": int((raw.get(slug) or {}).get("giorni", 0)), "categorie": []}
        for cat in cats:
            mt = store_month_target(run_cfg, mcfg, store, cat, ciclo)
            if mt <= 0:
                continue
            today, month_total = val(slug, "oggi", cat["key"]), val(slug, "mese", cat["key"])
            before = month_total - today
            baseline = (mt - before) / resta                      # quanto serve fare oggi per chiudere il mese
            daily = mt / ciclo
            pct = month_total / mt
            behind = pct < atteso - 0.02
            st = color(today, daily) if info["dati_oggi"] else "nessun dato"
            info["categorie"].append({
                "categoria": cat["nome"], "oggi": today, "target_giorno": round(daily, 1), "stato": st or "zero",
                "mese": month_total, "target_mese": mt, "mese_pct": round(100 * pct),
                "indietro": behind, "serve_oggi": math.ceil(max(0.0, baseline - today) - 1e-9),
                "recupera": behind and info["dati_oggi"] and today >= baseline > 0,
            })
        out["negozi"].append(info)
    return out


def format_summary(label: str, a: dict, day: date) -> str:
    """Testo compatto per Jarvis (che poi lo racconta a voce). Solo numeri, niente nomi di persone o clienti."""
    L = [f"RIEPILOGO RUN {label} del {day.isoformat()}: giorno {a['giorno']} di {a['ciclo']} del ciclo, a questo punto dovrebbe essere al {a['atteso_pct']}% del mese"
         + ("" if a["mese_con_target"] else " (mese senza target specifici: uso quelli standard)") + "."]
    L.append("GRUPPO (totale di oggi vs target giornaliero; colore come nell'app; 'passo' = quanto manca oggi per restare in linea col mese):")
    for g in a["gruppo"]:
        L.append(f"- {g['categoria']}: oggi {g['oggi']:g} su {g['target_giorno']:g} -> {g['stato']}; passo da fare {g['passo_da_fare']} ({g['stato_passo']}); mese {g['mese']:g} su {g['target_mese']:g}")
    for n in a["negozi"]:
        head = f"NEGOZIO {n['negozio']}" + ("" if n["nel_gruppo"] else " (fuori dal gruppo)")
        if not n["dati_oggi"]:
            L.append(f"{head}: ATTENZIONE, oggi non ha inserito nessun dato (giorni con dati nel mese: {n['giorni_con_dati']}).")
            continue
        rossi = [c for c in n["categorie"] if c["stato"] in ("rosso", "zero")]
        gialli = [c for c in n["categorie"] if c["stato"] == "giallo"]
        verdi = [c for c in n["categorie"] if c["stato"] == "verde"]
        L.append(f"{head}: {len(verdi)} categorie verdi, {len(gialli)} gialle, {len(rossi)} rosse.")
        for tag, lst in (("ROSSO", rossi), ("GIALLO", gialli)):
            for c in lst:
                L.append(f"  {tag} {c['categoria']}: oggi {c['oggi']:g} su {c['target_giorno']:g}; mese {c['mese']:g}/{c['target_mese']:g} ({c['mese_pct']}%)"
                         + ("; INDIETRO sul mese" if c["indietro"] else "") + f"; servono {c['serve_oggi']} oggi per restare in linea")
        rec = [c for c in n["categorie"] if c["recupera"]]
        if rec:
            L.append("  STA RECUPERANDO: " + ", ".join(f"{c['categoria']} (oggi {c['oggi']:g}, serviva {c['target_giorno']:g}+)" for c in rec))
        ind = [c for c in n["categorie"] if c["indietro"] and c["stato"] == "verde" and not c["recupera"]]
        if ind:
            L.append("  Verde oggi ma ancora indietro sul mese: " + ", ".join(c["categoria"] for c in ind))
    return "\n".join(L)


def riepilogo(day: str = "", tipo: str = "tutti") -> str:
    cfg = load_config()
    d = datetime.strptime(day, "%Y-%m-%d").date() if day else date.today()
    raw = fetch(cfg["url"], d.isoformat(), fresco=900)
    parts = []
    for kind, label in (("mono", "mono brand"), ("multi", "multi brand")):
        if tipo in ("tutti", kind) and kind in cfg.get("run", {}):
            parts.append(format_summary(label, analyze(cfg["run"][kind], raw.get(kind) or {}, d), d))
    return "\n\n".join(parts) or "Niente da riassumere: controlla il tipo (mono, multi o tutti)."


def _leggi(cfg: dict, oggi: date, max_eta: float = 0.0) -> dict:
    """I dati di oggi: la copia pronta in memoria se ha meno di max_eta secondi, altrimenti dall'app."""
    return fetch(cfg["url"], oggi.isoformat(), fresco=max_eta)


def parlato() -> str:
    """Il resoconto dei negozi di oggi gia' pronto da dire a voce (solo numeri, calcolato dal codice, senza modello). Frasi corte, una per negozio.
    Nel Multi Brand un negozio che non ha MAI inserito dati questo mese non viene detto 'mancante': magari non fa multi brand."""
    cfg = load_config()
    oggi = date.today()
    raw = _leggi(cfg, oggi)
    blocchi = []
    for kind, etichetta in (("mono", "Mono brand"), ("multi", "Multi brand")):
        if kind not in cfg.get("run", {}):
            continue
        a = analyze(cfg["run"][kind], raw.get(kind) or {}, oggi)
        righe = [f"{etichetta}."]
        if a["gruppo"]:
            righe.append("Totale di gruppo oggi: " + ", ".join(f"{g['categoria']} {g['oggi']:g} su {g['target_giorno']:g}, {g['stato']}" for g in a["gruppo"]) + ".")
        senza = []
        for n in a["negozi"]:
            if not n["dati_oggi"]:
                if kind == "mono" or n["giorni_con_dati"] > 0:
                    senza.append(n["negozio"])
                continue
            ros = sum(1 for c in n["categorie"] if c["stato"] in ("rosso", "zero"))
            gia = sum(1 for c in n["categorie"] if c["stato"] == "giallo")
            righe.append(f"{n['negozio']}: " + (" e ".join(([f"{ros} rosse"] if ros else []) + ([f"{gia} gialle"] if gia else [])) if ros or gia else "tutto verde") + ".")
        if senza:
            righe.append("Oggi non risultano dati per: " + ", ".join(senza) + ".")
        blocchi.append(" ".join(righe))
    return " ".join(blocchi) or "Non ho target dei negozi da guardare."


def _chiave(t: str) -> str:
    import re
    return re.sub(r"[^a-z0-9 ]", "", t.lower().replace("'", " ")).strip()


def trova_negozio(testo: str) -> str | None:
    """Il nome del negozio detto nella frase (confronto per parole intere, ignora 'il/la/lo'), oppure None."""
    try:
        cfg = load_config()
    except Exception:
        return None
    parole = set(_chiave(testo).split())
    migliori = []
    for kind in ("mono", "multi"):
        for n in ((cfg.get("run") or {}).get(kind) or {}).get("negozi", []):
            nome = n.get("nome", "")
            chiave = [w for w in _chiave(nome).split() if w not in ("il", "la", "lo", "i", "le", "di", "del", "della")]
            if chiave and all(w in parole for w in chiave):
                migliori.append((len(chiave), nome))
    return max(migliori)[1] if migliori else None


def parlato_negozio(nome: str) -> str:
    """Solo quel negozio: per ogni categoria quanto ha inserito oggi rispetto all'obiettivo del giorno (mono e multi brand)."""
    cfg = load_config()
    oggi = date.today()
    raw = _leggi(cfg, oggi, 900)
    parti = []
    for kind, etichetta in (("mono", "Mono brand"), ("multi", "Multi brand")):
        if kind not in cfg.get("run", {}):
            continue
        a = analyze(cfg["run"][kind], raw.get(kind) or {}, oggi)
        n = next((x for x in a["negozi"] if x["negozio"] == nome), None)
        if n is None:
            continue
        if not n["dati_oggi"]:
            if kind == "mono" or n["giorni_con_dati"] > 0:
                parti.append(f"{etichetta}: oggi non risultano dati.")
            continue
        parti.append(f"{etichetta}: " + ", ".join(f"{c['categoria']} {c['oggi']:g} su {c['target_giorno']:g} ({c['stato']})" for c in n["categorie"]) + ".")
    return f"{nome}. " + " ".join(parti) if parti else f"Per {nome} non ho dati di oggi."


def _radici(t: str) -> list[str]:
    """Parole senza finale (fissi/fisso, telefoni/telefono) per trovare una categoria nominata a voce."""
    return [w[:4] if len(w) > 4 else w for w in _chiave(t).split() if w not in ("di", "e", "il", "la", "lo", "i", "le", "del", "della", "per", "cb", "punti", "euro")]


def _cat_nominata(testo: str, nomi: list[str]) -> str | None:
    rt = set(_radici(testo))
    best = [(len(set(_radici(n)) & rt), n) for n in nomi]
    best = [b for b in best if b[0] and set(_radici(b[1])) <= rt]  # tutte le parole del nome devono stare nella frase
    return max(best)[1] if best else None


def domanda_gruppo(testo: str) -> str | None:
    """Domande sul TOTALE DI GRUPPO, dai dati gia' pronti e senza cervello: 'quanto e' il totale gruppo', 'la proiezione del totale gruppo',
    'quanti fissi fastweb mancano al totale multi'. None se la frase non e' di questo tipo. La proiezione e' lineare: quanto fatto nel mese
    diviso i giorni passati del ciclo, per i giorni totali del ciclo."""
    import re
    t = testo.lower()
    if re.search(r"\bobiettiv|come stiamo andando|come siamo messi", t) and not re.search(r"\bmanc", t):
        try:
            return obiettivi()
        except Exception:
            return None
    proiez = bool(re.search(r"proiezion|a questo ritmo|a fine mese|chiudiam", t))
    manca = bool(re.search(r"\bmanc", t))
    totale = bool(re.search(r"\btotal[ei]\b|\bgruppo\b", t))
    if not (proiez or manca or totale):
        return None
    try:
        cfg = load_config()
        oggi = date.today()
        raw = _leggi(cfg, oggi, 900)
    except Exception:
        return None
    voluti = [k for k in ("mono", "multi") if re.search(r"\b" + k + r"\b|multi ?brand|mono ?brand", t) and (k in t or k + " brand" in t or k + "brand" in t)] or ["mono", "multi"]
    pezzi, trovata = [], False
    for kind in voluti:
        if kind not in (cfg.get("run") or {}):
            continue
        a = analyze(cfg["run"][kind], raw.get(kind) or {}, oggi)
        gr = a["gruppo"]
        if not gr:
            continue
        etichetta = "Mono brand" if kind == "mono" else "Multi brand"
        cat = _cat_nominata(testo, [g["categoria"] for g in gr]) if (manca or proiez or totale) else None
        if cat:
            gr, trovata = [g for g in gr if g["categoria"] == cat], True
        elif manca and not totale:
            continue  # 'mancano ...' senza una categoria riconosciuta: lo gestisce il cervello
        righe = []
        for g in gr:
            mese, tm = g["mese"], g["target_mese"]
            proj = mese / max(1, a["giorno"]) * a["ciclo"]
            if manca:
                righe.append(f"{g['categoria']}: mancano {max(0, math.ceil(tm - mese - 1e-9)):g} al target del mese ({mese:g} su {tm:g}); oggi servono {g['passo_da_fare']:g} per restare in linea")
            elif proiez:
                righe.append(f"{g['categoria']}: proiezione {proj:.0f} su {tm:g} ({round(100 * proj / tm) if tm else 0}%)")
            else:
                righe.append(f"{g['categoria']}: mese {mese:g} su {tm:g} ({round(100 * mese / tm) if tm else 0}%), oggi {g['oggi']:g}")
        if righe:
            pezzi.append(f"{etichetta}, giorno {a['giorno']} di {a['ciclo']}. " + "; ".join(righe) + ".")
    if manca and not trovata and not totale:
        return None
    return " ".join(pezzi) or None


def obiettivi() -> str:
    """Obiettivi del mese in breve (solo calcolo, dati pronti): per mono e multi dove arriva il gruppo a fine mese a questo ritmo e le 3 categorie piu' indietro."""
    cfg = load_config()
    oggi = date.today()
    raw = _leggi(cfg, oggi, 900)
    pezzi = []
    for kind, etichetta in (("mono", "Mono brand"), ("multi", "Multi brand")):
        if kind not in (cfg.get("run") or {}):
            continue
        a = analyze(cfg["run"][kind], raw.get(kind) or {}, oggi)
        righe = []
        for g in a["gruppo"]:
            if g["target_mese"] > 0:
                righe.append((g["mese"] / max(1, a["giorno"]) * a["ciclo"] / g["target_mese"], g))
        if not righe:
            continue
        righe.sort(key=lambda x: x[0])
        indietro = [f"{g['categoria']} {round(100 * r)}%" for r, g in righe[:3] if r < 1]
        tot = sum(g["mese"] for _, g in righe) / max(1, a["giorno"]) * a["ciclo"] / sum(g["target_mese"] for _, g in righe)
        pezzi.append(f"{etichetta}, giorno {a['giorno']} di {a['ciclo']}: a questo ritmo il gruppo chiude intorno al {round(100 * tot)}% dei target." +
                     (" Piu' indietro: " + ", ".join(indietro) + "." if indietro else " Tutte le categorie sono in linea o sopra."))
    return " ".join(pezzi) or "Non ho target del mese da guardare."


def sintesi() -> dict:
    """Per il vigile (solo RAM, nessun testo salvato): {nome_negozio: {'dati': bool, 'rosse': n, 'gialle': n}} di oggi, mono e multi brand insieme."""
    cfg = load_config()
    oggi = date.today()
    raw = fetch(cfg["url"], oggi.isoformat())
    out: dict[str, dict] = {}
    for kind in ("mono", "multi"):
        if kind not in cfg.get("run", {}):
            continue
        a = analyze(cfg["run"][kind], raw.get(kind) or {}, oggi)
        for n in a["negozi"]:
            nome = n["negozio"] if kind == "mono" else f"{n['negozio']} (multi brand)"
            cat = n["categorie"]
            out[nome] = {"dati": bool(n["dati_oggi"]), "rosse": sum(1 for c in cat if c["stato"] in ("rosso", "zero")), "gialle": sum(1 for c in cat if c["stato"] == "giallo")}
    return out
