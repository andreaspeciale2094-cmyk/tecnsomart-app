"""Prova dell'ascolto con la tua voce: mostra un punteggio quando dici "Hey Jarvis". Non registra e non invia niente.
Uso: .venv\\Scripts\\python.exe scripts\\prova_ascolto.py   (dura 40 secondi; Ctrl+C per fermare)"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import sounddevice as sd  # noqa: E402
from openwakeword.model import Model  # noqa: E402
from openwakeword.utils import download_models  # noqa: E402

from jarvis import config  # noqa: E402


def main():
    print("Microfoni trovati:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  {i}: {d['name']}")
    try:
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    except Exception:
        print("Scarico i modelli (una volta sola)...")
        download_models(["hey_jarvis"])
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    print(f"\nDi' 'Hey Jarvis' a voce normale. Soglia attuale: {config.ASCOLTO_SOGLIA}. Dura 40 secondi.\n")
    massimo, fine = 0.0, time.time() + 40
    with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280, device=config.ASCOLTO_DISPOSITIVO or None) as s:
        while time.time() < fine:
            p = float(model.predict(s.read(1280)[0][:, 0].copy()).get("hey_jarvis", 0))
            massimo = max(massimo, p)
            if p > 0.15:
                print(f"  punteggio {p:.2f} " + "#" * int(p * 30) + ("   <-- RISVEGLIATO" if p >= config.ASCOLTO_SOGLIA else ""))
    print(f"\nPunteggio massimo: {massimo:.2f}. Se e' sotto {config.ASCOLTO_SOGLIA}, abbassa ASCOLTO_SOGLIA nel .env (per esempio 0.3).")


main()
