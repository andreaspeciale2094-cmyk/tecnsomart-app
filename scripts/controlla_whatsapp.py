"""Solo lettura, solo sul tuo schermo: com'e' fatto l'archivio di WhatsApp, chat per chat (tipo, numero si'/no, ultimi messaggi: chi, ora, lunghezza).
NON mostra i testi dei messaggi. Serve per capire perche' una chat risulta 'senza nome' o un messaggio sembra ricevuto invece che inviato."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from jarvis import whatsapp

try:
    chat = whatsapp._helper_json("/chat?tutte=1").get("chat", [])
except Exception as e:
    print("WhatsApp non risponde:", e)
    raise SystemExit
print(f"{len(chat)} chat in archivio. Le piu' recenti:\n")
for c in chat[:12]:
    tipo = "GRUPPO" if c.get("gruppo") else ("codice nascosto" if c["id"].endswith("@lid") else "numero")
    nome = c.get("nome") or "(senza nome)"
    print(f"- {nome} | {tipo} | numero {'si' if c.get('numero') else 'NO'} | non lette {c['non_lette']}")
    r = whatsapp._helper_json("/messaggi?id=" + whatsapp.quote(c["id"]) + "&n=3&segna=0")
    for m in r.get("messaggi", []):
        print(f"    {datetime.fromtimestamp(m['ts']):%d/%m %H:%M}  {'MIO ' if m['da_me'] else 'LORO'}  ({len(m['testo'])} caratteri)")
