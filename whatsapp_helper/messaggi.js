// Messaggi in arrivo: restano SOLO in memoria (RAM), mai su disco ne' nei registri. Solo chat singole.
// Funzioni pure, cosi' si provano senza collegarsi a WhatsApp.
export const chats = new Map();
const MAX_PER_CHAT = 100, MAX_CHAT = 60, ETA_MAX_S = 3 * 24 * 3600;

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

export function registra(m, ora = Date.now() / 1000) {
  const k = m?.key;
  if (!k) return false;
  const jid = k.remoteJidAlt || k.remoteJid || '';
  if (!(jid.endsWith('@s.whatsapp.net') || jid.endsWith('@lid'))) return false;  // niente gruppi, stati, newsletter
  const testo = testoDi(m);
  if (testo == null) return false;
  const ts = Number(m.messageTimestamp?.low ?? m.messageTimestamp ?? ora);
  if (ora - ts > ETA_MAX_S) return false;
  const numero = jid.endsWith('@s.whatsapp.net') ? jid.split('@')[0].split(':')[0] : '';
  let c = chats.get(jid);
  if (!c) {
    if (chats.size >= MAX_CHAT) {  // butta la chat meno recente
      const vecchia = [...chats.values()].sort((a, b) => a.ultimo - b.ultimo)[0];
      chats.delete(vecchia.id);
    }
    c = { id: jid, numero, nome: '', msgs: [], lettoFino: 0, ultimo: 0 };
    chats.set(jid, c);
  }
  if (!k.fromMe && m.pushName) c.nome = String(m.pushName).slice(0, 40);
  c.msgs.push({ da_me: !!k.fromMe, testo: String(testo).slice(0, 1500), ts });
  c.msgs.sort((a, b) => a.ts - b.ts);
  if (c.msgs.length > MAX_PER_CHAT) c.msgs.splice(0, c.msgs.length - MAX_PER_CHAT);
  c.ultimo = Math.max(c.ultimo, ts);
  if (k.fromMe) c.lettoFino = Math.max(c.lettoFino, ts);  // se rispondi dal telefono, la chat conta come letta
  return true;
}

export function elenco() {
  return [...chats.values()].map((c) => ({
    id: c.id, numero: c.numero, nome: c.nome, ultimo: c.ultimo,
    non_lette: c.msgs.filter((x) => !x.da_me && x.ts > c.lettoFino).length,
  })).filter((c) => c.non_lette > 0).sort((a, b) => b.ultimo - a.ultimo);
}

export function leggi(id, n = 10) {
  const c = chats.get(id);
  if (!c) return null;
  const ultimi = c.msgs.slice(-Math.max(1, Math.min(n, 30)));
  c.lettoFino = c.ultimo;  // letto da Jarvis: non lo si conta piu' come nuovo (nessuna spunta blu viene mandata)
  return { id: c.id, nome: c.nome, numero: c.numero, messaggi: ultimi };
}
