"""Carica openWakeWord senza scipy e scikit-learn, che a noi non servono (servono solo per addestrare modelli personalizzati)
e su alcuni PC non si caricano. Va importato PRIMA di openwakeword."""
import sys
import types

if "openwakeword.custom_verifier_model" not in sys.modules:
    _finto = types.ModuleType("openwakeword.custom_verifier_model")
    _finto.train_custom_verifier = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("addestramento non disponibile in Jarvis"))
    sys.modules["openwakeword.custom_verifier_model"] = _finto

import openwakeword  # noqa: E402,F401
from openwakeword.model import Model  # noqa: E402,F401
from openwakeword.utils import download_models  # noqa: E402,F401
from openwakeword.vad import VAD  # noqa: E402,F401
