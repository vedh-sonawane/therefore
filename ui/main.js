// main.js - navigating by diving INTO the organism.
// Surface = the whole engine with its civilizations. Dive into a civilization and you
// find its inventions. Click an invention and you inspect it in real depth: its genome,
// the sequence it actually produces, its measured properties, its novelty receipt, its
// lineage, its wealth. No pages. Everything lives inside this one thing.

const scene = document.getElementById('scene');
const ctx = scene.getContext('2d');
const tip = document.getElementById('tip');
const inspect = document.getElementById('inspect');
const inspectBody = document.getElementById('inspect-body');
const breadcrumb = document.getElementById('breadcrumb');
const readout = document.getElementById('readout');
const hud = document.getElementById('hud');

const COL = { gold: '#ffcf6b', cyan: '#73e6ff', violet: '#b39cff', red: '#ff6b8b',
              green: '#7dffb0', dim: '#5b6480' };

let DPR = Math.min(window.devicePixelRatio || 1, 2);
function resize() {
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  scene.width = innerWidth * DPR; scene.height = innerHeight * DPR;
}
window.addEventListener('resize', resize); resize();

const app = {
  level: 'surface',     // 'surface' | 'civ'
  civId: null,
  snap: null,
  cells: [],
  hover: null,
  mouse: { x: -1, y: -1 },
  recentBirths: [],
  lastEventId: 0,
  openInvId: null,
  arcs: [],
};

// ---- data ------------------------------------------------------------------
async function getJSON(url) { const r = await fetch(url); return r.json(); }

async function refreshState() {
  try {
    app.snap = await getJSON('/api/state');
    drawOrganismFromState();
    if (app.level === 'surface') buildSurfaceCells();
    updateReadout();
  } catch (e) {}
}

async function enterCiv(id) {
  app.level = 'civ'; app.civId = id;
  Organism.set({ depth: 0.55, hue: 0.5 + (id % 5) * 0.09 });
  const d = await getJSON('/api/civ/' + id);
  app.civData = d;
  buildCivCells(d);
  buildBreadcrumb();
  updateReadout();
}

function toSurface() {
  app.level = 'surface'; app.civId = null; closeInspect();
  Organism.set({ depth: 0 });
  buildSurfaceCells(); buildBreadcrumb(); updateReadout();
}

// ---- layout (phyllotaxis - organic, handles many nodes) --------------------
function layout(n, spread) {
  const pts = []; const golden = 2.399963229728653;
  for (let i = 0; i < n; i++) {
    const a = i * golden, r = spread * Math.sqrt(i + 0.6);
    pts.push([Math.cos(a) * r, Math.sin(a) * r, i]);
  }
  return pts;
}

function buildSurfaceCells() {
  if (!app.snap) return;
  const civs = app.snap.civs;
  const pts = layout(civs.length, Math.min(innerWidth, innerHeight) * 0.11 + 40);
  const cx = innerWidth / 2, cy = innerHeight / 2;
  app.cells = civs.map((c, i) => {
    const p = civs.length === 1 ? [0, 0, 0] : pts[i];
    const r = 34 + Math.log2(c.total + 2) * 10 + Math.min(40, c.firsts * 1.2);
    return {
      kind: 'civ', id: c.id, x: cx + p[0], y: cy + p[1], r,
      symbol: c.glyph, color: COL.cyan, pulse: 0,
      label: `${c.name} · ${c.alive} alive · ${c.firsts} firsts · era ${c.era}`,
      data: c, seq: null, phase: Math.random() * 6.28,
    };
  });
  app._civCellIndex = {}; app.cells.forEach(c => app._civCellIndex[c.id] = c);
}

