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

## Funzioni avanzate

- **Voce naturale:** con `ELEVENLABS_API_KEY` (o `OPENAI_API_KEY`) Jarvis risponde con una voce neurale; con `OPENAI_API_KEY` il microfono usa Whisper (premi per parlare, premi ancora per inviare). Senza chiavi ripiega sulla voce del browser. Il pulsante 👂 (parola d'ordine "Jarvis") usa sempre il riconoscimento del browser.
- **Briefing e attivita' pianificate:** imposta `BRIEFING_TIME=07:30` per il briefing mattutino (calendario, mail, promemoria). Puoi anche dire "ogni giorno alle 18 ricordami di..." o "ogni 30 minuti controlla le mail": Jarvis usa `schedule_task`. I risultati arrivano in 📬 (con notifica del browser e lettura vocale). Il server deve restare acceso.
- **Agenti in background:** per compiti lunghi ("fammi un'analisi di...") Jarvis avvia `background_task` e ti avvisa quando ha finito. Gli agenti in background non possono eseguire comandi sul PC ne' creare altri agenti.
- **Memoria semantica:** ritrova i ricordi per significato. Con `OPENAI_API_KEY` usa embedding reali; senza, un embedding locale a n-grammi.
- **Login:** imposta `JARVIS_PASSWORD`; tutte le API richiedono il cookie di sessione (max 5 tentativi al minuto per IP).

## Sicurezza

- Il controllo del PC (`run_shell`, file) e' **spento** finche' non metti `JARVIS_PC_CONTROL=true`; i file sono confinati in `JARVIS_WORKDIR`.
- Senza `JARVIS_PASSWORD` l'app non ha autenticazione: tienila su `localhost`. Se la esponi (telefono, rete), imposta la password e mettila dietro HTTPS (es. Caddy, Tailscale o Cloudflare Tunnel).
- Mail e calendario sono in sola lettura.

## Prossimi passi

App mobile nativa/PWA con notifiche push, wake word sempre attiva lato server, integrazione Google OAuth (invio mail, creazione eventi), visione (webcam/screenshot).
