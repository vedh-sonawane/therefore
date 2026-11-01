// main.js - the interface.
// A live world of inventions. The organism is the backdrop; the discovery stream on the
// right is where you read what it is finding right now; diving into it lets you inspect
// anything in full. Everything shown is real data from the engine.

const scene = document.getElementById('scene');
const ctx = scene.getContext('2d');
const tip = document.getElementById('tip');
const inspect = document.getElementById('inspect');
const inspectBody = document.getElementById('inspect-body');
const crumbs = document.getElementById('crumbs');
const statusEl = document.getElementById('status');
const feedEl = document.getElementById('feed');
const hintEl = document.getElementById('hint');

const COL = { gold: '#ffce6a', cyan: '#74e6ff', violet: '#b69cff', green: '#78f0b0',
              red: '#ff6f8d', dim: '#5b6480' };
const CA_PAL = ['#070a14', '#3b2f74', '#b36bff', '#ffcf6b'];

let DPR = Math.min(window.devicePixelRatio || 1, 2);
function resize() {
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  scene.width = innerWidth * DPR; scene.height = innerHeight * DPR;
}
addEventListener('resize', resize); resize();

const app = {
  level: 'surface', civId: null, civData: null, snap: null,
  cells: [], hover: null, mouse: { x: -1, y: -1 },
  recentBirths: [], openInvId: null, arcs: [], feed: [], _civCellIndex: {}, _cellIndex: {},
};

// ---------- data ----------
async function getJSON(u) { const r = await fetch(u); return r.json(); }

async function refreshState() {
  try {
    app.snap = await getJSON('/api/state');
    updateStatus(); updateOrganism();
    if (app.level === 'surface') buildSurfaceCells();
  } catch (e) {}
}

function updateStatus() {
  if (!app.snap) return;
  const t = app.snap.totals;
  statusEl.innerHTML =
    `<div class="stat"><span class="lab">tick</span> <b>${app.snap.tick}</b></div>` +
    `<div class="stat"><span class="lab">inventions</span> <b>${t.inventions.toLocaleString()}</b></div>` +
    `<div class="stat gold"><span class="lab">firsts</span> <b>${t.firsts.toLocaleString()}</b></div>` +
    `<div class="stat"><span class="lab">worlds</span> <b>${app.snap.civs.length}</b></div>`;
}

function updateCrumbs() {
  let s = `<b data-nav="surface">the organism</b>`;
  if (app.level === 'civ' && app.civData && app.civData.civ)
    s += ` &rsaquo; <b>${app.civData.civ.glyph} ${app.civData.civ.name}</b>`;
  crumbs.innerHTML = s;
}
crumbs.addEventListener('click', e => {
  if (e.target.dataset && e.target.dataset.nav === 'surface') toSurface();
});

function updateHint() {
  if (app.level === 'surface')
    hintEl.innerHTML = app.snap && app.snap.civs.length > 1
      ? `Each glowing orb is a sealed <b>world</b> inventing on its own. <b>Click one</b> to dive in. Watch the stream on the right for live discoveries.`
      : `This is a live world inventing things. <b>Click the orb</b> to dive in. Watch the stream on the right.`;
  else
    hintEl.innerHTML = `Each cell is an <b>invention</b>. <b>Click one</b> to see it, hear it, and watch its pattern. <b>Esc</b> to go back.`;
}

// ---------- organism ----------
function updateOrganism() {
  if (!app.snap) return;
  const total = app.snap.totals.inventions;
  app.recentBirths = app.recentBirths.filter(t => performance.now() - t < 8000);
  const activity = Math.min(1.1, app.recentBirths.length / 14);
  Organism.set({ mass: Math.min(1, Math.log10(total + 1) / 3), activity });
  Sound.activity(activity);
}

// ---------- navigation ----------
async function enterCiv(id) {
  app.level = 'civ'; app.civId = id;
  Organism.set({ depth: 0.55, hue: 0.5 + (id % 5) * 0.09 });
  app.civData = await getJSON('/api/civ/' + id);
  buildCivCells(app.civData);
  updateCrumbs(); updateHint();
}
function toSurface() {
  app.level = 'surface'; app.civId = null; closeInspect();
  Organism.set({ depth: 0 });
  buildSurfaceCells(); updateCrumbs(); updateHint();
}

