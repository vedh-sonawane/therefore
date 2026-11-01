// main.js - the terminal.
// A readable ledger of what the engine actually did, a vault of firsts, and the worlds.
// Everything shown is real data read from the running engine. No audio, no animation
// beyond a cursor blink. Click any line to see the full invention, including the
// black-and-white pattern its function makes when run as a cellular automaton.

const $ = s => document.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const getJSON = async u => (await fetch(u)).json();

const CA_GRAY = ['#000000', '#565a60', '#a9adb4', '#ffffff'];
const LEDGER_MAX = 160;

const state = { view: 'ledger', snap: null, seenInv: new Set(), rows: 0, openRow: null };

// ---------- header / stats ----------
async function refreshState() {
  try { state.snap = await getJSON('/api/state'); } catch (e) { return; }
  const t = state.snap.totals;
  $('#stats').innerHTML = [
    ['tick', state.snap.tick],
    ['inventions', t.inventions],
    ['firsts', t.firsts],
    ['experiments run', t.experiments],
    ['worlds', state.snap.civs.length],
  ].map(([l, n]) => `<div class="stat"><div class="n">${Number(n).toLocaleString()}</div><div class="l">${l}</div></div>`).join('');
  $('#foot-right').innerHTML = `<b>${t.inventions.toLocaleString()}</b> inventions, all run and verified. nothing here is fabricated.`;
}

// ---------- tabs ----------
document.querySelectorAll('nav .tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('nav .tab').forEach(t => t.classList.toggle('on', t === tab));
  const v = tab.dataset.view;
  document.querySelectorAll('.view').forEach(x => x.classList.toggle('on', x.id === 'view-' + v));
  state.view = v;
  if (v === 'firsts') loadFirsts();
  if (v === 'worlds') loadWorlds();
}));
$('#whatlink').addEventListener('click', () => $('#explain').classList.toggle('open'));

// ---------- ledger ----------
const EVENTS = {
  first:         { tag: 'FIRST',    cls: 'first' },
  exaptation:    { tag: 'EXAPT',    cls: 'exapt' },
  convergent:    { tag: 'CONVERGE', cls: 'converge' },
  first_contact: { tag: 'CONTACT',  cls: 'contact' },
  era:           { tag: 'ERA',      cls: 'era' },
  extinction:    { tag: 'EXTINCT',  cls: 'extinct' },
  resurrection:  { tag: 'REVIVE',   cls: 'revive' },
  taste:         { tag: 'TASTE',    cls: 'taste' },
  genesis:       { tag: 'WORLD',    cls: 'world' },
  birth:         { tag: 'INVENT',   cls: 'invent' },
};

// plain-language names for the things a world can come to value
const VIRTUE = {
  structure: 'structured sequences', rarity: 'rare kinds like primes and squares',
  growth: 'fast-growing sequences', novelty: 'never-before-seen sequences',
  richness: 'varied sequences', parsimony: 'short, simple definitions',
  recurrence: 'self-referential recurrences', totality: 'sequences that always compute',
};

function lineFor(e) {
  const p = e.payload || {};
  switch (e.type) {
    case 'birth':
      if (p.novelty === 'first') return null; // the dedicated FIRST line covers it
      return { inv: e.inv_id, seq: (p.prefix || []).join(' '),
        note: `${p.origin}${p.novelty === 'known' ? ' - matches a known sequence' : p.novelty === 'pending' ? ' - checking novelty' : ''}` };
    case 'first':
      return { inv: e.inv_id, seq: (p.seq || []).join(' '), note: 'not found in OEIS' };
    case 'exaptation':
      return { inv: e.inv_id, text: `#${e.inv_id} becomes a ${p.label} pattern`, note: `class ${p.class}` };
    case 'convergent':
      return { inv: e.inv_id, seq: (p.seq || []).join(' '), note: 'invented in two worlds independently' };
    case 'first_contact':
      return { text: `${p.from_glyph} met ${p.to_glyph}`, note: `carried ${p.new} invention(s) across` };
    case 'era':
      return { text: `${p.glyph} enters era ${p.era}`,
        note: `${(p.changed || []).join(', ')}${p.energy !== undefined ? ` - compute x${p.energy}` : ''}` };
    case 'extinction':
      return { text: `mass extinction in ${p.glyph}: ${p.count} inventions fell dormant`, note: 'the survivors repopulate' };
    case 'resurrection':
      return { text: `${p.count} dormant inventions revived in ${p.glyph}`, note: 'old failures that work under the new laws' };
    case 'taste':
      return p.kind === 'revolution'
        ? { text: `${p.glyph} undergoes a taste revolution`, note: `now prizes ${VIRTUE[p.to] || p.to}` }
        : { text: `${p.glyph} changes what it values`, note: `from ${VIRTUE[p.from] || p.from} to ${VIRTUE[p.to] || p.to}` };
    case 'genesis':
      return { text: `${p.glyph || ''} ${p.name} begins`, note: 'a new world' };
    default: return null;
  }
}

