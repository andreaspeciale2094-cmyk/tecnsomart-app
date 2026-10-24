// Archivio dei messaggi WhatsApp (chat singole e, dal 24/10 su richiesta di Andrea, anche i gruppi; mai stati e canali). Sta SOLO sul PC di Andrea, in memoria/whatsapp/archivio.bin,
// CIFRATO (AES-256-GCM, chiave in memoria/whatsapp/archivio.key): mai su GitHub, mai nei registri. Chi ha accesso ai file del PC potrebbe comunque
// leggerlo: la cifratura protegge dallo sguardo distratto, non da chi ha in mano il PC.
// Funzioni pure o quasi, cosi' si provano senza collegarsi a WhatsApp.
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';

export const chats = new Map();
export const limiti = { perChat: 5000, chat: 500, etaS: 400 * 24 * 3600 };
let fileArchivio = null, chiaveArchivio = null, timer = null;
export const info = { caricati: 0, salvataggi: 0 };

// ---------- cifratura e salvataggio ----------
function cifra(buf) {
  const iv = randomBytes(12), c = createCipheriv('aes-256-gcm', chiaveArchivio, iv);
  const dati = Buffer.concat([c.update(buf), c.final()]);
  return Buffer.concat([iv, c.getAuthTag(), dati]);
}
function decifra(buf) {
  const d = createDecipheriv('aes-256-gcm', chiaveArchivio, buf.subarray(0, 12));
  d.setAuthTag(buf.subarray(12, 28));
  return Buffer.concat([d.update(buf.subarray(28)), d.final()]);
}

export function abilitaArchivio(percorsoFile, percorsoChiave) {
  fileArchivio = percorsoFile;
  if (!existsSync(percorsoChiave)) writeFileSync(percorsoChiave, randomBytes(32).toString('hex'));
  chiaveArchivio = Buffer.from(readFileSync(percorsoChiave, 'utf8').trim(), 'hex');
  if (existsSync(percorsoFile)) {
    try {
      for (const c of JSON.parse(decifra(readFileSync(percorsoFile)).toString('utf8'))) { preparaChat(c); chats.set(c.id, c); }
    } catch (e) {  // file illeggibile (chiave cambiata o file rovinato): lo si mette da parte, senza cancellarlo, e si riparte da zero
      chats.clear();
      try { renameSync(percorsoFile, percorsoFile + '.illeggibile-' + Date.now()); } catch (x) {}
    }
  }
  info.caricati = totali().messaggi;
}

function preparaChat(c) {
  c.ids = new Set(c.msgs.map((m) => m.id).filter(Boolean));
  c.sporca = false;
  return c;
}

export function salvaSubito() {
  if (!fileArchivio) return false;
  if (timer) { clearTimeout(timer); timer = null; }
  const dati = [...chats.values()].map((c) => { ordina(c); return { id: c.id, numero: c.numero, nome: c.nome, gruppo: !!c.gruppo, lettoFino: c.lettoFino, ultimo: c.ultimo, msgs: c.msgs }; });
  const tmp = fileArchivio + '.tmp';
  writeFileSync(tmp, cifra(Buffer.from(JSON.stringify(dati), 'utf8')));
  renameSync(tmp, fileArchivio);
  info.salvataggi++;
  return true;
}

function programmaSalvataggio() {
  if (!fileArchivio || timer) return;
  timer = setTimeout(() => { timer = null; try { salvaSubito(); } catch (e) {} }, 15000);
  timer.unref?.();
}

// ---------- registrazione ----------
export function testoDi(m) {
  const x = m?.message;
  if (!x) return null;
  const inner = x.ephemeralMessage?.message || x.viewOnceMessage?.message || x;
  if (inner.conversation) return inner.conversation;
  if (inner.extendedTextMessage?.text) return inner.extendedTextMessage.text;
  if (inner.imageMessage) return '[foto]' + (inner.imageMessage.caption ? ' ' + inner.imageMessage.caption : '');
  if (inner.videoMessage) return '[video]' + (inner.videoMessage.caption ? ' ' + inner.videoMessage.caption : '');
  if (inner.audioMessage) return `[vocale ${inner.audioMessage.seconds || '?'} secondi]`;
  if (inner.documentMessage) return '[documento]';
  if (inner.stickerMessage) return '[sticker]';
  if (inner.contactMessage) return '[contatto]';
  if (inner.locationMessage) return '[posizione]';
  return null;  // reazioni, protocollo, ecc.: si ignorano
}

