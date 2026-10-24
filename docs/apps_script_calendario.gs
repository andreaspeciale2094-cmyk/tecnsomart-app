// Jarvis: scrittura di appuntamenti sul calendario Google. Va incollato in un progetto Apps Script nell'account di Andrea.
// SOLO CREARE: non cancella e non modifica niente. Jarvis lo chiama soltanto dopo il "Si" di Andrea sulla scheda.
// 1) Sostituisci CHIAVE_QUI con una chiave lunga e casuale (almeno 32 caratteri): la stessa chiave sta nell'indirizzo che Jarvis usa (?k=...).
// 2) Ci vogliono DUE copie di questo programma, una per ciascun account Google di Andrea (personale e lavoro): ognuna scrive sul calendario principale del PROPRIO account.
//    Ogni copia ha la sua chiave e il suo indirizzo (in Jarvis: memoria/calendario_url.txt per il personale, memoria/calendario_lavoro_url.txt per il lavoro).
// 3) Distribuisci > Nuova distribuzione > App web > "Esegui come: me" > "Chi ha accesso: Chiunque" (l'accesso e' protetto dalla chiave).
const CHIAVE = 'CHIAVE_QUI';
const FUSO = 'Europe/Rome';

function uscita_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.k !== CHIAVE || CHIAVE === 'CHIAVE_QUI') return uscita_({ ok: false, errore: 'non autorizzato' });
  const cal = CalendarApp.getDefaultCalendar();
  if (!cal) return uscita_({ ok: false, errore: 'calendario non trovato' });
  const inizio = Utilities.parseDate(String(p.inizio || ''), FUSO, "yyyy-MM-dd'T'HH:mm");
  const fine = Utilities.parseDate(String(p.fine || ''), FUSO, "yyyy-MM-dd'T'HH:mm");
  if (!(fine > inizio)) return uscita_({ ok: false, errore: 'orari non validi' });
  const titolo = String(p.titolo || '').slice(0, 120);
  const esistenti = cal.getEvents(inizio, fine).map(function (ev) { return { titolo: ev.getTitle(), inizio: Utilities.formatDate(ev.getStartTime(), FUSO, 'HH:mm') }; });
  const uguale = cal.getEvents(inizio, fine).some(function (ev) { return ev.getStartTime().getTime() === inizio.getTime() && ev.getTitle().toLowerCase() === titolo.toLowerCase(); });
  if (p.azione === 'controlla') return uscita_({ ok: true, conflitti: esistenti, gia_presente: uguale });
  if (p.azione !== 'crea') return uscita_({ ok: false, errore: 'azione sconosciuta' });
  if (uguale) return uscita_({ ok: true, gia_presente: true });
  cal.createEvent(titolo, inizio, fine, { location: String(p.luogo || '').slice(0, 200), description: 'Aggiunto da Jarvis dopo conferma' });
  return uscita_({ ok: true, creato: true, conflitti: esistenti });
}