function buildCivCells(d) {
  // Keep the view legible: a civilization can hold thousands of inventions, so we
  // show the ones that matter (alive, wealthy, and every first) up to a cap.
  let invs = d.inventions.filter(x => x.total);
  const prio = x => (x.status === 'alive' ? 1000 : 0) + (x.novelty === 'first' ? 500 : 0)
                  + (x.wealth || 0) + (x.uses || 0) * 3;
  invs.sort((a, b) => prio(b) - prio(a));
  const CAP = 150;
  app.civShown = invs.length;
  app.civTotal = d.inventions.length;
  if (invs.length > CAP) invs = invs.slice(0, CAP);
  const pts = layout(invs.length, Math.min(innerWidth, innerHeight) * 0.045 + 16);
  const cx = innerWidth / 2, cy = innerHeight / 2;
  const byId = {}; invs.forEach(x => byId[x.id] = x);
  app.cells = invs.map((iv, i) => {
    const p = pts[i];
    const r = 7 + Math.min(26, Math.log2((iv.wealth || 0) + 2) * 5) + Math.min(10, iv.uses * 1.2);
    let color = COL.violet;
    if (iv.origin === 'immigrant') color = COL.green;      // arrived via first contact
    else if (iv.novelty === 'first') color = COL.gold;
    else if (iv.novelty === 'known') color = COL.cyan;
    const dim = iv.status === 'dormant';
    return {
      kind: 'inv', id: iv.id, x: cx + p[0], y: cy + p[1], r,
      symbol: iv.symbol, color, dim, pulse: 0,
      label: `${iv.name} · ${iv.origin} · w=${iv.wealth} · uses=${iv.uses}`,
      data: iv, seq: iv.prefix, parts: iv.parts, phase: Math.random() * 6.28,
    };
  });
  app._cellIndex = {}; app.cells.forEach(c => app._cellIndex[c.id] = c);
}

// ---- drawing ---------------------------------------------------------------
function drawOrganismFromState() {
  if (!app.snap) return;
  const total = app.snap.totals.inventions;
  app.recentBirths = app.recentBirths.filter(t => performance.now() - t < 8000);
  const activity = Math.min(1.1, app.recentBirths.length / 14);
  Organism.set({ mass: Math.min(1, Math.log10(total + 1) / 3), activity });
  Sound.activity(activity);
}

function draw(now) {
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const t = now / 1000;

  // contact arcs: two civilizations touching, at the surface
  if (app.level === 'surface' && app.arcs.length && app._civCellIndex) {
    app.arcs = app.arcs.filter(a => now - a.born < 3200);
    for (const arc of app.arcs) {
      const A = app._civCellIndex[arc.a], B = app._civCellIndex[arc.b];
      if (!A || !B) continue;
      const age = (now - arc.born) / 3200;
      const alpha = Math.sin(Math.min(1, age) * Math.PI) * 0.8;
      const col = arc.convergent ? '255,207,107' : '125,255,176';
      ctx.strokeStyle = `rgba(${col},${alpha})`;
      ctx.lineWidth = arc.convergent ? 2.5 : 1.5;
      ctx.beginPath();
      const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2 - 90;
      ctx.moveTo(A.x, A.y); ctx.quadraticCurveTo(mx, my, B.x, B.y); ctx.stroke();
      // a travelling pulse along the arc
      const tt = (age * 1.4) % 1;
      const px = (1 - tt) * (1 - tt) * A.x + 2 * (1 - tt) * tt * mx + tt * tt * B.x;
      const py = (1 - tt) * (1 - tt) * A.y + 2 * (1 - tt) * tt * my + tt * tt * B.y;
      ctx.fillStyle = `rgba(${col},${alpha})`;
      ctx.beginPath(); ctx.arc(px, py, 4, 0, 6.2832); ctx.fill();
    }
  }

  // filaments: lineage (an invention to its parts) at civ level
  if (app.level === 'civ') {
    ctx.lineWidth = 1;
    for (const c of app.cells) {
      if (!c.parts || !c.parts.length) continue;
      for (const pid of c.parts) {
        const p = app._cellIndex[pid]; if (!p) continue;
        const grad = ctx.createLinearGradient(c.x, c.y, p.x, p.y);
        grad.addColorStop(0, 'rgba(179,156,255,0.22)');
        grad.addColorStop(1, 'rgba(115,230,255,0.05)');
        ctx.strokeStyle = grad;
        ctx.beginPath();
        const mx = (c.x + p.x) / 2 + Math.sin(t + c.phase) * 8;
        const my = (c.y + p.y) / 2 + Math.cos(t + c.phase) * 8;
        ctx.moveTo(c.x, c.y); ctx.quadraticCurveTo(mx, my, p.x, p.y); ctx.stroke();
      }
    }
  }

  let hover = null;
  for (const c of app.cells) {
    const breathe = 1 + Math.sin(t * 1.4 + c.phase) * 0.06;
    const rr = c.r * breathe * (1 + c.pulse * 0.6);
    c.pulse *= 0.93;
    const dx = app.mouse.x - c.x, dy = app.mouse.y - c.y;
    const isHover = dx * dx + dy * dy < rr * rr * 1.6;
    if (isHover) hover = c;

    const alpha = c.dim ? 0.3 : 1;
    const g = ctx.createRadialGradient(c.x, c.y, 1, c.x, c.y, rr * 2.4);
    g.addColorStop(0, hex(c.color, 0.95 * alpha));
    g.addColorStop(0.3, hex(c.color, 0.35 * alpha));
    g.addColorStop(1, hex(c.color, 0));
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(c.x, c.y, rr * 2.4, 0, 6.2832); ctx.fill();

    ctx.beginPath(); ctx.arc(c.x, c.y, rr, 0, 6.2832);
    ctx.fillStyle = hex(c.color, (isHover ? 0.3 : 0.14) * alpha); ctx.fill();
    ctx.lineWidth = isHover ? 2 : 1;
    ctx.strokeStyle = hex(c.color, (isHover ? 1 : 0.7) * alpha); ctx.stroke();

    // the civ/invention's own glyph, in its own script
    const fs = Math.max(11, Math.min(rr * 0.9, 30));
    ctx.font = `${fs}px tf-mono, monospace`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = hex('#ffffff', (isHover ? 1 : 0.85) * alpha);
    ctx.fillText(c.symbol || '∴', c.x, c.y);
  }

  app.hover = hover;
  updateTip(hover);
  requestAnimationFrame(draw);
}
requestAnimationFrame(draw);