function ordina(c) {
  if (c.sporca) { c.msgs.sort((a, b) => a.ts - b.ts); c.sporca = false; }
}

// ---------- identita': lo stesso contatto puo' comparire con il numero (@s.whatsapp.net) o con un codice nascosto (@lid) ----------
const alias = new Map();   // @lid -> @s.whatsapp.net, imparato dai messaggi che hanno tutti e due
const miei = new Set();    // i miei numeri/codici (per riconoscere i miei messaggi mandati da un altro dispositivo)
const norm = (j) => String(j || '').split('@')[0].split(':')[0];
export function impostaMiei(ids) { for (const i of ids || []) if (i) miei.add(norm(i)); }

function unisci(vecchio, nuovo) {  // un contatto trovato con due indirizzi: si riuniscono le due chat in una
  const a = chats.get(vecchio), b = chats.get(nuovo);
  if (!a || !b || a === b) return;
  for (const m of a.msgs) if (!m.id || !b.ids.has(m.id)) { b.msgs.push(m); if (m.id) b.ids.add(m.id); }
  b.nome = b.nome || a.nome; b.numero = b.numero || a.numero;
  b.lettoFino = Math.max(b.lettoFino, a.lettoFino); b.ultimo = Math.max(b.ultimo, a.ultimo); b.sporca = true;
  chats.delete(vecchio);
}

function indirizzo(k) {
  const grezzo = k.remoteJid || '', alt = k.remoteJidAlt || '';
  const telefono = [grezzo, alt].find((j) => j.endsWith('@s.whatsapp.net'));
  const lid = [grezzo, alt].find((j) => j.endsWith('@lid'));
  if (telefono && lid && alias.get(lid) !== telefono) { alias.set(lid, telefono); unisci(lid, telefono); }
  if (telefono) return telefono;
  if (lid) return alias.get(lid) || lid;
  return grezzo || alt;
}

// storico = true per i messaggi della storia vecchia: contano come gia' letti (non gonfiano i "non letti")
export function registra(m, ora = Date.now() / 1000, storico = false) {
  const k = m?.key;
  if (!k) return false;
  const jid = indirizzo(k);
  const gruppo = jid.endsWith('@g.us');
  if (!(jid.endsWith('@s.whatsapp.net') || jid.endsWith('@lid') || gruppo)) return false;  // niente stati e newsletter
  const testo = testoDi(m);
  if (testo == null) return false;
  const ts = Number(m.messageTimestamp?.low ?? m.messageTimestamp ?? ora);
  if (ora - ts > limiti.etaS) return false;
  const numero = jid.endsWith('@s.whatsapp.net') ? jid.split('@')[0].split(':')[0] : '';
  let c = chats.get(jid);
  if (!c) {
    if (chats.size >= limiti.chat) {  // butta la chat meno recente
      const vecchia = [...chats.values()].sort((a, b) => a.ultimo - b.ultimo)[0];
      chats.delete(vecchia.id);
    }
    c = preparaChat({ id: jid, numero, nome: '', gruppo, msgs: [], lettoFino: 0, ultimo: 0 });
    chats.set(jid, c);
  }
  if (k.id && c.ids.has(k.id)) return false;  // gia' registrato (la storia e i messaggi in diretta possono sovrapporsi)
  if (gruppo) c.gruppo = true;
  const mio = !!k.fromMe || (miei.size > 0 && (miei.has(norm(k.participant)) || miei.has(norm(k.participantAlt))));  // anche se l'ho mandato da un altro dispositivo
  if (!mio && m.pushName && !gruppo) c.nome = String(m.pushName).slice(0, 40);
  const msg = { id: k.id || '', da_me: mio, testo: String(testo).slice(0, 1500), ts };
  if (gruppo && !mio) msg.chi = String(m.pushName || (k.participant || '').split('@')[0].split(':')[0] || '').slice(0, 40);  // chi ha scritto nel gruppo
  c.msgs.push(msg);
  if (k.id) c.ids.add(k.id);
  c.sporca = true;
  if (c.msgs.length > limiti.perChat + 200) {  // ogni tanto si buttano i piu' vecchi
    ordina(c);
    for (const x of c.msgs.splice(0, c.msgs.length - limiti.perChat)) if (x.id) c.ids.delete(x.id);
  }
  c.ultimo = Math.max(c.ultimo, ts);
  if (mio || storico) c.lettoFino = Math.max(c.lettoFino, ts);  // se rispondi dal telefono (o e' storia vecchia), conta come letta
  programmaSalvataggio();
  return true;
}