function makeRow(e) {
  const meta = EVENTS[e.type]; if (!meta) return null;
  const d = lineFor(e); if (!d) return null;
  const row = el('div', 'row');
  const content = d.text
    ? `<span class="seq">${d.text}</span>${d.note ? `<span class="note">${d.note}</span>` : ''}`
    : `<span class="seq">${d.seq}</span>${d.note ? `<span class="note">${d.note}</span>` : ''}`;
  row.innerHTML = `<span class="tk">${e.tick}</span>` +
    `<span class="ty ${meta.cls === 'first' ? 'first' : meta.cls}">${meta.tag}</span>` +
    `<span class="ct">${content}</span>`;
  if (d.inv) {
    row.addEventListener('click', () => toggleDetail(row, d.inv));
  } else { row.style.cursor = 'default'; }
  return row;
}

function pushRow(e, atTop) {
  const row = makeRow(e); if (!row) return;
  const L = $('#ledger');
  if (atTop) L.insertBefore(row, L.firstChild); else L.appendChild(row);
  state.rows++;
  while (state.rows > LEDGER_MAX && L.lastChild) {
    if (L.lastChild.classList.contains('detail')) { L.removeChild(L.lastChild); continue; }
    L.removeChild(L.lastChild); state.rows--;
  }
}

async function seedLedger() {
  if (!state.snap) return;
  // the events endpoint returns events oldest-first, capped, so ask for a window that
  // ends at the newest event to get genuinely recent activity (not an old slice).
  const after = Math.max(0, (state.snap.last_event || 0) - 290);
  try {
    const { events } = await getJSON('/api/events?after=' + after);
    const good = events.filter(e => makeRowAllowed(e));
    for (const e of good.slice(-90)) pushRow(e, true);
  } catch (x) {}
}
function makeRowAllowed(e) { return EVENTS[e.type] && lineFor(e); }

function connectStream() {
  const es = new EventSource('/api/stream');
  es.onmessage = ev => { let e; try { e = JSON.parse(ev.data); } catch { return; } if (makeRowAllowed(e)) pushRow(e, true); };
}

// ---------- inline detail ----------
async function toggleDetail(row, invId) {
  // close if already open under this row
  if (row.nextSibling && row.nextSibling.classList && row.nextSibling.classList.contains('detail')) {
    row.nextSibling.remove(); row.classList.remove('sel'); return;
  }
  // close any other open detail
  document.querySelectorAll('.detail').forEach(d => d.remove());
  document.querySelectorAll('.row.sel').forEach(r => r.classList.remove('sel'));
  row.classList.add('sel');
  const host = el('div', 'detail', '<div class="kv">reading the record...</div>');
  row.after(host);
  await renderDetail(invId, host);
}