function hex(c, a) {
  if (c[0] === '#') {
    const n = parseInt(c.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }
  return c;
}

// ---- tooltip / breadcrumb / readout ----------------------------------------
function updateTip(h) {
  if (!h) { tip.style.display = 'none'; scene.style.cursor = 'crosshair'; return; }
  scene.style.cursor = 'pointer';
  tip.style.display = 'block';
  tip.style.left = h.x + 'px'; tip.style.top = h.y - h.r + 'px';
  let s = `<b>${h.symbol}</b> -> ${h.label}`;
  if (h.seq && h.seq.length) s += `<br><span style="color:#73e6ff">${h.seq.slice(0, 9).join(', ')} ...</span>`;
  tip.innerHTML = s;
}

function buildBreadcrumb() {
  let s = `<span data-nav="surface">∴</span>`;
  if (app.level === 'civ' && app.civData && app.civData.civ)
    s += ` &nbsp;›&nbsp; <span>${app.civData.civ.glyph} ${app.civData.civ.name}</span>`;
  breadcrumb.innerHTML = s;
}
breadcrumb.addEventListener('click', e => {
  if (e.target.dataset && e.target.dataset.nav === 'surface') toSurface();
});

function updateReadout() {
  if (!app.snap) return;
  const tt = app.snap.totals;
  let where = app.level === 'surface' ? 'the organism'
    : (app.civData && app.civData.civ ? app.civData.civ.name : 'a civilization');
  let shown = '';
  if (app.level === 'civ' && app.civShown)
    shown = ` &nbsp;·&nbsp; showing ${Math.min(150, app.civShown)} of ${app.civTotal} inventions`;
  readout.innerHTML =
    `<b>tick ${app.snap.tick}</b> &nbsp;·&nbsp; inside <b>${where}</b>${shown}<br>` +
    `${tt.inventions} inventions &nbsp;·&nbsp; <b style="color:#ffcf6b">${tt.firsts} firsts</b> ` +
    `&nbsp;·&nbsp; ${tt.experiments} experiments` +
    (app.latest ? `<br><span style="color:#8a93b2">latest: ${app.latest}</span>` : '');
}

// short plain words for a discovered property
const PROP_WORDS = {
  'prime-valued': 'prime numbers', 'square-valued': 'perfect squares',
  'exponential-growth': 'exponential growth', 'polynomial': 'a polynomial pattern',
  'geometric': 'geometric growth', 'periodic': 'a repeating cycle',
  'arithmetic': 'a steady step', 'strictly-increasing': 'always rising',
};

// ---- interaction -----------------------------------------------------------
scene.addEventListener('mousemove', e => { app.mouse.x = e.clientX; app.mouse.y = e.clientY; });
scene.addEventListener('mouseleave', () => { app.mouse.x = -1; app.mouse.y = -1; });
scene.addEventListener('click', () => {
  const h = app.hover; if (!h) return;
  if (h.kind === 'civ') enterCiv(h.id);
  else openInspect(h.id);
});
window.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (app.openInvId) closeInspect();
    else if (app.level === 'civ') toSurface();
  }
});

