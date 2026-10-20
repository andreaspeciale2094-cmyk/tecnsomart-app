"""Focus per addetto: legge dall'app i pezzi del mese per ragazzo (indirizzo di sola lettura) e li calcola come il
"Focus addetti" dell'app (punti per categoria, Local Promoter escluso, "migliore"). Nomi e numeri dei ragazzi non vengono
salvati ne' scritti nei registri. Nel codice non ci sono nomi di persone."""
from datetime import date

from . import negozi

# (nome, [prodotti], punti per prodotto o None = 1, prodotti che contano nel totale o None = tutti)
CATEGORIE = {
    0: ("ATTIVAZIONI MOBILE", ["W3 TIED EASY PAY", "W3 RELOAD EXCHANGE", "W3 UNTIED", "WINDTRE SECURITY PRO", "W3 TOURIST",
                               "W3 TIED PARTITA IVA", "GA CONVERGENTI FISSO", "MNP", "MNP VIRTUALI"], None, [0, 1, 2, 4]),
    2: ("FISSO", ["FISSO CONSUMER", "FWA", "FISSO BIZ 1 LINEA", "FISSO BIZ 2 LINEA", "DI CUI MIA", "DI CUI CONV MOBILE",
                  "DI CUI CONV LUCE", "DI CUI CONV ASS", "FRITZ BOX", "NETFLIX", "FISSO VOCE", "PIU SICURI",
                  "VOCE UNLIMITED", "FISSO SOLO VOCE"], None, [0, 1, 2, 3, 8, 13]),
    3: ("CB (PUNTI)", ["CAMBI PIANO", "TEL FINDO/COMPASS CB", "TEL VAR CB", "CB FISSO CAMBIO TECNOLOGIA", "CB FISSO CON NETFLIX"],
        [4, 8, 6, 2, 4], None),
    4: ("TELEFONI CB", ["TEL FIN 0-200", "TEL FIN 200-600", "TEL FIN 600-2000", "TEL VAR 0-200", "TEL VAR 200-600",
                        "TEL VAR 600-2000", "ACCESSORI"], None, None),
    5: ("LUCE & GAS", ["CF RID", "CF BP", "P.IVA", "EX ACEA"], None, None),
    6: ("ASSICURAZIONI (PUNTI)", ["SPORT", "ELETTRODOMESTICI", "VIAGGI & VACANZE", "VIAGGI MONDO", "CASA START", "SPORT FAMIGLIA",
                                  "MICIO & FIDO", "CASA FULL", "CASA PLUS", "PROTEZIONE PRO BIZ", "RID", "CDC",
                                  "DI CUI ANNUALI", "DI CUI MENSILI"], [0.5, 0.5, 1.5, 1.5, 2, 2, 2, 3, 3, 4, 1, 1, 1, 1],
        list(range(10))),
    7: ("ALLARME / PROTECTA", ["PROTECTA"], None, None),
    8: ("TELEFONI FIN", ["TEL FIN 0-200", "TEL FIN 200-600", "TEL FIN 600-2000"], None, None),
    9: ("TELEFONI VAR", ["TEL VAR 0-200", "TEL VAR 200-600", "TEL VAR 600-2000"], None, None),
    10: ("ACCESSORI (euro)", ["ACCESSORI"], None, None),
}
NASCOSTI = {(2, 10)}  # FISSO VOCE confluisce in VOCE UNLIMITED


def _chiave(k: str):
    """'categoria-prodotto' -> (ci, pi), con le stesse correzioni dell'app (vecchia categoria Telefoni, Fisso voce)."""
    try:
        ci, pi = (int(x) for x in k.split("-"))
    except ValueError:
        return None
    if ci == 1:  # vecchi TELEFONI divisi in FIN (8), VAR (9), ACCESSORI (10)
        ci, pi = (8, pi) if pi <= 2 else ((9, pi - 3) if pi <= 5 else (10, 0))
    if (ci, pi) == (2, 10):
        ci, pi = 2, 12
    return ci, pi


def pezzi(raw_addetto: dict) -> dict:
    """{(ci, pi): pezzi} di un addetto."""
    out: dict = {}
    for k, v in raw_addetto.items():
        c = _chiave(k)
        if c and c[0] in CATEGORIE and c[1] < len(CATEGORIE[c[0]][1]):
            out[c] = out.get(c, 0.0) + negozi._num(v)
    return out


def punti_categoria(p: dict, ci: int) -> float:
    _, prodotti, punti, solo = CATEGORIE[ci]
    return sum(p.get((ci, pi), 0) * (punti[pi] if punti else 1) for pi in range(len(prodotti)) if solo is None or pi in solo)


def _fmt(x: float) -> str:
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:.1f}"


def trova(nomi, richiesto: str) -> str | None:
    r = richiesto.strip().lower()
    esatti = [n for n in nomi if n.lower() == r]
    parziali = esatti or [n for n in nomi if r in n.lower() or n.lower() in r]
    return parziali[0] if len(parziali) == 1 or esatti else None


def focus(raw: dict, nome: str = "") -> str:
    """Testo per il cervello: numeri del mese, confronto con la squadra e punti sotto/sopra la media."""
    addetti = {n: pezzi(a) for n, a in (raw.get("addetti") or {}).items()}
    if not addetti:
        return f"Nel mese {raw.get('mese')} non ci sono ancora numeri per gli addetti."
    mese = raw.get("mese")
    n = len(addetti)
    righe = [f"Focus addetti, mese {mese}. Addetti con numeri: {n}. Punti per categoria (come l'app); Local Promoter escluso."]
    if nome:
        scelto = trova(list(addetti), nome)
        if not scelto:
            return f"Non trovo un addetto chiamato '{nome}'. Addetti presenti: {', '.join(sorted(addetti))}."
        righe.append(f"ADDETTO: {scelto}")
        for ci, (cat, prodotti, _, _) in CATEGORIE.items():
            tot = {a: punti_categoria(p, ci) for a, p in addetti.items()}
            if not any(tot.values()):
                continue
            media = sum(tot.values()) / n
            ordine = sorted(tot, key=lambda a: -tot[a])
            pos = ordine.index(scelto) + 1
            dett = []
            for pi, pr in enumerate(prodotti):
                if (ci, pi) in NASCOSTI:
                    continue
                mio = addetti[scelto].get((ci, pi), 0)
                med = sum(p.get((ci, pi), 0) for p in addetti.values()) / n
                if mio or med >= 1:
                    dett.append(f"{pr} {_fmt(mio)} (media {med:.1f})")
            righe.append(f"- {cat}: totale {_fmt(tot[scelto])}, media squadra {media:.1f}, posto {pos} su {n}"
                         f"{', migliore della squadra' if pos == 1 and tot[scelto] > 0 else ''}. Prodotti: " + "; ".join(dett))
        return "\n".join(righe)
    righe.append("SQUADRA (migliore per categoria, media):")
    for ci, (cat, _, _, _) in CATEGORIE.items():
        tot = {a: punti_categoria(p, ci) for a, p in addetti.items()}
        if any(tot.values()):
            m = max(tot, key=lambda a: tot[a])
            righe.append(f"- {cat}: migliore {m} ({_fmt(tot[m])}), media {sum(tot.values()) / n:.1f}")
    return "\n".join(righe)


def leggi(mese: str = "") -> dict:
    mese = mese or date.today().strftime("%Y-%m")
    url = negozi.load_config().get("url", "")
    return negozi.fetch(url, azione="jarvis_addetti", mese=mese)


def riepilogo(nome: str = "", mese: str = "") -> str:
    return focus(leggi(mese), nome)
