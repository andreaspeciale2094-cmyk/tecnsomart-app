"""Prova veloce degli avvisi sul telefono: 1) manda subito un messaggio di prova su Telegram, 2) mostra per 10 secondi da quanti secondi non tocchi il PC (e' il numero che Jarvis guarda).
Non mostra chiavi: la configurazione si legge dal .env senza stamparla."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import config, presenza, telegram_bot

print("=== 1) Messaggio di prova su Telegram ===")
if not config.ENABLE_TELEGRAM:
    print("Telegram e' spento: nel file .env manca JARVIS_TELEGRAM=true.")
elif not config.TELEGRAM_TOKEN:
    print("Manca TELEGRAM_TOKEN nel file .env.")
elif not str(config.TELEGRAM_USER_ID).strip().lstrip("-").isdigit():
    print("Manca TELEGRAM_USER_ID nel file .env (scrivi al bot su Telegram: ti dice il numero da mettere).")
else:
    try:
        telegram_bot._scrivi(int(config.TELEGRAM_USER_ID), "Prova di Jarvis: se leggi questo, gli avvisi sul telefono funzionano.")
        print("Fatto: guarda il telefono, dovrebbe essere arrivato un messaggio.")
    except Exception as e:
        print("Non sono riuscito a mandarlo:", type(e).__name__, "(controlla internet e il TELEGRAM_TOKEN)")

print("\n=== 2) Da quanti secondi non tocchi il PC (non muovere il mouse per vederlo salire) ===")
print(f"Jarvis ti considera lontano da {int(config.TELEGRAM_ASSENTE_S)} secondi in su.")
for _ in range(10):
    print(f"  non tocchi il PC da {int(presenza.inattivo_s())} secondi")
    time.sleep(1)
