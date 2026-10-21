// Rete neurale che si muove a ritmo della voce di Jarvis. Solo grafica: non cambia nessuna funzione.
// Legge il suono dall'analizzatore audio (window.JarvisAnalyser, collegato alle voci del server); se la voce e' quella del browser
// (non si puo' misurare) o se Jarvis pensa, simula un ritmo credibile. Stati letti dalla sfera (#orb): speaking, thinking, listening.
(function () {
  const wrap = document.getElementById('visore');
  const canvas = document.getElementById('rete');
  if (!wrap || !canvas) return;
  const g = canvas.getContext('2d');
  const orb = document.getElementById('orb');
  const N = 120, BANDE = 48;
  const nodi = [], bordi = [], impulsi = [];
  let W = 0, H = 0, dpr = 1, ang = 0, tilt = 0.35, livello = 0, ultimo = performance.now();
  const dati = new Uint8Array(128);

  // nodi su una sfera (distribuiti in modo uniforme) con un po' di disordine; ognuno ascolta una banda di frequenza
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963;
    const j = 0.88 + Math.random() * 0.24;
    nodi.push({ x: Math.cos(th) * r * j, y: y * j, z: Math.sin(th) * r * j, banda: Math.floor(Math.random() * BANDE), v: 0 });
  }
  // ogni nodo si collega ai 3 piu' vicini
  for (let i = 0; i < N; i++) {
    const d = nodi.map((n, k) => [k, (n.x - nodi[i].x) ** 2 + (n.y - nodi[i].y) ** 2 + (n.z - nodi[i].z) ** 2]).filter(a => a[0] !== i).sort((a, b) => a[1] - b[1]).slice(0, 3);
    for (const [k] of d) if (!bordi.some(b => (b[0] === i && b[1] === k) || (b[0] === k && b[1] === i))) bordi.push([i, k]);
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
    if (document.hidden || wrap.offsetParent === null) return;
    if (calmo && adesso - ultimo < 33) return;  // effetti ridotti: meta' dei fotogrammi
    const dt = Math.min(0.05, (adesso - ultimo) / 1000); ultimo = adesso;
    const modo = stato();
    const conSpettro = leggiSuono(modo, adesso);
    if (conSpettro) { for (const n of nodi) n.v += ((dati[n.banda + 2] / 255) * 1.6 - n.v) * 0.35; }
    else for (const n of nodi) n.v += ((livello * (0.5 + 0.5 * Math.sin(adesso / 140 + n.banda))) - n.v) * 0.2;

    const colore = modo === 'ascolta' ? [255, 180, 84] : [255, 42, 61];
    ang += dt * (0.18 + livello * (modo === 'pensa' ? 2.2 : 0.9));
    const cx = W / 2, cy = H / 2, R = Math.min(W * 0.34, H * 0.42);
    const ca = Math.cos(ang), sa = Math.sin(ang), ct = Math.cos(tilt), st = Math.sin(tilt);
    const p = nodi.map(n => {
      const k = 1 + n.v * 0.38 + livello * 0.12;
      let x = n.x * k, y = n.y * k, z = n.z * k;
      const x1 = x * ca + z * sa, z1 = -x * sa + z * ca;
      const y2 = y * ct - z1 * st, z2 = y * st + z1 * ct;
      const f = 2.6 / (2.6 - z2);
      return { x: cx + x1 * R * f, y: cy + y2 * R * f, z: z2, f, v: n.v };
    });

    g.clearRect(0, 0, canvas.width, canvas.height);
    g.save(); g.scale(dpr, dpr);
    g.globalCompositeOperation = 'lighter';
    // alone centrale
    const gr = g.createRadialGradient(cx, cy, 0, cx, cy, R * (1.1 + livello * 0.5));
    gr.addColorStop(0, `rgba(${colore},${0.16 + livello * 0.35})`); gr.addColorStop(1, `rgba(${colore},0)`);
    g.fillStyle = gr; g.fillRect(0, 0, W, H);
    // collegamenti
    for (const [a, b] of bordi) {
      const A = p[a], B = p[b], prof = (A.z + B.z) / 2 * 0.5 + 0.5, forza = (A.v + B.v) / 2;
      g.strokeStyle = `rgba(${colore},${Math.min(0.9, 0.06 + prof * 0.18 + forza * 0.7)})`;
      g.lineWidth = 0.6 + forza * 1.6;
      g.beginPath(); g.moveTo(A.x, A.y); g.lineTo(B.x, B.y); g.stroke();
    }
    // impulsi che corrono lungo i collegamenti (piu' numerosi quando la voce e' forte)
    const nascita = modo === 'parla' ? livello * 0.9 : modo === 'pensa' ? 0.35 : modo === 'ascolta' ? 0.12 : 0.03;
    if (Math.random() < nascita * (calmo ? 0.5 : 1) && impulsi.length < 60) impulsi.push({ e: Math.floor(Math.random() * bordi.length), t: 0, dir: Math.random() < 0.5 });
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
      const prof = n.z * 0.5 + 0.5, r = (1.2 + prof * 1.6 + n.v * 5) * n.f;
      g.fillStyle = n.v > 0.55 ? 'rgba(255,235,220,0.95)' : `rgba(${colore},${0.35 + prof * 0.5 + n.v * 0.4})`;
      g.beginPath(); g.arc(n.x, n.y, r, 0, 6.283); g.fill();
      if (!calmo && n.v > 0.35) { g.fillStyle = `rgba(${colore},${n.v * 0.25})`; g.beginPath(); g.arc(n.x, n.y, r * 3.2, 0, 6.283); g.fill(); }
    }
    g.restore();
  }
  requestAnimationFrame(disegna);
})();