// ---- inspection ------------------------------------------------------------
async function openInspect(id) {
  const d = await getJSON('/api/invention/' + id);
  if (!d || d.error) return;
  app.openInvId = id;
  inspect.classList.add('open');
  const nv = d.novelty;
  let novHtml = '';
  if (nv) {
    if (nv.status === 'first') {
      novHtml = `<div class="prop first">∴ FIRST - not found in ${nv.catalog}</div>
        <div class="kv"><span class="k">receipt:</span> queried ${nv.receipt.result_count} results</div>
        ${nv.receipt.query ? `<div class="kv"><a href="${nv.receipt.query}" target="_blank">open the ${nv.catalog} query</a></div>` : ''}`;
    } else if (nv.status === 'known') {
      novHtml = nv.matches.map(m =>
        `<div class="kv"><span class="k">${nv.catalog}:</span> <a href="https://oeis.org/${m.id}" target="_blank">${m.id}</a> ${m.name}</div>`).join('');
    } else {
      novHtml = `<div class="kv"><span class="k">novelty:</span> ${nv.status}</div>`;
    }
  }
  const lineage = (arr, lbl) => arr && arr.length
    ? `<div class="sec">${lbl}</div>` + arr.map(p =>
        `<span class="chip" data-inv="${p.id}">${p.symbol || '?'} ${p.prefix ? '· ' + p.prefix.slice(0, 5).join(',') : ''}</span>`).join('')
    : '';
  const exp = d.experiments[0];
  inspectBody.innerHTML = `
    <h1>${d.symbol}</h1>
    <div class="sub">${d.name} · ${d.origin} · ${d.total ? 'total' : 'partial'} · tick ${d.created_tick}</div>
    <div class="what">${describe(d)}</div>
    <div class="seq">${d.prefix.slice(0, 18).join(',  ')}${d.prefix.length > 18 ? ' ...' : ''}</div>
    ${novHtml}
    <div class="sec">measured properties</div>
    ${d.properties.length ? d.properties.map(p => `<span class="prop" title="${JSON.stringify(p.detail)}">${p.name}${fmtDetail(p.detail)}</span>`).join('') : '<span style="color:#5b6480">none detected</span>'}
    <div class="sec">evidence (a real run)</div>
    ${exp ? `<div class="kv"><span class="k">ran n=${exp.input.n ? exp.input.n.join('..') : '?'}:</span> ${exp.ok ? 'completed' : 'stopped - ' + exp.error}</div>
             <div class="kv"><span class="k">compute used:</span> ${exp.ops} ops</div>` : ''}
    <div class="sec">economy</div>
    <div class="kv"><span class="k">wealth:</span> ${d.wealth} &nbsp; <span class="k">used as a part:</span> ${d.uses}× &nbsp; <span class="k">status:</span> ${d.status}</div>
    <div class="kv"><span class="k">taste score:</span> ${d.score}</div>
    ${lineage(d.parents, 'descended from')}
    ${lineage(d.parts, 'built from (its parts)')}
    <div class="sec">genome</div>
    <div class="genome">${prettyGenome(d.genome)}</div>
  `;
  inspectBody.querySelectorAll('[data-inv]').forEach(el =>
    el.addEventListener('click', () => openInspect(+el.dataset.inv)));
}
function closeInspect() { app.openInvId = null; inspect.classList.remove('open'); }
document.getElementById('close').addEventListener('click', closeInspect);