// ---------- layout ----------
function layout(n, spread) {
  const pts = [], golden = 2.399963229728653;
  for (let i = 0; i < n; i++) {
    const a = i * golden, r = spread * Math.sqrt(i + 0.6);
    pts.push([Math.cos(a) * r, Math.sin(a) * r]);
  }
  return pts;
}

function buildSurfaceCells() {
  if (!app.snap) return;
  const civs = app.snap.civs;
  const pts = layout(civs.length, Math.min(innerWidth, innerHeight) * 0.14 + 30);
  const cx = innerWidth / 2, cy = innerHeight / 2 + 10;
  app.cells = civs.map((c, i) => {
    const p = civs.length === 1 ? [0, 0] : pts[i];
    const r = 40 + Math.log2(c.total + 2) * 9 + Math.min(34, c.firsts * 1.0);
    return {
      kind: 'civ', id: c.id, x: cx + p[0], y: cy + p[1], r,
      glyph: c.glyph, name: c.name, color: COL.cyan, pulse: 0,
      sub: `${c.alive} alive  ${c.firsts} firsts`,
      phase: (i * 1.7) % 6.28, seq: null,
    };
  });
  app._civCellIndex = {}; app.cells.forEach(c => app._civCellIndex[c.id] = c);
}

function buildCivCells(d) {
  let invs = d.inventions.filter(x => x.total);
  const prio = x => (x.status === 'alive' ? 1000 : 0) + (x.novelty === 'first' ? 400 : 0)
                  + (x.origin === 'immigrant' ? 300 : 0) + (x.wealth || 0) + (x.uses || 0) * 3;
  invs.sort((a, b) => prio(b) - prio(a));
  app.civShown = invs.length; app.civTotal = d.inventions.length;
  const CAP = 90;
  if (invs.length > CAP) invs = invs.slice(0, CAP);
  const pts = layout(invs.length, Math.min(innerWidth, innerHeight) * 0.05 + 22);
  const cx = innerWidth / 2, cy = innerHeight / 2 + 10;
  app.cells = invs.map((iv, i) => {
    const p = pts[i];
    const r = 11 + Math.min(26, Math.log2((iv.wealth || 0) + 2) * 5) + Math.min(9, iv.uses * 1.1);
    let color = COL.violet;
    if (iv.origin === 'immigrant') color = COL.green;
    else if (iv.novelty === 'first') color = COL.gold;
    else if (iv.novelty === 'known') color = COL.cyan;
    return {
      kind: 'inv', id: iv.id, x: cx + p[0], y: cy + p[1], r,
      glyph: iv.symbol, color, dim: iv.status === 'dormant', pulse: 0,
      name: iv.name, origin: iv.origin, wealth: iv.wealth, uses: iv.uses,
      novelty: iv.novelty, seq: iv.prefix, parts: iv.parts, phase: (i * 1.3) % 6.28,
    };
  });
  app._cellIndex = {}; app.cells.forEach(c => app._cellIndex[c.id] = c);
}

