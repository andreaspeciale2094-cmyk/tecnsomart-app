"""Cassa dei contanti di Andrea: registro scritto a mano (a voce) di prelievi e spese, solo sul PC (memoria/cassa.json).
Jarvis non tocca il conto corrente: qui ci sono solo i numeri che dice Andrea. Il registro non si cancella mai:
una voce sbagliata si annulla (resta visibile come annullata). Gli importi non vanno nei registri di errori/consumi."""
import json
from datetime import date, datetime
from pathlib import Path

FILE = Path(__file__).parent.parent / "memoria" / "cassa.json"
TIPI = {"prelievo": 1, "spesa": -1}


class CassaError(Exception):
    """Errore con un messaggio gia' in italiano semplice."""


def _carica() -> list[dict]:
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except ValueError:
        raise CassaError("Il file memoria\\cassa.json non e' leggibile. Non l'ho toccato: controllalo con Claude o Cowork.")


def _salva(voci: list[dict]):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(voci, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def saldo(voci: list[dict] | None = None) -> float:
    voci = _carica() if voci is None else voci
    return round(sum(TIPI[v["tipo"]] * v["importo"] for v in voci if not v.get("annullata")), 2)


def _eur(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + " euro"


def segna(tipo: str, importo: float, nota: str = "") -> str:
    if tipo not in TIPI:
        raise CassaError("Il tipo deve essere 'prelievo' o 'spesa'.")
    try:
        importo = round(float(importo), 2)
    except (TypeError, ValueError):
        raise CassaError("L'importo non e' un numero.")
    if importo <= 0 or importo > 100000:
        raise CassaError("L'importo deve essere un numero positivo.")
    voci = _carica()
    voci.append({"id": (voci[-1]["id"] + 1) if voci else 1, "data": date.today().isoformat(), "ora": datetime.now().strftime("%H:%M"),
                 "tipo": tipo, "importo": importo, "nota": " ".join(nota.split())[:80]})
    _salva(voci)
    return f"Segnato: {tipo} di {_eur(importo)}. In cassa restano {_eur(saldo(voci))}."


def annulla_ultima() -> str:
    voci = _carica()
    attive = [v for v in voci if not v.get("annullata")]
    if not attive:
        raise CassaError("Non c'e' niente da annullare.")
    v = attive[-1]
    v["annullata"] = True
    _salva(voci)
    return f"Annullata l'ultima voce ({v['tipo']} di {_eur(v['importo'])}). In cassa restano {_eur(saldo(voci))}."


def resoconto(giorno: str = "") -> str:
    giorno = giorno or date.today().isoformat()
    voci = _carica()
    if not voci:
        return "La cassa e' vuota: non ci sono ancora prelievi o spese segnati."
    oggi = [v for v in voci if v["data"] == giorno and not v.get("annullata")]
    pre = sum(v["importo"] for v in oggi if v["tipo"] == "prelievo")
    spe = sum(v["importo"] for v in oggi if v["tipo"] == "spesa")
    righe = [f"Cassa contanti al {giorno}: in cassa {_eur(saldo(voci))}.",
             f"In quel giorno: prelevati {_eur(pre)}, spesi {_eur(spe)}."]
    righe += [f"- {v['ora']} {v['tipo']} {_eur(v['importo'])}" + (f" ({v['nota']})" if v["nota"] else "") for v in oggi]
    return "\n".join(righe)