// turn measured properties + novelty into a plain-language sentence, so you can
// tell at a glance WHAT was discovered without reading the genome.
function describe(d) {
  const props = {}; d.properties.forEach(p => props[p.name] = p.detail);
  // if the OEIS recognised it, that is the clearest possible description
  if (d.novelty && d.novelty.status === 'known' && d.novelty.matches.length) {
    const m = d.novelty.matches[0];
    return `This is a known sequence: ${m.name} (OEIS ${m.id}).`;
  }
  let noun = 'integer sequence';
  if (props['prime-valued']) noun = 'sequence of prime numbers';
  else if (props['square-valued']) noun = 'sequence of perfect squares';
  const adj = [];
  if (props['strictly-increasing']) adj.push('strictly increasing');
  else if (props['non-decreasing']) adj.push('non-decreasing');
  const clauses = [];
  if (props['geometric']) clauses.push(`each term is ${props['geometric'].ratio} times the last`);
  if (props['arithmetic']) clauses.push(`each term is ${props['arithmetic'].step} more than the last`);
  if (props['polynomial']) clauses.push(`it follows a degree-${props['polynomial'].degree} polynomial`);
  if (props['exponential-growth']) clauses.push(`it grows exponentially (about ${props['exponential-growth'].rate}x per step)`);
  if (props['periodic']) clauses.push(`it repeats with period ${props['periodic'].period}`);
  const head = adj.length ? adj[0] : noun;
  const article = /^[aeiou]/i.test(head) ? 'An' : 'A';
  let s = `${article}${adj.length ? ' ' + adj.join(', ') : ''} ${noun}`;
  if (clauses.length) s += ` where ${clauses.join(', and ')}`;
  s += '.';
  if (d.novelty) {
    if (d.novelty.status === 'first') s += ' It was not found in the OEIS, so as far as that catalog knows it is new.';
    else if (d.novelty.status === 'unchecked') s += ' Its novelty has not been checked yet (the catalog was unreachable).';
    else if (d.novelty.status === 'pending') s += ' Its novelty check is still queued.';
  }
  if (!clauses.length && noun === 'integer sequence')
    s = 'A sequence with no simple closed-form pattern detected' + (d.novelty && d.novelty.status === 'first' ? ', and not found in the OEIS.' : '.');
  if (d.origin === 'immigrant')
    s += ' It was carried in from another civilization during first contact and re-run here to confirm it behaves the same.';
  return s;
}

function fmtDetail(d) {
  if (!d) return '';
  const keys = Object.keys(d);
  if (!keys.length) return '';
  if (d.degree !== undefined) return ` ${d.degree}`;
  if (d.ratio !== undefined) return ` ×${d.ratio}`;
  if (d.step !== undefined) return ` +${d.step}`;
  if (d.period !== undefined) return ` p=${d.period}`;
  if (d.rate !== undefined) return ` ~${d.rate}`;
  return '';
}

function prettyGenome(node, depth) {
  depth = depth || 0;
  if (!Array.isArray(node)) return String(node);
  const tag = node[0];
  if (tag === 'const') return String(node[2]);
  if (tag === 'param') return 'n';
  if (tag === 'self') return 'f(' + node.slice(1).map(a => prettyGenome(a, depth + 1)).join(', ') + ')';
  if (tag === 'call') return '⟨' + node[1] + '⟩(' + node.slice(2).map(a => prettyGenome(a, depth + 1)).join(', ') + ')';
  if (tag === 'prim') {
    const name = node[1];
    const args = node.slice(2).map(a => prettyGenome(a, depth + 1));
    if (name === 'if') return `if ${args[0]} then ${args[1]} else ${args[2]}`;
    const infix = { add: '+', sub: '−', mul: '×', idiv: '÷', mod: 'mod', pow: '^',
      lt: '<', le: '≤', gt: '>', ge: '≥', eq: '=', and: '∧', or: '∨' };
    if (infix[name] && args.length === 2) return `(${args[0]} ${infix[name]} ${args[1]})`;
    return `${name}(${args.join(', ')})`;
  }
  return JSON.stringify(node);
}

// ---- live events (SSE) -----------------------------------------------------
function connectStream() {
  const es = new EventSource('/api/stream');
  es.onmessage = ev => {
    let e; try { e = JSON.parse(ev.data); } catch { return; }
    handleEvent(e);
  };
  es.onerror = () => { /* browser auto-reconnects */ };
}

