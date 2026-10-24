// Programma di appoggio di Jarvis per WhatsApp, senza finestre: invia, riceve e ARCHIVIA i messaggi delle chat singole e dei gruppi (si INVIA solo a numeri singoli).
// L'archivio sta solo sul PC, cifrato (memoria/whatsapp/archivio.bin): mai su GitHub, mai nei registri.
// Ascolta solo su 127.0.0.1 e vuole una chiave (memoria/whatsapp/token.txt). Non scrive mai i messaggi su disco ne' nei registri.
// I dati del collegamento (come una password) stanno in memoria/whatsapp/auth, solo sul PC di Andrea.
// Lo avvia Jarvis quando serve e si chiude insieme a Jarvis: non resta acceso da solo.
import { createServer } from 'node:http';
import { randomBytes } from 'node:crypto';
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { exec } from 'node:child_process';
import { lookup } from 'node:dns/promises';
import { connect } from 'node:net';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import { registra, registraStorico, impostaNomi, impostaMiei, gruppoNoto, gruppoSenzaNome, nomeGruppo, elenco, leggi, cerca, totali, abilitaArchivio, salvaSubito } from './messaggi.js';
import makeWASocket, { useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, fetchLatestWaWebVersion, Browsers } from '@whiskeysockets/baileys';

const QUI = dirname(fileURLToPath(import.meta.url));
const DATI = join(QUI, '..', 'memoria', 'whatsapp');
const AUTH = join(DATI, 'auth');
const PORTA = 8787;
const MOSTRA_QR = process.argv.includes('--collega');
const NUMERO = (process.argv.find((a) => a.startsWith('--numero=')) || '').slice(9).replace(/\D/g, '');  // collegamento con codice al posto del QR
let codiceChiesto = false;
mkdirSync(AUTH, { recursive: true });

const TOKEN_FILE = join(DATI, 'token.txt');
if (!existsSync(TOKEN_FILE)) writeFileSync(TOKEN_FILE, randomBytes(32).toString('hex'));
const TOKEN = readFileSync(TOKEN_FILE, 'utf8').trim();

abilitaArchivio(join(DATI, 'archivio.bin'), join(DATI, 'archivio.key'));  // i messaggi si salvano cifrati sul PC e si ritrovano all'accensione
// Il codice si vede anche in una pagina del browser (il disegno nella finestra nera a volte e' troppo grande o storto)
async function apriQrNelBrowser(testo) {
  try {
    const { default: QR } = await import('qrcode');
    const img = await QR.toDataURL(testo, { width: 420, margin: 2 });
    const file = join(DATI, 'qr.html');
    writeFileSync(file, `<!doctype html><meta charset="utf-8"><title>Collega WhatsApp</title><body style="font-family:sans-serif;text-align:center;background:#fff;color:#000"><h2>Scansiona con WhatsApp</h2><p>Telefono: WhatsApp &gt; Impostazioni &gt; Dispositivi collegati &gt; Collega un dispositivo</p><img src="${img}"><p>Il codice cambia ogni ~20 secondi: se non funziona, guarda la finestra nera e riprova con il nuovo.</p></body>`);
    if (process.platform === 'win32') exec(`start "" "${file}"`);
    console.log('Ho aperto il codice anche nel browser (file memoria\\whatsapp\\qr.html).');
  } catch (e) { console.log('(Non riesco ad aprire il codice nel browser: usa quello qui sopra.)'); }
}
const stato = { connesso: false, bisogna_qr: false, bloccato: false, errore: '', storia: { ricevuta: 0, ultimo: 0 } };
let sock = null;
// Se la connessione si chiude di continuo, controlla se il PC raggiunge WhatsApp e lo dice in parole semplici
async function controlloRete() {
  try {
    const a = await lookup('web.whatsapp.com');
    console.log(`  Rete: l'indirizzo di WhatsApp si trova (${a.address}).`);
    await new Promise((ok, no) => { const c = connect({ host: a.address, port: 443, timeout: 6000 }, () => { c.destroy(); ok(); }); c.on('error', no); c.on('timeout', () => { c.destroy(); no(new Error('nessuna risposta in 6 secondi')); }); });
    console.log('  Rete: la porta di WhatsApp risponde. Provo il collegamento sicuro...');
    console.log('  Programma: Node ' + process.version);
    const { default: WS } = await import('ws');
    await new Promise((ok) => {
      const w = new WS('wss://web.whatsapp.com/ws/chat', { headers: { Origin: 'https://web.whatsapp.com' }, handshakeTimeout: 8000 });
      const fine = setTimeout(() => { console.log('  Collegamento sicuro: nessuna risposta in 10 secondi.'); try { w.terminate(); } catch (e) {} ok(); }, 10000);
      w.on('open', () => { console.log('  Collegamento sicuro: APERTO (poi WhatsApp lo chiude da solo).'); clearTimeout(fine); w.close(); ok(); });
      w.on('error', (e) => { console.log('  Collegamento sicuro: ERRORE -> ' + String(e.code || '') + ' ' + String(e.message || e).slice(0, 120)); clearTimeout(fine); ok(); });
      w.on('close', (c) => { console.log('  Collegamento sicuro: chiuso, codice ' + c); });
    });
  } catch (e) { console.log("  Rete: NON raggiungo WhatsApp (" + String(e.message || e).slice(0, 80) + "). Controlla internet, VPN/Tailscale, antivirus o firewall."); }
}
let chiusure = 0;  // chiusure di fila senza arrivare al collegamento: dopo 3 si riprova in modo semplice (senza storia)

