// Programma di appoggio di Jarvis per WhatsApp: SOLO INVIO, senza finestre.
// Ascolta solo su 127.0.0.1 e vuole una chiave (memoria/whatsapp/token.txt). Non scrive mai i messaggi su disco ne' nei registri.
// I dati del collegamento (come una password) stanno in memoria/whatsapp/auth, solo sul PC di Andrea.
// Lo avvia Jarvis quando serve e si chiude insieme a Jarvis: non resta acceso da solo.
import { createServer } from 'node:http';
import { randomBytes } from 'node:crypto';
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import pino from 'pino';
import qrcode from 'qrcode-terminal';
import makeWASocket, { useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, Browsers } from '@whiskeysockets/baileys';

const QUI = dirname(fileURLToPath(import.meta.url));
const DATI = join(QUI, '..', 'memoria', 'whatsapp');
const AUTH = join(DATI, 'auth');
const PORTA = 8787;
const MOSTRA_QR = process.argv.includes('--collega');
mkdirSync(AUTH, { recursive: true });

const TOKEN_FILE = join(DATI, 'token.txt');
if (!existsSync(TOKEN_FILE)) writeFileSync(TOKEN_FILE, randomBytes(32).toString('hex'));
const TOKEN = readFileSync(TOKEN_FILE, 'utf8').trim();

const stato = { connesso: false, bisogna_qr: false, bloccato: false, errore: '' };
let sock = null;

async function avvia() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH);
  const { version } = await fetchLatestBaileysVersion();
  sock = makeWASocket({ version, auth: state, logger: pino({ level: 'silent' }), browser: Browsers.macOS('Desktop'), syncFullHistory: false, markOnlineOnConnect: false });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (u) => {
    if (u.qr) {
      stato.bisogna_qr = true;
      if (MOSTRA_QR) {
        console.log('\nScansiona questo codice con WhatsApp sul telefono: Impostazioni > Dispositivi collegati > Collega un dispositivo.\n');
        qrcode.generate(u.qr, { small: true });
      }
    }
    if (u.connection === 'open') {
      stato.connesso = true; stato.bisogna_qr = false; stato.errore = '';
      if (MOSTRA_QR) console.log('\nCOLLEGATO. Ora puoi chiudere questa finestra: Jarvis usa il collegamento da solo, senza finestre.');
    }
    if (u.connection === 'close') {
      stato.connesso = false;
      const codice = u.lastDisconnect?.error?.output?.statusCode;
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
      setTimeout(() => avvia().catch(() => {}), 3000);
    }
  });
}

// Coda: un messaggio alla volta, con una pausa di qualche secondo, come farebbe una persona.
let coda = Promise.resolve();
const attesa = (ms) => new Promise((r) => setTimeout(r, ms));
let ultimo = 0;

function invia(numero, testo) {
  const lavoro = coda.then(async () => {
    if (stato.bloccato) throw new Error(stato.errore);
    if (!stato.connesso) throw new Error("WhatsApp non e' collegato.");
    const pausa = 5000 + Math.random() * 7000;
    const gia = Date.now() - ultimo;
    if (gia < pausa) await attesa(pausa - gia);
    const [esiste] = (await sock.onWhatsApp(numero)) || [];
    if (!esiste?.exists) throw new Error('Quel numero non risulta su WhatsApp.');
    const jid = esiste.jid;
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
  if (req.method === 'GET' && req.url === '/stato') return rispondi(res, 200, { ok: true, ...stato });
  if (req.method === 'POST' && req.url === '/invia') {
    try {
      const { numero, testo } = await leggiCorpo(req);
      if (!/^\d{8,15}$/.test(String(numero || '')) || !String(testo || '').trim() || String(testo).length > 1000) {
        return rispondi(res, 400, { ok: false, errore: 'dati non validi' });
      }
      await invia(String(numero), String(testo));
      return rispondi(res, 200, { ok: true });
    } catch (e) {
      return rispondi(res, 200, { ok: false, errore: String(e.message || e).slice(0, 200) });
    }
  }
  rispondi(res, 404, { ok: false, errore: 'non trovato' });
}).listen(PORTA, '127.0.0.1');

// Se Jarvis si chiude, si chiude anche questo programma (Jarvis lo avvia con un canale aperto).
if (process.send || process.env.JARVIS_FIGLIO) process.stdin.on('end', () => process.exit(0)).resume();

avvia().catch((e) => { stato.errore = 'Avvio non riuscito: ' + String(e.message || e).slice(0, 120); });