function handleEvent(e) {
  const p = e.payload || {};
  if (e.type === 'birth') {
    app.recentBirths.push(performance.now());
    Organism.flash(0.25);
    Sound.birth(p.prefix || [], p.score || 0);
    pulseCell(e.inv_id);
    if (app.level === 'civ' && app.civId === e.civ_id) scheduleCivRefresh();
  } else if (e.type === 'first') {
    Organism.flash(1.4);
    Sound.first(p.seq || []);
    app.latest = `a new sequence not in the OEIS, e.g. ${(p.seq || []).slice(0, 6).join(', ')}`;
    flashLine(`FIRST  ${(p.seq || []).slice(0, 8).join(', ')}  not found in OEIS`, COL.gold);
    updateReadout();
  } else if (e.type === 'discovery') {
    Sound.discovery([]);
    pulseCell(e.inv_id);
    const words = (p.properties || []).map(x => PROP_WORDS[x]).filter(Boolean);
    if (words.length) {
      app.latest = `found ${words.join(' and ')}`;
      flashLine(`discovery: ${words.join(', ')}`, COL.violet);
      updateReadout();
    }
  } else if (e.type === 'known') {
    const m = (p.matches || [{}])[0];
    app.latest = `re-invented ${m.id || ''} ${(m.name || '').slice(0, 40)}`;
    flashLine(`${m.id || ''}  ${(m.name || '').slice(0, 40)}`, COL.cyan);
    updateReadout();
  } else if (e.type === 'dormant') {
    Sound.dormant();
    flashLine(`× ${p.symbol || ''} went bankrupt`, COL.dim);
  } else if (e.type === 'genesis') {
    flashLine(`${p.glyph || ''} ${p.name} - a civilization begins`, COL.cyan);
  } else if (e.type === 'first_contact') {
    Organism.flash(0.8);
    Sound.contact();
    app.arcs.push({ a: p.from_civ, b: p.to_civ, born: performance.now(),
                    convergent: (p.convergent || 0) > 0 });
    const cv = p.convergent ? `, and found ${p.convergent} already shared` : '';
    app.latest = `first contact: ${p.from_glyph} reached ${p.to_glyph}${cv}`;
    flashLine(`first contact: ${p.from_glyph} meets ${p.to_glyph} - carried ${p.new} invention(s) across${cv}`, COL.green);
    updateReadout();
  } else if (e.type === 'convergent') {
    Organism.flash(1.0);
    Sound.convergent();
    app.arcs.push({ a: p.a_civ, b: p.b_civ, born: performance.now(), convergent: true });
    app.latest = `convergent invention: two worlds independently reached ${(p.seq || []).slice(0, 6).join(', ')}`;
    flashLine(`convergent: two sealed worlds both invented ${(p.seq || []).slice(0, 7).join(', ')}`, COL.gold);
    updateReadout();
  }
}

let civRefreshT = null;
function scheduleCivRefresh() {
  if (civRefreshT) return;
  civRefreshT = setTimeout(async () => {
    civRefreshT = null;
    if (app.level === 'civ' && app.civId != null) {
      const d = await getJSON('/api/civ/' + app.civId);
      app.civData = d; buildCivCells(d);
    }
  }, 1500);
}

function pulseCell(id) {
  const c = app._cellIndex && app._cellIndex[id];
  if (c) c.pulse = 1;
}

function flashLine(text, color) {
  const el = document.createElement('div');
  el.className = 'flashline';
  el.style.cssText = `position:absolute;left:50%;top:${26 + Math.random() * 20}%;` +
    `transform:translateX(-50%);color:${color};font-size:13px;letter-spacing:.14em;` +
    `text-shadow:0 0 20px ${color};white-space:nowrap`;
  el.textContent = text;
  hud.appendChild(el);
  setTimeout(() => el.remove(), 2300);
}

// ---- sound toggle ----------------------------------------------------------
const soundBtn = document.getElementById('sound');
soundBtn.addEventListener('click', () => {
  const on = Sound.toggle();
  soundBtn.textContent = on ? 'sound: on' : 'sound: off - click to wake';
});

// ---- boot ------------------------------------------------------------------
// screenshot mode (?shot / ?civ=ID / ?inspect=ID) skips the live stream so a
// headless capture can reach network-idle, and can jump straight to a state.
const params = new URLSearchParams(location.search);
const SHOT = params.has('shot') || params.has('civ') || params.has('inspect');
(async () => {
  await refreshState();
  if (params.has('civ')) await enterCiv(+params.get('civ'));
  if (params.has('inspect')) {
    const cid = params.get('civ');
    if (cid) await enterCiv(+cid);
    await openInspect(+params.get('inspect'));
  }
  if (!SHOT) { setInterval(refreshState, 1600); connectStream(); }
})();
