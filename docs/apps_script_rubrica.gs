// Jarvis: lettura dei contatti Google, SOLA LETTURA. Va incollato in un progetto Apps Script nell'account di Andrea.
// 1) Sostituisci CHIAVE_QUI con una chiave lunga e casuale (almeno 32 caratteri). La stessa chiave sta nell'indirizzo che Jarvis usa (?k=...).
// 2) In "Servizi" aggiungi "People API" (identificatore: People).
// 3) Distribuisci > Nuova distribuzione > App web > "Esegui come: me" > "Chi ha accesso: Chiunque" (l'accesso e' protetto dalla chiave).
const CHIAVE = 'CHIAVE_QUI';

function doGet(e) {
  if (!e || !e.parameter || e.parameter.k !== CHIAVE || CHIAVE === 'CHIAVE_QUI') {
    return ContentService.createTextOutput(JSON.stringify({ errore: 'non autorizzato' })).setMimeType(ContentService.MimeType.JSON);
  }
  const contatti = [];
  let pagina = null;
  do {
    const r = People.People.Connections.list('people/me', { personFields: 'names,phoneNumbers', pageSize: 1000, pageToken: pagina });
    (r.connections || []).forEach(function (p) {
      const nome = (p.names && p.names[0] && p.names[0].displayName) || '';
      const numeri = (p.phoneNumbers || []).map(function (n) { return n.canonicalForm || n.value; }).filter(Boolean);
      if (nome && numeri.length) contatti.push({ nome: nome, numeri: numeri });
    });
    pagina = r.nextPageToken;
  } while (pagina);
  return ContentService.createTextOutput(JSON.stringify({ contatti: contatti })).setMimeType(ContentService.MimeType.JSON);
}