// ---------- draw ----------
function hex(c, a) {
  const n = parseInt(c.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

function draw(now) {
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  const t = now / 1000;

  if (app.level === 'surface') drawArcs(now);
  if (app.level === 'civ') drawFilaments(t);

  let hover = null;
  for (const c of app.cells) {
    const breathe = 1 + Math.sin(t * 1.3 + c.phase) * 0.05;
    const rr = c.r * breathe * (1 + c.pulse * 0.5);
    c.pulse *= 0.92;
    const dx = app.mouse.x - c.x, dy = app.mouse.y - c.y;
    const isHover = dx * dx + dy * dy < rr * rr * 1.5;
    if (isHover) hover = c;
    const alpha = c.dim ? 0.32 : 1;

    const g = ctx.createRadialGradient(c.x, c.y, 1, c.x, c.y, rr * 2.3);
    g.addColorStop(0, hex(c.color, 0.9 * alpha));
    g.addColorStop(0.35, hex(c.color, 0.28 * alpha));
    g.addColorStop(1, hex(c.color, 0));
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(c.x, c.y, rr * 2.3, 0, 6.2832); ctx.fill();

    ctx.beginPath(); ctx.arc(c.x, c.y, rr, 0, 6.2832);
    ctx.fillStyle = hex('#070a14', 0.55 * alpha); ctx.fill();
    ctx.lineWidth = isHover ? 2.5 : 1.4;
    ctx.strokeStyle = hex(c.color, (isHover ? 1 : 0.75) * alpha); ctx.stroke();

    if (c.kind === 'inv' && c.seq && rr > 15) {
      drawSpark(c.x, c.y, rr * 1.35, c.seq, hex(c.color, 0.95 * alpha));
    } else {
      const fs = Math.max(12, Math.min(rr * 0.85, c.kind === 'civ' ? 30 : 20));
      ctx.font = `${fs}px ui-monospace, Consolas, monospace`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = hex('#ffffff', (isHover ? 1 : 0.85) * alpha);
      ctx.fillText(c.glyph || '∴', c.x, c.y);
    }

    if (c.kind === 'civ') {
      ctx.font = '600 14px ui-monospace, Consolas, monospace';
      ctx.textAlign = 'center'; ctx.textBaseline = 'top';
      ctx.fillStyle = hex('#eef1fb', isHover ? 1 : 0.8);
      ctx.fillText(c.name, c.x, c.y + rr + 10);
      ctx.font = '11px ui-monospace, Consolas, monospace';
      ctx.fillStyle = hex('#8a93b2', 0.8);
      ctx.fillText(c.sub, c.x, c.y + rr + 28);
    }
  }
  app.hover = hover;
  updateTip(hover);
  requestAnimationFrame(draw);
}

function drawSpark(cx, cy, w, seq, color) {
  const n = Math.min(seq.length, 14); if (n < 2) return;
  const vals = seq.slice(0, n), mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const h = w * 0.5;
  ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const x = cx - w / 2 + (i / (n - 1)) * w;
    const y = cy + h / 2 - ((vals[i] - mn) / rng) * h;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.stroke();
}

function drawFilaments(t) {
  for (const c of app.cells) {
    if (!c.parts) continue;
    for (const pid of c.parts) {
      const p = app._cellIndex[pid]; if (!p) continue;
      const grad = ctx.createLinearGradient(c.x, c.y, p.x, p.y);
      grad.addColorStop(0, 'rgba(182,156,255,0.20)');
      grad.addColorStop(1, 'rgba(116,230,255,0.04)');
      ctx.strokeStyle = grad; ctx.lineWidth = 1; ctx.beginPath();
      const mx = (c.x + p.x) / 2 + Math.sin(t + c.phase) * 7;
      const my = (c.y + p.y) / 2 + Math.cos(t + c.phase) * 7;
      ctx.moveTo(c.x, c.y); ctx.quadraticCurveTo(mx, my, p.x, p.y); ctx.stroke();
    }
  }
}

function drawArcs(now) {
  app.arcs = app.arcs.filter(a => now - a.born < 3200);
  for (const arc of app.arcs) {
    const A = app._civCellIndex[arc.a], B = app._civCellIndex[arc.b];
    if (!A || !B) continue;
    const age = (now - arc.born) / 3200;
    const alpha = Math.sin(Math.min(1, age) * Math.PI) * 0.85;
    const col = arc.convergent ? '255,206,106' : '120,240,176';
    ctx.strokeStyle = `rgba(${col},${alpha})`; ctx.lineWidth = arc.convergent ? 2.5 : 1.6;
    const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2 - 80;
    ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.quadraticCurveTo(mx, my, B.x, B.y); ctx.stroke();
    const tt = (age * 1.4) % 1;
    const px = (1 - tt) ** 2 * A.x + 2 * (1 - tt) * tt * mx + tt * tt * B.x;
    const py = (1 - tt) ** 2 * A.y + 2 * (1 - tt) * tt * my + tt * tt * B.y;
    ctx.fillStyle = `rgba(${col},${alpha})`;
    ctx.beginPath(); ctx.arc(px, py, 4, 0, 6.2832); ctx.fill();
  }
}

function updateTip(h) {
  if (!h) { tip.style.display = 'none'; scene.style.cursor = 'default'; return; }
  scene.style.cursor = 'pointer';
  tip.style.display = 'block';
  tip.style.left = h.x + 'px'; tip.style.top = (h.y - h.r) + 'px';
  if (h.kind === 'civ') {
    tip.innerHTML = `<b>${h.name}</b> &middot; dive in`;
  } else {
    let s = `<b>${h.glyph}</b> ${h.name}`;
    if (h.novelty === 'first') s += ' &middot; <span style="color:#ffce6a">first</span>';
    if (h.origin === 'immigrant') s += ' &middot; <span style="color:#78f0b0">immigrant</span>';
    if (h.seq && h.seq.length) s += `<br><span style="color:#74e6ff">${h.seq.slice(0, 8).join(', ')}</span>`;
    tip.innerHTML = s;
  }
}
requestAnimationFrame(draw);

// ---------- interaction ----------
scene.addEventListener('mousemove', e => { app.mouse.x = e.clientX; app.mouse.y = e.clientY; });
scene.addEventListener('mouseleave', () => { app.mouse.x = -1; app.mouse.y = -1; });
scene.addEventListener('click', () => {
  const h = app.hover; if (!h) return;
  if (h.kind === 'civ') enterCiv(h.id); else openInspect(h.id);
});
addEventListener('keydown', e => {
  if (e.key === 'Escape') { if (app.openInvId) closeInspect(); else if (app.level === 'civ') toSurface(); }
});

// ---------- inspection ----------
async function openInspect(id) {
  const d = await getJSON('/api/invention/' + id);
  if (!d || d.error) return;
  app.openInvId = id; inspect.classList.add('open');
  const nv = d.novelty;
  let novHtml = '';
  if (nv) {
    if (nv.status === 'first')
      novHtml = `<div class="sec">novelty</div><span class="prop" style="color:#ffce6a;border-color:rgba(255,206,106,.5)">not found in OEIS</span>`
        + (nv.receipt.query ? ` <div class="kv"><a href="${nv.receipt.query}" target="_blank">open the OEIS query that found nothing</a></div>` : '');
    else if (nv.status === 'known' && nv.matches.length)
      novHtml = `<div class="sec">recognised</div>` + nv.matches.map(m =>
        `<div class="kv"><a href="https://oeis.org/${m.id}" target="_blank">${m.id}</a> ${m.name}</div>`).join('');
  }
  const lineage = (arr, lbl) => arr && arr.length
    ? `<div class="sec">${lbl}</div>` + arr.map(p =>
        `<span class="chip" data-inv="${p.id}">${p.symbol || '?'}${p.prefix ? ' &middot; ' + p.prefix.slice(0, 5).join(',') : ''}</span>`).join('') : '';
  const exp = d.experiments[0];
  const ex = d.exaptation;
  inspectBody.innerHTML = `
    <h1>${d.symbol}</h1>
    <div class="sub">${d.name} &middot; ${d.origin} &middot; ${d.total ? 'total' : 'partial'} &middot; tick ${d.created_tick}</div>
    <div class="what">${describe(d)}</div>
    <div class="seq">${d.prefix.slice(0, 16).join(',  ')}${d.prefix.length > 16 ? '  ...' : ''}</div>
    <div class="sec">seen: its function run as a cellular automaton</div>
    <div class="carow">
      <canvas id="ca-canvas" class="cacanvas" width="330" height="330" style="max-width:190px"></canvas>
      <div class="cameta">
        <div class="classbadge" id="ca-badge">${ex ? 'class ' + ex.class : ''}</div>
        <div class="kv" id="ca-label"></div>
      </div>
    </div>
    <div class="sec">heard: its sequence as a melody</div>
    <canvas id="seq-plot" class="plot" width="330" height="60"></canvas>
    <div class="btn" id="play-seq">play this sequence</div>
    ${novHtml}
    <div class="sec">measured properties</div>
    ${d.properties.filter(p => p.name !== 'exaptation').map(p => `<span class="prop">${p.name}${fmtDetail(p.detail)}</span>`).join('') || '<span style="color:#5b6480">none detected</span>'}
    <div class="sec">evidence (a real run)</div>
    ${exp ? `<div class="kv"><span class="k">ran n=${exp.input.n ? exp.input.n.join(' to ') : '?'}:</span> ${exp.ok ? 'completed' : 'stopped, ' + exp.error}</div>
             <div class="kv"><span class="k">compute used:</span> ${exp.ops} ops</div>` : ''}
    <div class="sec">economy</div>
    <div class="kv"><span class="k">wealth</span> ${d.wealth} &nbsp;&nbsp; <span class="k">reused</span> ${d.uses}x &nbsp;&nbsp; <span class="k">status</span> ${d.status} &nbsp;&nbsp; <span class="k">taste</span> ${d.score}</div>
    ${lineage(d.parents, 'descended from')}
    ${lineage(d.parts, 'built from its parts')}
    <div class="sec">genome</div>
    <div class="genome">${prettyGenome(d.genome)}</div>`;
  inspectBody.querySelectorAll('[data-inv]').forEach(el =>
    el.addEventListener('click', () => openInspect(+el.dataset.inv)));
  renderBehavior(d);
}
function closeInspect() { app.openInvId = null; inspect.classList.remove('open'); }
document.getElementById('close').addEventListener('click', closeInspect);

function renderBehavior(d) {
  const cc = document.getElementById('ca-canvas'), ex = d.exaptation;
  if (cc && ex && ex.rows) {
    drawCA(cc, ex.rows);
    const lbl = document.getElementById('ca-label');
    if (lbl) lbl.innerHTML = `This number sequence, with its function used as a cellular-automaton rule, produces a <b style="color:#b69cff">${ex.label}</b> pattern. ${ex.class === 'IV' || ex.class === 'III' ? 'A structure it was never built to make.' : ''}`;
    const b = document.getElementById('ca-badge'); if (b) b.textContent = `estimated class ${ex.class}`;
  }
  const pc = document.getElementById('seq-plot'); if (pc) plotSeq(pc, d.prefix);
  const pb = document.getElementById('play-seq');
  if (pb) pb.addEventListener('click', () => { Sound.play(d.prefix); pb.textContent = 'playing...'; setTimeout(() => pb.textContent = 'play this sequence', 1300); });
}
function drawCA(cv, rows) {
  const g = cv.getContext('2d'), H = rows.length, W = rows[0].length;
  const cw = cv.width / W, ch = cv.height / H;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    g.fillStyle = CA_PAL[((rows[y][x] % 4) + 4) % 4];
    g.fillRect(x * cw, y * ch, Math.ceil(cw), Math.ceil(ch));
  }
}
function plotSeq(c, seq) {
  const g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height);
  const n = Math.min(seq.length, 40); if (n < 2) return;
  const v = seq.slice(0, n), mn = Math.min(...v), mx = Math.max(...v), rng = (mx - mn) || 1;
  const X = i => i / (n - 1) * (c.width - 6) + 3, Y = x => c.height - ((x - mn) / rng) * (c.height - 10) - 5;
  g.strokeStyle = '#74e6ff'; g.lineWidth = 1.5; g.beginPath();
  v.forEach((x, i) => { const px = X(i), py = Y(x); i ? g.lineTo(px, py) : g.moveTo(px, py); });
  g.stroke();
  g.fillStyle = '#ffce6a';
  v.forEach((x, i) => { g.beginPath(); g.arc(X(i), Y(x), 1.7, 0, 6.2832); g.fill(); });
}