async function avvia() {
  if (MOSTRA_QR) console.log('Mi collego a WhatsApp, attendi qualche secondo...');
  const { state, saveCreds } = await useMultiFileAuthState(AUTH);
  // La versione di WhatsApp dichiarata conta: se e' vecchia, WhatsApp chiude la connessione. Si provano tre fonti a rotazione.
  const fonte = chiusure % 3;  // 0 = versione vera del sito di WhatsApp, 1 = elenco della libreria, 2 = quella inclusa nel programma
  let version;
  if (fonte === 0) { const r = await fetchLatestWaWebVersion(); version = r.isLatest ? r.version : (await fetchLatestBaileysVersion()).version; }
  else if (fonte === 1) version = (await fetchLatestBaileysVersion()).version;
  if (MOSTRA_QR && chiusure > 0) console.log('  (versione di WhatsApp: ' + (version ? version.join('.') : 'quella inclusa nel programma') + ')');
  sock = makeWASocket({ ...(version ? { version } : {}), auth: state, logger: pino({ level: MOSTRA_QR ? 'warn' : 'silent' }), browser: Browsers.macOS('Desktop'), ...(chiusure >= 3 ? {} : { syncFullHistory: true, shouldSyncHistoryMessage: () => true }), markOnlineOnConnect: false });  // la storia vecchia arriva una volta sola, subito dopo il collegamento
  sock.ev.on('creds.update', saveCreds);
  const nomiRichiesti = new Set();
  const cercaNomeGruppo = async (jid) => {  // il nome del gruppo si chiede una volta sola a WhatsApp
    if (nomiRichiesti.has(jid) || !gruppoSenzaNome(jid)) return;
    nomiRichiesti.add(jid);
    try { const g = await sock.groupMetadata(jid); nomeGruppo(jid, g?.subject); } catch (e) {}
  };
  sock.ev.on('messages.upsert', ({ messages }) => { for (const m of messages || []) { try { registra(m); const j = m?.key?.remoteJid || ''; if (j.endsWith('@g.us')) cercaNomeGruppo(j); } catch (e) {} } });
  sock.ev.on('groups.upsert', (gs) => { try { impostaNomi((gs || []).map((g) => ({ id: g.id, name: g.subject }))); } catch (e) {} });
  sock.ev.on('messaging-history.set', (h) => {
    try {
      const n = registraStorico(h);
      for (const c of h.chats || []) if (String(c.id || '').endsWith('@g.us')) cercaNomeGruppo(c.id);
      stato.storia.ricevuta += n; stato.storia.ultimo = Date.now();
      if (MOSTRA_QR) process.stdout.write(`\rStorico scaricato: ${stato.storia.ricevuta} messaggi (${totali().chat} chat)...   `);
    } catch (e) {}
  });
  sock.ev.on('contacts.upsert', (c) => { try { impostaNomi(c); } catch (e) {} });
  sock.ev.on('connection.update', async (u) => {
    if (u.qr && NUMERO && MOSTRA_QR && !codiceChiesto && !state.creds.registered) {
      codiceChiesto = true;
      try {
        const c = await sock.requestPairingCode(NUMERO);
        console.log(`\nCODICE DA SCRIVERE SUL TELEFONO: ${c}\nWhatsApp > Impostazioni > Dispositivi collegati > Collega un dispositivo > "Collega con numero di telefono".`);
      } catch (e) { console.log('Non riesco a ottenere il codice: ' + String(e?.message || e).slice(0, 100)); codiceChiesto = false; }
    } else if (u.qr) {
      stato.bisogna_qr = true;
      if (MOSTRA_QR) {
        console.log('\nScansiona questo codice con WhatsApp sul telefono: Impostazioni > Dispositivi collegati > Collega un dispositivo.\n');
        qrcode.generate(u.qr, { small: true });
        apriQrNelBrowser(u.qr);
      }
    }
    if (u.connection === 'open') {
      chiusure = 0;
      try { impostaMiei([sock.user?.id, sock.user?.lid]); } catch (e) {}
      stato.connesso = true; stato.bisogna_qr = false; stato.errore = '';
      if (MOSTRA_QR) {
        console.log("\nCOLLEGATO. Adesso WhatsApp manda la storia dei messaggi: NON chiudere questa finestra finche' non vedi FATTO (puo' volerci qualche minuto).");
        const inizio = Date.now();
        const guardia = setInterval(() => {
          const quieto = Date.now() - Math.max(stato.storia.ultimo, inizio);
          if ((stato.storia.ricevuta > 0 && quieto > 60000) || quieto > 240000) {
            clearInterval(guardia);
            try { salvaSubito(); } catch (e) {}
            const t = totali();
            console.log(`\nFATTO. Ho salvato ${t.messaggi} messaggi di ${t.chat} chat sul tuo PC (cifrati). Ora puoi chiudere questa finestra: Jarvis usa il collegamento da solo.`);
            if (!stato.storia.ricevuta) console.log("(WhatsApp non ha mandato la storia vecchia: da adesso in poi i messaggi nuovi si salvano da soli.)");
          }
        }, 5000);
      }
    }
    if (u.connection === 'close') {
      stato.connesso = false;
      chiusure++;
      if (MOSTRA_QR && chiusure === 2) await controlloRete();
      if (MOSTRA_QR && chiusure === 3) console.log('(Riprovo in modo semplice, senza scaricare la storia vecchia.)');
      const codice = u.lastDisconnect?.error?.output?.statusCode;
      if (MOSTRA_QR) console.log(`(connessione chiusa, codice ${codice ?? '?'}: ${String(u.lastDisconnect?.error?.message || '').slice(0, 80)} - riprovo)`);
      if (codice === DisconnectReason.loggedOut) {
        stato.errore = 'Il telefono ha scollegato Jarvis: va rifatto il collegamento con il codice.';
        stato.bisogna_qr = true;
        return;
      }
      if (codice === DisconnectReason.forbidden) {
        stato.bloccato = true;
        stato.errore = "WhatsApp ha limitato il numero. Jarvis non invia piu' messaggi.";
        return;
      }
      setTimeout(() => avvia().catch((e) => { if (MOSTRA_QR) console.log('ERRORE: ' + String(e?.message || e).slice(0, 200)); }), 3000);
    }
  });
}

