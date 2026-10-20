// ============================================================================
// COLLEGAMENTO PER JARVIS - SOLA LETTURA
// Da aggiungere in Codice.gs. NON modifica niente nei fogli e non cambia l'app dei negozi.
// Risponde solo se la richiesta contiene la chiave segreta salvata nelle "Proprietà script" (JARVIS_TOKEN).
// Restituisce SOLO numeri aggregati per negozio e categoria (oggi e mese): niente note, niente nomi di addetti o clienti.
// ============================================================================

function jarvisRiepilogo_(e) {
  var p = (e && e.parameter) || {};
  var token = PropertiesService.getScriptProperties().getProperty('JARVIS_TOKEN');
  if (!token || String(p.token || '') !== token) {
    return jarvisJson_({ ok: false, errore: 'non autorizzato' });
  }
  var oggi = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  var data = normalizeDate_(p.data || oggi);
  return jarvisJson_({
    ok: true,
    data: data,
    mono: jarvisRaccogli_(getRunSheet_(RUN_SHEET_DATI), data),
    multi: jarvisRaccogli_(getRunMultibrandSheet_(RUN_MULTIBRAND_SHEET_DATI), data)
  });
}

// Per ogni negozio: valori di oggi e totali del mese fino a oggi (compreso), come getTotaliMese ma fino alla data scelta.
function jarvisRaccogli_(sheet, data) {
  var values = sheet.getDataRange().getValues();
  var mese = data.slice(0, 7);
  var negozi = {};
  for (var i = 1; i < values.length; i++) {
    var d = normalizeDate_(values[i][0]);
    if (d.slice(0, 7) !== mese || d > data) continue;
    var slug = String(values[i][1] || '').trim();
    if (!slug) continue;
    var valori = {};
    try { valori = JSON.parse(values[i][2] || '{}'); } catch (err) { valori = {}; }
    var n = negozi[slug] || (negozi[slug] = { oggi: {}, mese: {}, giorni: 0, haOggi: false });
    n.giorni++;
    if (d === data) n.haOggi = true;
    for (var k in valori) {
      if (!valori.hasOwnProperty(k)) continue;
      var v = effectiveValue_(valori[k]);   // stessa regola dell'app: mattina + pomeriggio
      n.mese[k] = (n.mese[k] || 0) + v;
      if (d === data) n.oggi[k] = (n.oggi[k] || 0) + v;
    }
  }
  return negozi;
}

function jarvisJson_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ----------------------------------------------------------------------------
// FOCUS ADDETTI (Report normale) - SOLA LETTURA
// Per ogni addetto: pezzi del mese per prodotto, sommati su tutti i negozi tranne Local Promoter
// (come il "Focus addetti" dell'app). Chiave "categoria-prodotto" (es. "0-0"). Legge solo il foglio "Dati".
// Uso: ?azione=jarvis_addetti&token=...&mese=AAAA-MM
// ----------------------------------------------------------------------------
function jarvisAddetti_(e) {
  var p = (e && e.parameter) || {};
  var token = PropertiesService.getScriptProperties().getProperty('JARVIS_TOKEN');
  if (!token || String(p.token || '') !== token) {
    return jarvisJson_({ ok: false, errore: 'non autorizzato' });
  }
  var oggi = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  var mese = String(p.mese || oggi.slice(0, 7)).slice(0, 7);
  var esclusi = { 'local-promoter': true };
  var values = getReportSheet_(REPORT_SHEET_DATI).getDataRange().getValues();
  var addetti = {};
  for (var i = 1; i < values.length; i++) {
    if (normalizeDate_(values[i][0]).slice(0, 7) !== mese) continue;
    var slug = String(values[i][1] || '').trim();
    var nome = String(values[i][2] || '').trim();
    if (!nome || esclusi[slug]) continue;           // riga di negozio o negozio escluso
    var valori = {};
    try { valori = JSON.parse(values[i][3] || '{}'); } catch (err) { valori = {}; }
    var a = addetti[nome] || (addetti[nome] = {});
    for (var k in valori) {
      if (valori.hasOwnProperty(k)) a[k] = (a[k] || 0) + (Number(valori[k]) || 0);
    }
  }
  return jarvisJson_({ ok: true, mese: mese, addetti: addetti });
}

// ----------------------------------------------------------------------------
// In doGet esistente, come PRIMA riga dentro la funzione, aggiungere:
//
//   if (e && e.parameter && e.parameter.azione === 'jarvis') return jarvisRiepilogo_(e);
//   if (e && e.parameter && e.parameter.azione === 'jarvis_addetti') return jarvisAddetti_(e);
//
// (la prima c'e' gia': aggiungere solo la seconda). Il resto di doGet resta identico.
// Poi: Distribuisci > Gestisci distribuzioni > Modifica > Nuova versione.
// ----------------------------------------------------------------------------