function describe(d) {
  const props = {}; d.properties.forEach(p => props[p.name] = p.detail);
  if (d.novelty && d.novelty.status === 'known' && d.novelty.matches.length)
    return `This is a known sequence: ${d.novelty.matches[0].name} (OEIS ${d.novelty.matches[0].id}).`;
  let noun = 'integer sequence';
  if (props['prime-valued']) noun = 'sequence of prime numbers';
  else if (props['square-valued']) noun = 'sequence of perfect squares';
  const adj = [];
  if (props['strictly-increasing']) adj.push('strictly increasing');
  else if (props['non-decreasing']) adj.push('non-decreasing');
  const cl = [];
  if (props['geometric']) cl.push(`each term is ${props['geometric'].ratio} times the last`);
  if (props['arithmetic']) cl.push(`each term is ${props['arithmetic'].step} more than the last`);
  if (props['polynomial']) cl.push(`it follows a degree-${props['polynomial'].degree} polynomial`);
  if (props['exponential-growth']) cl.push(`it grows exponentially (about ${props['exponential-growth'].rate}x per step)`);
  if (props['periodic']) cl.push(`it repeats with period ${props['periodic'].period}`);
  const head = adj.length ? adj[0] : noun;
  let s = `${/^[aeiou]/i.test(head) ? 'An' : 'A'}${adj.length ? ' ' + adj.join(', ') : ''} ${noun}`;
  if (cl.length) s += ` where ${cl.join(', and ')}`;
  s += '.';
  if (!cl.length && noun === 'integer sequence')
    s = 'A sequence with no simple closed-form pattern detected.';
  if (d.novelty && d.novelty.status === 'first') s += ' It was not found in the OEIS, so as far as that catalog knows it is new.';
  if (d.origin === 'immigrant') s += ' It was carried in from another world during first contact and re-run here to confirm it behaves the same.';
  return s;
}
function fmtDetail(x) {
  if (!x) return '';
  if (x.degree !== undefined) return ' ' + x.degree;
  if (x.ratio !== undefined) return ' x' + x.ratio;
  if (x.step !== undefined) return ' +' + x.step;
  if (x.period !== undefined) return ' p' + x.period;
  if (x.rate !== undefined) return ' ~' + x.rate;
  return '';
}
function prettyGenome(node) {
  if (!Array.isArray(node)) return String(node);
  const tag = node[0];
  if (tag === 'const') return String(node[2]);
  if (tag === 'param') return 'n';
  if (tag === 'self') return 'f(' + node.slice(1).map(prettyGenome).join(', ') + ')';
  if (tag === 'call') return '[' + node[1] + '](' + node.slice(2).map(prettyGenome).join(', ') + ')';
  if (tag === 'prim') {
    const name = node[1], a = node.slice(2).map(prettyGenome);
    if (name === 'if') return `if ${a[0]} then ${a[1]} else ${a[2]}`;
    const inf = { add: '+', sub: '-', mul: '*', idiv: '/', mod: 'mod', pow: '^', lt: '<', le: '<=', gt: '>', ge: '>=', eq: '=', and: 'and', or: 'or' };
    if (inf[name] && a.length === 2) return `(${a[0]} ${inf[name]} ${a[1]})`;
    return `${name}(${a.join(', ')})`;
  }
  return JSON.stringify(node);
}

