# Prove da fare (elenco di Andrea)

Segna con [x] quando provato. Dopo ogni prova dire a Jarvis/Claude com'e' andata.

## Subito
- [ ] Icone vere nella barra in basso (WhatsApp, app Tecno, altre app dello Store/Chrome)
- [ ] Avviso Telegram quando sei lontano: "ricordami tra 5 minuti di bere", poi 3 minuti senza toccare il PC
- [ ] Treno: dire "domani faccio apertura/chiusura"; avviso ~28 min prima; ritardo/cancellazione anticipati
- [ ] Trenord: `controlla_trenord.bat` e, con un treno davvero in ritardo, controllare che lo legga

## Telefono / account
- [ ] Calendari Google (due account): collegamento, "Si', aggiungi", calendario a voce
- [ ] Chiamate perse: macro MacroDroid verso Jarvis
- [ ] Cambio nome contatto dal telefono -> rubrica

## Amazon
- [ ] Ricerca veloce (browser tenuto acceso) e carrello solo dopo il "si'"

## Velocita' e voce
- [ ] Modello rapido e cache 1 ora (righe 'letto da cache' in logs\consumi.log)
- [ ] Voce: parole in maiuscolo non piu' "spagnole"; frasi d'attesa nuove
- [ ] Risposte veloci: ore, meteo, impegni, appunti, promemoria a voce

## Agenti
- [ ] Negozi: "come sono andati i negozi" (solo cio' che e' stato fatto), un negozio solo
- [ ] WhatsApp senza risposta (9-21), addetti indietro (lunedi'), banca sopra 50 euro
- [ ] Obiettivi del lunedi', resoconto della settimana (domenica sera), agente "domani"
- [ ] "Concludi la giornata": resoconto + diario degli agenti
- [ ] Salute di Jarvis, guardiano dei consumi, backup settimanale

## Notizie e siti
- [ ] `controlla_notizie.bat`: quali giornali rispondono
- [ ] "novita' su Milano", "notizie sul Milan", "cosa e' successo in politica"
- [ ] Primo sito: "fammi un sito vetrina..." e anteprima

## Agenti scioperi / Milan / meteo
- [ ] Sciopero treni: scheda quando un giornale ne parla (si vede solo se ce n'e' uno)
- [ ] Milan: scheda con formazioni prima della partita e risultato dopo
- [ ] Meteo: avviso con temporale o pioggia forte in arrivo
- [ ] Sky Go: con Display Portal scollegato non si blocca

## Turni, sveglia, fine ciclo
- [ ] Dire a Jarvis i turni della settimana ("lunedi apertura, martedi chiusura...") e controllare che li ripeta
- [ ] La sera: "Domani apertura: sveglia alle 7:20..."
- [ ] Chiusura: sveglia alle 9:00; prova a dire "domani chiusura, sveglia alle 8:30"

## Altre prove rimaste
- [ ] Interruzioni a voce (pezzo 4 Fase 2) e fermare Jarvis mentre parla
- [ ] Riconoscimento della tua voce
- [ ] Jarvis acceso col coperchio chiuso (se attivato)
- [ ] Jarvis al posto del desktop di Windows (se attivato)
- [ ] Fase 3: `scripts/prova_riassunto.py`

## Da ricordare
- Tetto di spesa 25 dollari sulla Console Anthropic: lo imposta Andrea
- Punto debole: `DEFAULT_PASSWORD` in chiaro in Codice.gs