// Coda: un messaggio alla volta, con una pausa di qualche secondo, come farebbe una persona.
let coda = Promise.resolve();
const attesa = (ms) => new Promise((r) => setTimeout(r, ms));
let ultimo = 0;

function invia(numero, testo, gruppo = '') {
  const lavoro = coda.then(async () => {
    if (stato.bloccato) throw new Error(stato.errore);
    if (!stato.connesso) throw new Error("WhatsApp non e' collegato.");
    const pausa = 5000 + Math.random() * 7000;
    const gia = Date.now() - ultimo;
    if (gia < pausa) await attesa(pausa - gia);
    let jid = gruppo;  // un gruppo che c'e' gia' nell'archivio (mai un indirizzo mandato da fuori)
    if (!gruppo) {
      const [esiste] = (await sock.onWhatsApp(numero)) || [];
      if (!esiste?.exists) throw new Error('Quel numero non risulta su WhatsApp.');
      jid = esiste.jid;
    }
    await sock.presenceSubscribe(jid);
    await sock.sendPresenceUpdate('composing', jid);
    await attesa(Math.min(1000 + testo.length * 40, 4000));
    await sock.sendMessage(jid, { text: testo });
    await sock.sendPresenceUpdate('paused', jid);
    ultimo = Date.now();
  });
  coda = lavoro.catch(() => {});
  return lavoro;
}