// ---------- discovery stream ----------
const FEED_MAX = 10;
const TAGLABEL = { first: 'first', convergent: 'convergent', exaptation: 'exapted',
                   known: 'recognised', first_contact: 'contact', genesis: 'world' };
function pushFeed(type, item) {
  app.feed.unshift({ type, ...item });
  if (app.feed.length > FEED_MAX) app.feed.pop();
  renderFeed();
}
function renderFeed() {
  feedEl.innerHTML = '';
  for (const f of app.feed) {
    const card = document.createElement('div');
    card.className = 'card';
    const cls = f.type === 'first_contact' ? 'contact' : f.type;
    card.innerHTML =
      `<div class="bar b-${cls}"></div><div class="body">` +
      `<span class="tag t-${cls}">${TAGLABEL[f.type] || f.type}</span>` +
      `<span class="tick">t${f.tick}</span>` +
      `<div class="main">${f.main}</div><div class="cap">${f.cap}</div></div>` +
      (f.thumb ? `<canvas width="81" height="81" class="thumb"></canvas>` : '');
    if (f.inv) card.addEventListener('click', () => openInspect(f.inv));
    feedEl.appendChild(card);
    if (f.thumb) drawCA(card.querySelector('canvas'), f.thumb);
  }
}

// ---------- live events ----------
function connectStream() {
  const es = new EventSource('/api/stream');
  es.onmessage = ev => { let e; try { e = JSON.parse(ev.data); } catch { return; } handleEvent(e); };
}
// map an event to a discovery card (or null if it does not belong in the stream)
function feedData(e) {
  const p = e.payload || {};
  if (e.type === 'first') return { type: 'first', tick: e.tick, inv: e.inv_id,
    main: (p.seq || []).slice(0, 8).join(', '), cap: 'not found in OEIS' };
  if (e.type === 'convergent') return { type: 'convergent', tick: e.tick, inv: e.inv_id,
    main: (p.seq || []).slice(0, 7).join(', '), cap: 'invented in two worlds independently' };
  if (e.type === 'exaptation') return { type: 'exaptation', tick: e.tick, inv: e.inv_id,
    main: `${p.label} pattern`, cap: `${(p.seq || []).slice(0, 5).join(', ')} becomes structure`, wantThumb: true };
  if (e.type === 'known') { const m = (p.matches || [{}])[0]; return { type: 'known', tick: e.tick, inv: e.inv_id,
    main: `${m.id || ''} ${(m.name || '').slice(0, 30)}`, cap: 'recognised in the OEIS' }; }
  if (e.type === 'first_contact') return { type: 'first_contact', tick: e.tick,
    main: `${p.from_glyph} met ${p.to_glyph}`, cap: `carried ${p.new} invention(s) across` };
  if (e.type === 'genesis') return { type: 'genesis', tick: e.tick,
    main: `${p.glyph || ''} ${p.name}`, cap: 'a new world begins' };
  return null;
}

