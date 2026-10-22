// Rete neurale che si muove a ritmo della voce di Jarvis. Solo grafica: non cambia nessuna funzione.
// Legge il suono dall'analizzatore audio (window.JarvisAnalyser, collegato alle voci del server); se la voce e' quella del browser
// (non si puo' misurare) o se Jarvis pensa, simula un ritmo credibile. Stati letti dalla sfera (#orb): speaking, thinking, listening.
(function () {
  const wrap = document.getElementById('visore');
  const canvas = document.getElementById('rete');
  if (!wrap || !canvas) return;
  const g = canvas.getContext('2d');
  const orb = document.getElementById('orb');
  const BANDE = 48;
  const nodi = [], bordi = [], impulsi = [];
  let W = 0, H = 0, dpr = 1, ang = 0, tilt = 0.35, livello = 0, ultimo = performance.now();
  const dati = new Uint8Array(128);
  // agenti al lavoro (pezzo 3): ognuno ha una zona fissa intorno alla rete che si accende mentre lavora, con un raggio dal centro e il suo nome
  const AGENTI_ORD = ['agenda', 'posta', 'whatsapp', 'negozi', 'soldi'];
  const ag = {}; let agenti = {}, sondaggio = true;
  async function sondaAgenti() { if (!sondaggio || document.hidden) return;
    try { const r = await fetch('/api/agenti', { credentials: 'same-origin' }); if (r.status === 401 || r.status === 404) { sondaggio = false; return; } if (r.ok) agenti = (await r.json()).agenti || {}; } catch (e) {} }
  setInterval(sondaAgenti, 700);

  // due gusci di nodi (esterno fitto e interno piu' piccolo) su sfere con un po' di disordine: la rete e' fitta e ha profondita'
  function guscio(n, raggio, variazione) {
    for (let i = 0; i < n; i++) {
      const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963;
      const j = raggio * (1 - variazione + Math.random() * variazione * 2);
      nodi.push({ x: Math.cos(th) * r * j, y: y * j, z: Math.sin(th) * r * j, banda: Math.floor(Math.random() * BANDE), v: 0 });
    }
  }
  // piu' punti sui PC potenti, un po' meno su quelli lenti
  const dens = (navigator.hardwareConcurrency || 4) >= 8 ? 1 : 0.7;
  guscio(Math.round(440 * dens), 1.0, 0.1);
  guscio(Math.round(190 * dens), 0.62, 0.15);
  guscio(Math.round(80 * dens), 0.3, 0.2);
  const N = nodi.length;
  // ogni nodo si collega ai 4 piu' vicini (anche tra i gusci)
  const visti = new Set();
  for (let i = 0; i < N; i++) {
    const d = nodi.map((n, k) => [k, (n.x - nodi[i].x) ** 2 + (n.y - nodi[i].y) ** 2 + (n.z - nodi[i].z) ** 2]).filter(a => a[0] !== i).sort((a, b) => a[1] - b[1]).slice(0, 4);
    for (const [k] of d) { const chiave = Math.min(i, k) * N + Math.max(i, k); if (!visti.has(chiave)) { visti.add(chiave); bordi.push([i, k]); } }
  }

  function misura() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = wrap.clientWidth; H = wrap.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr; canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  }
  new ResizeObserver(misura).observe(wrap);
  misura();

  function stato() {
    const c = orb ? orb.className : '';
    return c.includes('speaking') ? 'parla' : c.includes('thinking') ? 'pensa' : c.includes('listening') ? 'ascolta' : 'riposo';
  }

  function leggiSuono(modo, t) {
    const a = window.JarvisAnalyser;
    let reale = 0;
    if (a && modo === 'parla') {
      a.getByteFrequencyData(dati);
      let s = 0; for (let i = 2; i < 70; i++) s += dati[i];
      reale = Math.min(1, (s / 68 / 255) * 2.2);
    }
    let voluto;
    if (modo === 'parla') voluto = reale > 0.02 ? reale : 0.35 + 0.25 * Math.sin(t / 90) + 0.2 * Math.sin(t / 37) + Math.random() * 0.12; // voce del browser: ritmo simulato
    else if (modo === 'pensa') voluto = 0.3 + 0.12 * Math.sin(t / 160);
    else if (modo === 'ascolta') voluto = 0.2 + 0.1 * Math.sin(t / 300);
    else voluto = 0.05 + 0.03 * Math.sin(t / 900);
    livello += (voluto - livello) * 0.25;
    return modo === 'parla' && reale > 0.02;
  }

  function disegna(adesso) {
    requestAnimationFrame(disegna);
    const calmo = document.body.classList.contains('calmo');
    if (document.hidden || wrap.getClientRects().length === 0) return;
    if (calmo && adesso - ultimo < 33) return;  // effetti ridotti: meta' dei fotogrammi
    const dt = Math.min(0.05, (adesso - ultimo) / 1000); ultimo = adesso;
    let attivi = 0;
    for (const nm of new Set([...AGENTI_ORD, ...Object.keys(agenti)])) {
      const a = ag[nm] ||= { i: 0, fase: '' }, f = agenti[nm] || '';
      if (f) a.fase = f;
      a.i += ((f === 'lavora' ? 1 : f === 'fatto' ? 0.6 : f === 'errore' ? 0.4 : 0) - a.i) * Math.min(1, dt * 6);
      if (!f && a.i < 0.02) { a.i = 0; a.fase = ''; }
      if (a.i > 0.02) attivi++;
    }
    let modo = stato();
    if (attivi && modo === 'riposo') modo = 'pensa';  // mentre gli agenti lavorano la rete si muove come quando pensa
    const conSpettro = leggiSuono(modo, adesso);
    if (conSpettro) { for (const n of nodi) n.v += ((dati[n.banda + 2] / 255) * 1.6 - n.v) * 0.35; }
    else for (const n of nodi) n.v += ((livello * (0.5 + 0.5 * Math.sin(adesso / 140 + n.banda))) - n.v) * 0.2;

    const colore = modo === 'ascolta' ? [255, 180, 84] : [255, 42, 61];
    ang += dt * (0.18 + livello * (modo === 'pensa' ? 2.2 : 0.9));
    const cx = W / 2, cy = H / 2 - (document.body.classList.contains('solovoce') ? H * 0.04 : 0), R = Math.min(W * 0.38, H * 0.355) * (window.RETE_SCALA || 1);
    const ca = Math.cos(ang), sa = Math.sin(ang), ct = Math.cos(tilt), st = Math.sin(tilt);
    const p = nodi.map(n => {
      const k = 1 + n.v * 0.38 + livello * 0.12;
      let x = n.x * k, y = n.y * k, z = n.z * k;
      const x1 = x * ca + z * sa, z1 = -x * sa + z * ca;
      const y2 = y * ct - z1 * st, z2 = y * st + z1 * ct;
      const f = 2.6 / (2.6 - z2);
      return { x: cx + x1 * R * f, y: cy + y2 * R * f, z: z2, f, v: n.v };
    });

    const zone = [];
    if (attivi) {
      for (const [nm, a] of Object.entries(ag)) {
        if (a.i <= 0.02) continue;
        const k = AGENTI_ORD.indexOf(nm), idx = k < 0 ? AGENTI_ORD.length + Object.keys(ag).indexOf(nm) : k, th = -Math.PI / 2 + idx * 2 * Math.PI / Math.max(5, AGENTI_ORD.length);
        const ax = cx + Math.cos(th) * R * 0.82, ay = cy + Math.sin(th) * R * 0.74, rz = R * 0.27;
        for (const q of p) { const d = Math.hypot(q.x - ax, q.y - ay) / rz; if (d < 1 && q.z > -0.35) q.v = Math.max(q.v, Math.pow(1 - d, 1.4) * a.i * 0.6); }
        zone.push({ nm, a, th, ax, ay, rz });
      }
    }

    g.clearRect(0, 0, canvas.width, canvas.height);
    g.save(); g.scale(dpr, dpr);
    g.globalCompositeOperation = 'lighter';
    // alone centrale
    const gr = g.createRadialGradient(cx, cy, 0, cx, cy, R * (1.1 + livello * 0.5));
    gr.addColorStop(0, `rgba(${colore},${0.16 + livello * 0.35})`); gr.addColorStop(1, `rgba(${colore},0)`);
    g.fillStyle = gr; g.fillRect(0, 0, W, H);
    // collegamenti, disegnati a gruppi di trasparenza (veloce anche con tanti fili)
    const gruppi = Array.from({ length: 9 }, () => []);
    for (const [a, b] of bordi) {
      const A = p[a], B = p[b], prof = (A.z + B.z) / 2 * 0.5 + 0.5, forza = (A.v + B.v) / 2;
      const alfa = Math.min(0.95, 0.04 + prof * 0.14 + forza * 0.7);
      gruppi[Math.min(8, Math.floor(alfa * 9.5))].push(A.x, A.y, B.x, B.y);
    }
    for (let k = 0; k < 9; k++) {
      const v = gruppi[k]; if (!v.length) continue;
      g.strokeStyle = `rgba(${colore},${(k + 0.5) / 9.5})`; g.lineWidth = 0.4 + k * 0.17;
      g.beginPath(); for (let i = 0; i < v.length; i += 4) { g.moveTo(v[i], v[i + 1]); g.lineTo(v[i + 2], v[i + 3]); } g.stroke();
    }
    // impulsi che corrono lungo i collegamenti (piu' numerosi quando la voce e' forte)
    const nascita = modo === 'parla' ? livello * 0.9 : modo === 'pensa' ? 0.35 : modo === 'ascolta' ? 0.12 : 0.03;
    if (Math.random() < nascita * 1.6 * (calmo ? 0.5 : 1) && impulsi.length < 160) impulsi.push({ e: Math.floor(Math.random() * bordi.length), t: 0, dir: Math.random() < 0.5 });
    for (let i = impulsi.length - 1; i >= 0; i--) {
      const im = impulsi[i]; im.t += dt * (1.4 + livello * 2.5);
      if (im.t >= 1) { impulsi.splice(i, 1); continue; }
      const [a, b] = bordi[im.e], A = p[im.dir ? a : b], B = p[im.dir ? b : a];
      const x = A.x + (B.x - A.x) * im.t, y = A.y + (B.y - A.y) * im.t;
      g.fillStyle = `rgba(255,${modo === 'ascolta' ? 230 : 140},${modo === 'ascolta' ? 160 : 150},0.95)`;
      g.beginPath(); g.arc(x, y, 2 + livello * 2.5, 0, 6.283); g.fill();
    }
    // nodi
    for (const n of p) {
      const prof = n.z * 0.5 + 0.5, r = (0.7 + prof * 1.0 + n.v * 3.6) * n.f;
      g.fillStyle = n.v > 0.55 ? 'rgba(255,235,220,0.95)' : `rgba(${colore},${0.35 + prof * 0.5 + n.v * 0.4})`;
      g.beginPath(); g.arc(n.x, n.y, r, 0, 6.283); g.fill();
      if (!calmo && n.v > 0.5) { g.fillStyle = `rgba(${colore},${n.v * 0.25})`; g.beginPath(); g.arc(n.x, n.y, r * 3.2, 0, 6.283); g.fill(); }
    }
    // agenti: raggio dal centro, cerchio e nome (restano fermi mentre la rete gira)
    for (const z of zone) {
      const { a, th, ax, ay, rz } = z, lavora = a.fase === 'lavora', oro = a.fase === 'fatto', c = oro ? [255, 180, 84] : lavora ? [255, 42, 61] : [255, 120, 60];
      const gr2 = g.createLinearGradient(cx, cy, ax, ay); gr2.addColorStop(0, `rgba(${c},0)`); gr2.addColorStop(1, `rgba(${c},${0.22 * a.i})`);
      g.strokeStyle = gr2; g.lineWidth = 1; g.beginPath(); g.moveTo(cx, cy); g.lineTo(ax, ay); g.stroke();
      g.strokeStyle = `rgba(${c},${0.28 * a.i})`; g.lineWidth = 1; g.beginPath(); g.arc(ax, ay, rz * (0.92 + 0.06 * Math.sin(adesso / 220)), 0, 6.283); g.stroke();
      if (lavora) for (let j = 0; j < 2; j++) { const f = ((adesso / 1400) + j / 2) % 1; g.fillStyle = `rgba(255,200,190,${0.55 * a.i})`; g.beginPath(); g.arc(cx + (ax - cx) * f, cy + (ay - cy) * f, 1.8, 0, 6.283); g.fill(); }
      g.globalCompositeOperation = 'source-over';
      const lato = Math.cos(th) >= -0.3 ? 1 : -1, lx = ax + lato * (rz + 12), ly = ay;  // il nome sta di lato, mai sopra o sotto (non si taglia e non copre i sottotitoli)
      g.textAlign = lato > 0 ? 'left' : 'right'; g.textBaseline = 'middle';
      g.font = '600 10px ui-monospace, Consolas, monospace'; if ('letterSpacing' in g) g.letterSpacing = '2px';
      g.shadowColor = `rgba(${c},.9)`; g.shadowBlur = 5; g.fillStyle = `rgba(255,255,255,${Math.min(0.75, a.i * 1.1)})`; g.fillText(z.nm.toUpperCase(), lx, ly - 7);
      g.font = '9px ui-monospace, Consolas, monospace'; g.fillStyle = `rgba(${c},${Math.min(0.7, a.i * 1.1)})`;
      g.fillText(lavora ? 'AL LAVORO' : oro ? 'FATTO' : 'NON RISPONDE', lx, ly + 7); g.shadowBlur = 0;
      g.globalCompositeOperation = 'lighter';
    }
    g.restore();
  }
  requestAnimationFrame(disegna);
})();