function leggiCorpo(req) {
  return new Promise((ok, no) => {
    let d = '';
    req.on('data', (c) => { d += c; if (d.length > 20000) { no(new Error('troppo grande')); req.destroy(); } });
    req.on('end', () => { try { ok(JSON.parse(d || '{}')); } catch (e) { no(e); } });
  });
}

const rispondi = (res, codice, obj) => { res.writeHead(codice, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(obj)); };

createServer(async (req, res) => {
  const host = req.headers.host || '';
  if (host !== `127.0.0.1:${PORTA}` && host !== `localhost:${PORTA}`) return rispondi(res, 403, { ok: false, errore: 'host non ammesso' });
  if (req.headers['x-token'] !== TOKEN) return rispondi(res, 401, { ok: false, errore: 'non autorizzato' });
  if (req.method === 'GET' && req.url === '/stato') return rispondi(res, 200, { ok: true, ...stato, archivio: totali() });
  if (req.method === 'GET' && (req.url === '/chat' || req.url === '/chat?tutte=1')) return rispondi(res, 200, { ok: true, chat: elenco(req.url.endsWith('tutte=1')) });
  if (req.method === 'GET' && req.url.startsWith('/cerca?')) {
    const q = new URL(req.url, 'http://x').searchParams;
    return rispondi(res, 200, { ok: true, trovati: cerca({ q: q.get('q') || '', chat: q.get('chat') || '', giorni: Number(q.get('giorni') || 0), n: Number(q.get('n') || 15) }) });
  }
  if (req.method === 'POST' && req.url === '/salva') { try { salvaSubito(); } catch (e) {} return rispondi(res, 200, { ok: true }); }
  if (req.method === 'GET' && req.url.startsWith('/messaggi?')) {
    const q = new URL(req.url, 'http://x').searchParams;
    const r = leggi(q.get('id') || '', Number(q.get('n') || 10), q.get('segna') !== '0');
    return rispondi(res, r ? 200 : 404, r ? { ok: true, ...r } : { ok: false, errore: 'chat non trovata' });
  }
  if (req.method === 'POST' && req.url === '/invia') {
    try {
      const { numero, testo, gruppo } = await leggiCorpo(req);
      const valido = gruppo ? (/^\d{5,}(-\d+)?@g\.us$/.test(String(gruppo)) && gruppoNoto(String(gruppo))) : /^\d{8,15}$/.test(String(numero || ''));
      if (!valido || !String(testo || '').trim() || String(testo).length > 1000) {
        return rispondi(res, 400, { ok: false, errore: 'dati non validi' });
      }
      await invia(String(numero || ''), String(testo), gruppo ? String(gruppo) : '');
      return rispondi(res, 200, { ok: true });
    } catch (e) {
      return rispondi(res, 200, { ok: false, errore: String(e.message || e).slice(0, 200) });
    }
  }
  rispondi(res, 404, { ok: false, errore: 'non trovato' });
}).listen(PORTA, '127.0.0.1');

// Se Jarvis si chiude, si chiude anche questo programma (Jarvis lo avvia con un canale aperto).
if (process.send || process.env.JARVIS_FIGLIO) process.stdin.on('end', () => process.exit(0)).resume();
process.on('exit', () => { try { salvaSubito(); } catch (e) {} });  // alla chiusura normale si salva tutto

avvia().catch((e) => { stato.errore = 'Avvio non riuscito: ' + String(e.message || e).slice(0, 120); if (MOSTRA_QR) console.log('ERRORE: ' + stato.errore); });