async function pushEvent(e) {
  const d = feedData(e); if (!d) return;
  if (d.wantThumb) {
    try { const inv = await getJSON('/api/invention/' + d.inv); d.thumb = inv.exaptation && inv.exaptation.rows; } catch (x) {}
  }
  const { type, ...item } = d; pushFeed(type, item);
}

async function handleEvent(e) {
  const p = e.payload || {};
  if (e.type === 'birth') {
    app.recentBirths.push(performance.now());
    Organism.flash(0.2); Sound.birth(p.prefix || [], p.score || 0); pulseCell(e.inv_id);
    if (app.level === 'civ' && app.civId === e.civ_id) scheduleCivRefresh();
    return;
  }
  if (e.type === 'first') { Organism.flash(1.3); Sound.first(p.seq || []); }
  else if (e.type === 'convergent') { Organism.flash(1.0); Sound.convergent();
    app.arcs.push({ a: p.a_civ, b: p.b_civ, born: performance.now(), convergent: true }); }
  else if (e.type === 'exaptation') { Organism.flash(0.9); Sound.discovery([]); pulseCell(e.inv_id); }
  else if (e.type === 'first_contact') { Organism.flash(0.8); Sound.contact();
    app.arcs.push({ a: p.from_civ, b: p.to_civ, born: performance.now(), convergent: (p.convergent || 0) > 0 }); }
  await pushEvent(e);
}