// nomi dei contatti che arrivano con la storia (solo per le chat che esistono gia' o appena create)
export function impostaNomi(elenco) {
  for (const x of elenco || []) {
    const nome = String(x?.name || x?.notify || x?.subject || '').slice(0, 40);
    if (!nome) continue;
    for (const chiave of [x.id, x.lid, x.phoneNumber]) {  // il contatto puo' essere noto con il numero o con il codice nascosto
      const c = chiave && (chats.get(chiave) || chats.get(alias.get(chiave)));
      if (c && !c.nome) { c.nome = nome; break; }
    }
  }
}

export function registraStorico({ chats: cs, contacts, messages }, ora = Date.now() / 1000) {
  let n = 0;
  for (const m of messages || []) if (registra(m, ora, true)) n++;
  impostaNomi(cs); impostaNomi(contacts);
  return n;
}

// ---------- lettura e ricerca ----------
export function gruppoNoto(jid) {
  const c = chats.get(jid);
  return !!c && !!c.gruppo;
}

export function gruppoSenzaNome(jid) {
  const c = chats.get(jid);
  return !!c && c.gruppo && !c.nome;
}

export function nomeGruppo(jid, nome) {
  const c = chats.get(jid);
  if (c && nome) { c.nome = String(nome).slice(0, 40); programmaSalvataggio(); }
}

export function totali() {
  let messaggi = 0;
  for (const c of chats.values()) messaggi += c.msgs.length;
  return { chat: chats.size, messaggi };
}

export function elenco(tutte = false) {
  return [...chats.values()].map((c) => {
    ordina(c);
    const nuovi = c.msgs.filter((x) => !x.da_me && x.ts > c.lettoFino);
    return { id: c.id, numero: c.numero, nome: c.nome, gruppo: !!c.gruppo, ultimo: c.ultimo, messaggi: c.msgs.length, non_lette: nuovi.length,
             anteprima: nuovi.length ? ((nuovi[nuovi.length - 1].chi ? nuovi[nuovi.length - 1].chi + ': ' : '') + String(nuovi[nuovi.length - 1].testo)).slice(0, 160) : '' };  // l'ultimo messaggio non letto, solo per la scheda sullo schermo
  }).filter((c) => tutte || c.non_lette > 0).sort((a, b) => b.ultimo - a.ultimo);
}

export function leggi(id, n = 10, segna = true) {
  const c = chats.get(id);
  if (!c) return null;
  ordina(c);
  const ultimi = c.msgs.slice(-Math.max(1, Math.min(n, 100)));
  if (segna) {  // letto da Jarvis: non lo si conta piu' come nuovo (nessuna spunta blu viene mandata); la lettura 'silenziosa' (promesse) non lo tocca
    c.lettoFino = c.ultimo;
    programmaSalvataggio();
  }
  return { id: c.id, nome: c.nome, numero: c.numero, gruppo: !!c.gruppo, messaggi: ultimi };
}

const pulisci = (t) => String(t).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// cerca per parole (tutte presenti) in tutti i messaggi, o solo in una chat; i piu' recenti per primi
export function cerca({ q = '', chat = '', giorni = 0, n = 15 } = {}, ora = Date.now() / 1000) {
  const parole = pulisci(q).split(/\s+/).filter(Boolean);
  if (!parole.length) return [];
  const da = giorni > 0 ? ora - giorni * 86400 : 0;
  const trovati = [];
  for (const c of chats.values()) {
    if (chat && c.id !== chat) continue;
    for (const m of c.msgs) {
      if (m.ts < da) continue;
      const t = pulisci(m.testo);
      if (parole.every((p) => t.includes(p))) trovati.push({ chat_id: c.id, nome: c.nome, numero: c.numero, gruppo: !!c.gruppo, chi: m.chi || '', da_me: m.da_me, testo: m.testo, ts: m.ts });
    }
  }
  return trovati.sort((a, b) => b.ts - a.ts).slice(0, Math.max(1, Math.min(n, 50)));
}
