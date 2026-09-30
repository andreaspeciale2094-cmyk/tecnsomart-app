# Jarvis

Assistente personale stile Jarvis: **Claude come cervello**, memoria a lungo termine, voce, web, mail/calendario, domotica e controllo del PC.

## Avvio

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # inserisci ANTHROPIC_API_KEY
uvicorn jarvis.server:app --reload
```

Apri http://localhost:8000 con **Chrome o Edge** (servono per il riconoscimento vocale).
Di' "Jarvis, ..." con il pulsante 👂 attivo, oppure usa il microfono 🎤.

## Architettura

| Parte | File | Note |
|---|---|---|
| Cervello | `jarvis/brain.py` | Claude con ciclo agentico di tool use + ricerca web lato server |
| Memoria | `jarvis/memory.py` | Fatti in SQLite, iniettati nel prompt a ogni turno; Jarvis li salva da solo |
| Tool | `jarvis/tools/` | `web`, `pc`, `home`, `mail_calendar`, `memory_tools` |
| Interfaccia | `static/index.html` | Chat + voce (Web Speech API) |

**Aggiungere un'abilita':** crea un modulo in `jarvis/tools/` con `SCHEMAS` e `HANDLERS` e registralo in `tools/__init__.py`.

## Sicurezza

- Il controllo del PC (`run_shell`, file) e' **spento** finche' non metti `JARVIS_PC_CONTROL=true`; i file sono confinati in `JARVIS_WORKDIR`.
- L'app non ha autenticazione: tienila su `localhost`. Non esporla su internet senza login.
- Mail e calendario sono in sola lettura.

## Prossimi passi

Voce piu' naturale (ElevenLabs/Whisper), app mobile, azioni proattive (briefing mattutino), agenti in background, memoria semantica con embedding.
