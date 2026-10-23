"""Prova dei dati dei treni: mostra cosa risponde la fonte per il tuo treno (solo stazioni e orari dei treni, niente di personale).
Uso: .venv\\Scripts\\python.exe scripts\\controlla_treni.py [orario, es. 07:48]"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import config, treni  # noqa: E402

ora = sys.argv[1] if len(sys.argv) > 1 else "07:48"
imp = treni._impostazioni()
try:
    nome, codice = treni.codice_stazione(imp["partenza"])
    print(f"Stazione: {nome} (codice {codice})")
    h, m = (int(x) for x in ora.split(":"))
    q = datetime.now(ZoneInfo(config.FUSO)).replace(hour=h, minute=m, second=0, microsecond=0) - timedelta(minutes=10)
    elenco = treni.partenze(codice, q)
    print(f"Partenze lette: {len(elenco)}")
    for t in elenco[:12]:
        print(" ", treni._ora_partenza(t), "per", str(t.get("destinazione", "")).title(), "| n.", t.get("numeroTreno"), "| ritardo", t.get("ritardo"), "| provvedimento", t.get("provvedimento"))
    print()
    print(treni.stato(ora))
except treni.TreniError as e:
    print("PROBLEMA:", e)