// fill the stream with recent discoveries so it is populated the moment you arrive
async function seedFeed() {
  if (!app.snap) return;
  const after = Math.max(0, (app.snap.last_event || 0) - 1200);
  try {
    const { events } = await getJSON('/api/events?after=' + after);
    const notable = events.filter(e => feedData(e));
    for (const e of notable.slice(-FEED_MAX)) await pushEvent(e);
  } catch (x) {}
}

let civRefreshT = null;
function scheduleCivRefresh() {
  if (civRefreshT) return;
  civRefreshT = setTimeout(async () => {
    civRefreshT = null;
    if (app.level === 'civ' && app.civId != null) {
      app.civData = await getJSON('/api/civ/' + app.civId); buildCivCells(app.civData);
    }
  }, 1800);
}
function pulseCell(id) { const c = app._cellIndex[id]; if (c) c.pulse = 1; }

// ---------- controls ----------
const soundBtn = document.getElementById('sound');
soundBtn.addEventListener('click', () => {
  const on = Sound.toggle();
  soundBtn.textContent = on ? 'sound on' : 'sound off';
  soundBtn.classList.toggle('on', on);
});
const streamBtn = document.getElementById('togglestream');
streamBtn.addEventListener('click', () => {
  const s = document.getElementById('stream');
  const hidden = s.classList.toggle('hidden');
  streamBtn.textContent = hidden ? 'show stream' : 'hide stream';
});

// ---------- boot ----------
const params = new URLSearchParams(location.search);
const SHOT = params.has('shot') || params.has('civ') || params.has('inspect');
(async () => {
  await refreshState(); updateCrumbs(); updateHint();
  await seedFeed();
  if (params.has('civ')) await enterCiv(+params.get('civ'));
  if (params.has('inspect')) { if (params.get('civ')) await enterCiv(+params.get('civ')); await openInspect(+params.get('inspect')); }
  if (!SHOT) { setInterval(refreshState, 1800); connectStream(); }
})();
