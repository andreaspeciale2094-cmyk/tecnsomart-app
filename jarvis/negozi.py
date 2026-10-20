"""Riepilogo dei negozi TecnoSmart: legge i numeri dall'app (indirizzo di sola lettura) e li confronta con i target
con le STESSE regole dell'app (passo giornaliero, giorni rimasti, soglie verde/giallo/rosso).
I target stanno solo sul PC di Andrea, in memoria/negozi.json (mai su GitHub). I dati dei negozi non vengono salvati."""
import json
import math
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


def fetch(url: str, day: str = "", azione: str = "jarvis", **extra) -> dict:
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
    raw = fetch(cfg["url"], d.isoformat())
    parts = []
    for kind, label in (("mono", "mono brand"), ("multi", "multi brand")):
        if tipo in ("tutti", kind) and kind in cfg.get("run", {}):
            parts.append(format_summary(label, analyze(cfg["run"][kind], raw.get(kind) or {}, d), d))
    return "\n\n".join(parts) or "Niente da riassumere: controlla il tipo (mono, multi o tutti)."