async function renderDetail(invId, host) {
  let d; try { d = await getJSON('/api/invention/' + invId); } catch (x) { host.innerHTML = '<div class="kv">could not load</div>'; return; }
  if (!d || d.error) { host.innerHTML = '<div class="kv">not found</div>'; return; }
  const ex = d.exaptation, nv = d.novelty, exp = d.experiments[0];
  const props = d.properties.filter(p => p.name !== 'exaptation');

  let novHtml = '';
  if (nv && nv.status === 'first')
    novHtml = `<div class="kv"><b>not found in the OEIS.</b> as far as that public catalog knows, this sequence is new.` +
      (nv.receipt.query ? ` <a href="${nv.receipt.query}" target="_blank">see the query</a>` : '') + `</div>`;
  else if (nv && nv.status === 'known' && nv.matches.length)
    novHtml = `<div class="kv">recognised as <b>${nv.matches[0].id}</b> ${nv.matches[0].name} <a href="https://oeis.org/${nv.matches[0].id}" target="_blank">(OEIS)</a></div>`;
  else novHtml = `<div class="kv">novelty: ${nv ? nv.status : 'n/a'}</div>`;

  const lineage = (arr, lab) => arr && arr.length
    ? `<div class="fieldlab">${lab}</div>` + arr.map(p => `<span class="chip" data-inv="${p.id}">${p.symbol || '?'}${p.prefix ? '  ' + p.prefix.slice(0, 5).join(' ') : ''}</span>`).join('') : '';

  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca" width="81" height="81"></canvas>
       <div class="caption">${ex ? `its function, run as a cellular automaton, makes a <b style="color:#e9e9ec">${ex.label}</b> pattern (estimated class ${ex.class}). a structure it was never built to make.` : 'no pattern'}</div>
     </div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">${d.origin} &middot; ${d.total ? 'runs to completion' : 'partial'} &middot; invented at tick ${d.created_tick}</div>
       <p class="lead">${describe(d)}</p>
       ${novHtml}
       <div class="fieldlab">the sequence it produces</div>
       <div class="seqline">${d.prefix.slice(0, 20).join(',  ')}${d.prefix.length > 20 ? '  ...' : ''}</div>
       <canvas class="plot" width="600" height="54"></canvas>
       <div class="fieldlab">measured properties</div>
       ${props.length ? props.map(p => `<span class="prop">${p.name}${fmtDetail(p.detail)}</span>`).join('') : '<span style="color:#56565d">none detected</span>'}
       <div class="fieldlab">proof it ran</div>
       ${exp ? `<div class="kv">ran for inputs n=${exp.input.n ? exp.input.n.join(' to ') : '?'}; ${exp.ok ? 'completed' : 'stopped, ' + exp.error}; used <b>${exp.ops}</b> computation steps</div>` : ''}
       <div class="fieldlab">standing</div>
       <div class="kv">wealth <b>${d.wealth}</b> &nbsp; reused as a part <b>${d.uses}x</b> &nbsp; status <b>${d.status}</b></div>
       ${lineage(d.parents, 'descended from')}
       ${lineage(d.parts, 'built from')}
       <div class="fieldlab">the invention itself (its genome)</div>
       <div class="genome">f(n) = ${prettyGenome(d.genome)}</div>
     </div></div>`;

  if (ex && ex.rows) drawCA(host.querySelector('.ca'), ex.rows);
  plotSeq(host.querySelector('.plot'), d.prefix);
  host.querySelectorAll('[data-inv]').forEach(c => c.addEventListener('click', () => {
    document.querySelectorAll('.detail').forEach(x => x.remove());
    openStandaloneDetail(+c.dataset.inv);
  }));
}

// when inspecting a lineage chip there may be no row to attach to; open at top of ledger
function openStandaloneDetail(invId) {
  const L = $('#ledger');
  const host = el('div', 'detail', '');
  L.insertBefore(host, L.firstChild);
  renderDetail(invId, host);
  host.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function drawCA(cv, rows) {
  const g = cv.getContext('2d'), H = rows.length, W = rows[0].length;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    g.fillStyle = CA_GRAY[((rows[y][x] % 4) + 4) % 4]; g.fillRect(x, y, 1, 1);
  }
}
function plotSeq(c, seq) {
  const g = c.getContext('2d'); g.clearRect(0, 0, c.width, c.height);
  const n = Math.min(seq.length, 40); if (n < 2) return;
  const v = seq.slice(0, n), mn = Math.min(...v), mx = Math.max(...v), rng = (mx - mn) || 1;
  const X = i => 6 + i / (n - 1) * (c.width - 12), Y = x => c.height - 6 - ((x - mn) / rng) * (c.height - 12);
  g.strokeStyle = '#8c8c93'; g.lineWidth = 1; g.beginPath();
  v.forEach((x, i) => { const px = X(i), py = Y(x); i ? g.lineTo(px, py) : g.moveTo(px, py); });
  g.stroke();
  g.fillStyle = '#e9e9ec';
  v.forEach((x, i) => { g.fillRect(X(i) - 1, Y(x) - 1, 2, 2); });
}

// ---------- firsts ----------
async function loadFirsts() {
  const host = $('#firsts'); host.innerHTML = '<div class="empty">reading the vault...</div>';
  let v; try { v = (await getJSON('/api/vault')).vault; } catch (x) { host.innerHTML = '<div class="empty">could not load</div>'; return; }
  if (!v.length) { host.innerHTML = '<div class="empty">no firsts yet</div>'; return; }
  host.innerHTML = '';
  v.forEach(f => {
    const row = el('div', 'row');
    row.innerHTML = `<span class="tk">${f.tick}</span><span class="ty first">FIRST</span>` +
      `<span class="ct"><span class="seq">${(f.seq || []).join(' ')}</span><span class="note">not in OEIS</span></span>`;
    row.addEventListener('click', () => toggleDetail(row, f.inv_id));
    host.appendChild(row);
  });
}

// ---------- worlds ----------
async function loadWorlds() {
  const host = $('#worlds'); if (!state.snap) await refreshState();
  host.innerHTML = '';
  state.snap.civs.forEach(c => {
    const row = el('div', 'row');
    row.innerHTML = `<span class="tk">${c.glyph}</span><span class="ty">${c.name.toUpperCase()}</span>` +
      `<span class="ct"><span class="seq">era ${c.era} &middot; ${c.alive} alive, ${c.dormant} dormant</span>` +
      `<span class="note">${c.firsts} firsts${c.taste_top ? ' &middot; values ' + (VIRTUE[c.taste_top] || c.taste_top) : ''}</span></span>`;
    row.addEventListener('click', () => toggleWorld(row, c.id));
    host.appendChild(row);
  });
}
async function toggleWorld(row, civId) {
  if (row.nextSibling && row.nextSibling.classList && row.nextSibling.classList.contains('detail')) {
    row.nextSibling.remove(); row.classList.remove('sel'); return;
  }
  document.querySelectorAll('#worlds .detail').forEach(d => d.remove());
  document.querySelectorAll('#worlds .row.sel').forEach(r => r.classList.remove('sel'));
  row.classList.add('sel');
  const host = el('div', 'detail', '<div class="kv">reading this world...</div>');
  row.after(host);
  const d = await getJSON('/api/civ/' + civId);
  const top = d.inventions.filter(i => i.total).sort((a, b) => b.wealth - a.wealth).slice(0, 40);
  host.innerHTML = `<div class="fieldlab">most valuable inventions in this world</div>`;
  const list = el('div');
  top.forEach(iv => {
    const r = el('div', 'row');
    r.style.gridTemplateColumns = '112px 1fr';
    r.innerHTML = `<span class="ty ${iv.novelty === 'first' ? 'first' : ''}">${iv.novelty === 'first' ? 'FIRST' : iv.origin.slice(0, 11)}</span>` +
      `<span class="ct"><span class="seq">${(iv.prefix || []).slice(0, 12).join(' ')}</span></span>`;
    r.addEventListener('click', () => toggleDetail(r, iv.id));
    list.appendChild(r);
  });
  host.appendChild(list);
}

// ---------- language helpers ----------
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
  if (props['exponential-growth']) cl.push(`it grows exponentially, about ${props['exponential-growth'].rate}x per step`);
  if (props['periodic']) cl.push(`it repeats with period ${props['periodic'].period}`);
  const head = adj.length ? adj[0] : noun;
  let s = `${/^[aeiou]/i.test(head) ? 'An' : 'A'}${adj.length ? ' ' + adj.join(', ') : ''} ${noun}`;
  if (cl.length) s += ` where ${cl.join(', and ')}`;
  s += '.';
  if (!cl.length && noun === 'integer sequence') s = 'A sequence with no simple closed-form pattern detected.';
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
  if (tag === 'call') return 'g' + node[1] + '(' + node.slice(2).map(prettyGenome).join(', ') + ')';
  if (tag === 'prim') {
    const name = node[1], a = node.slice(2).map(prettyGenome);
    if (name === 'if') return `(${a[1]} if ${a[0]} else ${a[2]})`;
    const inf = { add: '+', sub: '-', mul: '*', idiv: '/', mod: 'mod', pow: '^', lt: '<', le: '<=', gt: '>', ge: '>=', eq: '=', and: 'and', or: 'or' };
    if (inf[name] && a.length === 2) return `(${a[0]} ${inf[name]} ${a[1]})`;
    return `${name}(${a.join(', ')})`;
  }
  return JSON.stringify(node);
}

// ---------- boot ----------
const STATIC = new URLSearchParams(location.search).has('static');
(async () => {
  await refreshState();
  await seedLedger();
  const prm = new URLSearchParams(location.search);
  if (prm.get('tab')) { const t = document.querySelector(`nav .tab[data-view="${prm.get('tab')}"]`); if (t) t.click(); }
  const open = prm.get('open');
  if (open) openStandaloneDetail(+open);
  if (!STATIC) { setInterval(refreshState, 2000); connectStream(); }
})();
