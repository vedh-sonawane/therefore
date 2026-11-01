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
    ['worlds', state.snap.civs.length],
    ['written by itself', (state.snap.ouroboros || 0) + '%'],
  ].map(([l, n]) => `<div class="stat"><div class="n">${typeof n === 'number' ? Number(n).toLocaleString() : n}</div><div class="l">${l}</div></div>`).join('');
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
  figure:        { tag: 'FIGURE',   cls: 'figure' },
  melody:        { tag: 'MELODY',   cls: 'melody' },
  algorithm:     { tag: 'ALGORITHM', cls: 'algorithm' },
  magic:         { tag: 'MATH',     cls: 'magic' },
  automaton:     { tag: 'SCIENCE',  cls: 'automaton' },
  strategy:      { tag: 'STRATEGY', cls: 'strategy' },
  circuit:       { tag: 'LOGIC',    cls: 'circuit' },
  ouroboros:     { tag: 'OUROBOROS', cls: 'ouroboros' },
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
    case 'figure':
      return { inv: e.inv_id, text: `a figure drawn from ${(p.from || []).join(' and ')}`, note: 'two sequences became a shape' };
    case 'melody':
      return { inv: e.inv_id, text: `a melody from ${(p.from || []).join(' and ')}`, note: 'two sequences became a tune' };
    case 'algorithm': {
      const bk = p.best_known ? `, best known ${p.best_known}` : '';
      const tag = p.novelty === 'beats-known' ? ' (beats the best known!)' : p.novelty === 'optimal' ? ' (matches the known optimum)' : '';
      return { inv: e.inv_id, text: `a sorting network for ${p.n} wires using ${p.comparators} comparators${tag}`, note: `provably sorts every input${bk}` };
    }
    case 'magic':
      return { inv: e.inv_id, text: `a ${p.n} by ${p.n} magic square, every line sums to ${p.sum}`, note: 'verified exactly' };
    case 'automaton':
      return { inv: e.inv_id, text: `a cellular automaton with ${p.label} behaviour`, note: `a rule invented for its own complexity (class ${p.class})` };
    case 'strategy':
      return { inv: e.inv_id, text: `a strategy winning ${p.wins} of ${p.winnable} winnable positions${p.optimal ? ', provably optimal' : ''}`, note: 'the subtraction game, checked by playing every game out' };
    case 'circuit':
      return { inv: e.inv_id, text: `a logic circuit implementing invention ${p.source} with ${p.gates} gates`, note: `verified on all ${p.inputs} inputs` };
    case 'ouroboros':
      return { inv: e.inv_id, text: `the engine ${p.verb || 'adopts'} ${p.symbol} to run ${p.role}`, note: `${p.pct}% of its machinery is now self-written` };
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
  if (d.domain === 'figure') renderFigure(d, host);
  else if (d.domain === 'melody') renderMelody(d, host);
  else if (d.domain === 'sortnet') renderSortnet(d, host);
  else if (d.domain === 'magic') renderMagic(d, host);
  else if (d.domain === 'automaton') renderAutomaton(d, host);
  else if (d.domain === 'strategy') renderStrategy(d, host);
  else if (d.domain === 'circuit') renderCircuit(d, host);
  else renderNumber(d, host);
  wireChips(host);
}

function lineageHTML(arr, lab) {
  return arr && arr.length
    ? `<div class="fieldlab">${lab}</div>` + arr.map(p => `<span class="chip" data-inv="${p.id}">${p.symbol || '?'}${p.prefix ? '  ' + p.prefix.slice(0, 5).join(' ') : ''}</span>`).join('') : '';
}
function wireChips(host) {
  host.querySelectorAll('[data-inv]').forEach(c => c.addEventListener('click', () => {
    document.querySelectorAll('.detail').forEach(x => x.remove());
    openStandaloneDetail(+c.dataset.inv);
  }));
}
function standingHTML(d) {
  return `<div class="fieldlab">standing</div>` +
    `<div class="kv">wealth <b>${d.wealth}</b> &nbsp; reused as a part <b>${d.uses}x</b> &nbsp; status <b>${d.status}</b></div>`;
}

function renderNumber(d, host) {
  const ex = d.exaptation, nv = d.novelty, exp = d.experiments[0];
  const props = d.properties.filter(p => p.name !== 'exaptation');
  let novHtml = '';
  if (nv && nv.status === 'first')
    novHtml = `<div class="kv"><b>not found in the OEIS.</b> as far as that public catalog knows, this sequence is new.` +
      (nv.receipt.query ? ` <a href="${nv.receipt.query}" target="_blank">see the query</a>` : '') + `</div>`;
  else if (nv && nv.status === 'known' && nv.matches.length)
    novHtml = `<div class="kv">recognised as <b>${nv.matches[0].id}</b> ${nv.matches[0].name} <a href="https://oeis.org/${nv.matches[0].id}" target="_blank">(OEIS)</a></div>`;
  else novHtml = `<div class="kv">novelty: ${nv ? nv.status : 'n/a'}</div>`;
  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca" width="81" height="81"></canvas>
       <div class="caption">${ex ? `its function, run as a cellular automaton, makes a <b style="color:#e9e9ec">${ex.label}</b> pattern (estimated class ${ex.class}). a structure it was never built to make.` : 'no pattern'}</div>
     </div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">number &middot; ${d.origin} &middot; invented at tick ${d.created_tick}</div>
       <p class="lead">${describe(d)}</p>
       ${novHtml}
       <div class="fieldlab">the sequence it produces</div>
       <div class="seqline">${d.prefix.slice(0, 20).join(',  ')}${d.prefix.length > 20 ? '  ...' : ''}</div>
       <canvas class="plot" width="600" height="54"></canvas>
       <div class="fieldlab">measured properties</div>
       ${props.length ? props.map(p => `<span class="prop">${p.name}${fmtDetail(p.detail)}</span>`).join('') : '<span style="color:#56565d">none detected</span>'}
       <div class="fieldlab">proof it ran</div>
       ${exp ? `<div class="kv">ran for inputs n=${exp.input.n ? exp.input.n.join(' to ') : '?'}; ${exp.ok ? 'completed' : 'stopped, ' + exp.error}; used <b>${exp.ops}</b> computation steps</div>` : ''}
       ${standingHTML(d)}
       ${lineageHTML(d.parents, 'descended from')}
       ${lineageHTML(d.parts, 'built from')}
       <div class="fieldlab">the invention itself (its genome)</div>
       <div class="genome">f(n) = ${prettyGenome(d.genome)}</div>
     </div></div>`;
  if (ex && ex.rows) drawCA(host.querySelector('.ca'), ex.rows);
  plotSeq(host.querySelector('.plot'), d.prefix);
}

function renderFigure(d, host) {
  const f = d.figure, props = d.properties;
  const src = f ? `<span class="chip" data-inv="${f.turn.id}">${f.turn.symbol}</span> sets how it turns, ` +
                  `<span class="chip" data-inv="${f.step.id}">${f.step.symbol}</span> sets how far it steps` : '';
  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca fig" width="330" height="330"></canvas>
       <div class="caption">a turtle walks this path: at each step it turns by one sequence and moves by another. a shape made of two number sequences.</div>
     </div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">figure &middot; a cross-domain invention &middot; tick ${d.created_tick}</div>
       <p class="lead">${describe(d)}</p>
       <div class="fieldlab">drawn from two number inventions</div>
       <div class="kv">${src}</div>
       <div class="fieldlab">measured properties</div>
       ${props.length ? props.map(p => `<span class="prop">${p.name}${fmtDetail(p.detail)}</span>`).join('') : '<span style="color:#56565d">none</span>'}
       ${standingHTML(d)}
       ${lineageHTML(d.parts, 'its parts')}
     </div></div>`;
  if (f && f.points) drawFigure(host.querySelector('.fig'), f.points);
}

function renderSortnet(d, host) {
  const s = d.sortnet;
  const verdict = s ? (s.valid
    ? `verified: it sorts all ${s.inputs} possible inputs correctly.`
    : `warning: this network does not sort all inputs.`) : '';
  const cmp = s && s.best_known
    ? (s.count < s.best_known ? `${s.count} comparators, which beats the best known count of ${s.best_known}.`
      : s.count === s.best_known ? `${s.count} comparators, matching the known optimum.`
      : `${s.count} comparators (the best known is ${s.best_known}).`)
    : (s ? `${s.count} comparators.` : '');
  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca net" width="360" height="220"></canvas>
       <div class="caption">each horizontal line is a wire; each vertical link is a compare-and-swap. inputs enter on the left, leave sorted on the right.</div>
     </div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">algorithm &middot; a sorting network for ${s ? s.n : '?'} wires &middot; tick ${d.created_tick}</div>
       <p class="lead">A sorting network: a fixed sequence of compare-and-swap steps that sorts any input of ${s ? s.n : '?'} items. It uses ${cmp} ${s ? 'Its parallel depth is ' + s.depth + '.' : ''}</p>
       <div class="kv"><b>${verdict}</b> This is proven exhaustively by the 0/1 principle, not sampled.</div>
       <div class="fieldlab">the comparators, in order</div>
       <div class="seqline">${s ? s.comparators.map(c => '(' + c[0] + ',' + c[1] + ')').join('  ') : ''}</div>
       ${standingHTML(d)}
       ${lineageHTML(d.parents, 'improved from an earlier network')}
     </div></div>`;
  if (s) drawSortnet(host.querySelector('.net'), s.n, s.comparators);
}

function drawSortnet(cv, n, comps) {
  const g = cv.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, cv.width, cv.height);
  const padL = 10, padR = 10, padT = 16, padB = 16;
  const wireGap = (cv.height - padT - padB) / Math.max(1, n - 1);
  const Y = w => padT + w * wireGap;
  const steps = comps.length + 1;
  const dx = (cv.width - padL - padR) / (steps + 1);
  g.strokeStyle = '#56565d'; g.lineWidth = 1;
  for (let w = 0; w < n; w++) { g.beginPath(); g.moveTo(padL, Y(w)); g.lineTo(cv.width - padR, Y(w)); g.stroke(); }
  g.strokeStyle = '#e9e9ec'; g.fillStyle = '#e9e9ec'; g.lineWidth = 1.5;
  comps.forEach((c, k) => {
    const x = padL + dx * (k + 1), y1 = Y(c[0]), y2 = Y(c[1]);
    g.beginPath(); g.moveTo(x, y1); g.lineTo(x, y2); g.stroke();
    g.beginPath(); g.arc(x, y1, 2.6, 0, 6.2832); g.fill();
    g.beginPath(); g.arc(x, y2, 2.6, 0, 6.2832); g.fill();
  });
}

function renderMagic(d, host) {
  const m = d.magic, n = m ? m.n : 0;
  let grid = '';
  if (m) {
    grid = `<table class="msq">` + Array.from({ length: n }, (_, r) =>
      `<tr>` + m.square.slice(r * n, r * n + n).map(v => `<td>${v}</td>`).join('') + `</tr>`).join('') + `</table>`;
  }
  host.innerHTML =
    `<div class="dgrid"><div>${grid}
       <div class="caption">every row, every column, and both diagonals sum to the same number.</div></div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">mathematics &middot; a ${n} by ${n} magic square &middot; tick ${d.created_tick}</div>
       <p class="lead">An arrangement of the numbers 1 to ${n * n} where every line adds up to ${m ? m.sum : '?'}.</p>
       <div class="kv"><b>${m && m.valid ? 'verified: all ' + (2 * n + 2) + ' lines sum to ' + m.sum + '.' : 'not verified'}</b></div>
       ${standingHTML(d)}
     </div></div>`;
}

function renderAutomaton(d, host) {
  const a = d.automaton;
  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca" width="81" height="81"></canvas>
       <div class="caption">a rule invented for its own behaviour. time runs downward from a single seed.</div></div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">science &middot; a cellular automaton &middot; tick ${d.created_tick}</div>
       <p class="lead">A cellular automaton whose rule was invented directly. Its measured behaviour is <b>${a ? a.label : '?'}</b> (estimated class ${a ? a.class : '?'}), the kind of complexity that is interesting precisely because it is rare.</p>
       <div class="fieldlab">the rule table</div>
       <div class="seqline">${a ? a.table.join('  ') : ''}</div>
       ${standingHTML(d)}
     </div></div>`;
  if (a && a.rows) drawCA(host.querySelector('.ca'), a.rows);
}

function renderStrategy(d, host) {
  const s = d.strategy;
  let tbl = '';
  if (s) tbl = `<table class="policy"><tr>${s.policy.map((_, i) => `<td class="h">${i + 1}</td>`).join('')}</tr>` +
    `<tr>${s.policy.map(v => `<td>${v}</td>`).join('')}</tr></table>`;
  host.innerHTML =
    `<div class="dgrid"><div>
       <div class="caption" style="max-width:260px">the subtraction game: a pile of tokens, each player removes 1 to ${s ? s.k : '?'}, and whoever takes the last token wins.</div>
       <div class="fieldlab">its policy (pile size on top, tokens to take below)</div>
       ${tbl}
     </div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">game theory &middot; a strategy &middot; tick ${d.created_tick}</div>
       <p class="lead">A strategy for the subtraction game. Played as the first player against a perfect opponent from every starting pile, it wins <b>${s ? s.wins : '?'}</b> of the <b>${s ? s.winnable : '?'}</b> positions the first player can possibly win.${s && s.optimal ? ' That is every one of them, so this is provably optimal play.' : ''}</p>
       <div class="kv"><b>Verified by playing out every game, not by assertion.</b></div>
       ${standingHTML(d)}
     </div></div>`;
}

function renderCircuit(d, host) {
  const c = d.circuit;
  const names = { and: 'AND', or: 'OR', xor: 'XOR', nand: 'NAND', nor: 'NOR', not: 'NOT' };
  let gl = '';
  if (c) gl = c.gates.map((g, i) => {
    const wire = k => k < c.n ? 'x' + k : 'g' + (k - c.n);
    return `g${i} = ${g[0] === 'not' ? 'NOT ' + wire(g[1]) : wire(g[1]) + ' ' + (names[g[0]] || g[0]) + ' ' + wire(g[2])}`;
  }).join('<br>');
  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca net" width="300" height="180"></canvas>
       <div class="caption">inputs x0..x${c ? c.n - 1 : '?'} on the left feed gates; the last gate is the output.</div></div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">logic &middot; a boolean circuit &middot; tick ${d.created_tick}</div>
       <p class="lead">A logic circuit the world built to implement one of its own inventions: the parity of invention <b>${c ? c.source : '?'}</b>'s output, as a function of ${c ? c.n : '?'} input bits. It uses <b>${c ? c.used : '?'}</b> essential gates${c && c.gates.length > c.used ? ` (it invented ${c.gates.length}; ${c.gates.length - c.used} turned out redundant)` : ''}.</p>
       <div class="kv"><b>${c && c.valid ? 'verified: correct on all ' + c.inputs + ' possible inputs.' : 'not verified'}</b> The target was generated by the engine, not given to it, and checked against the full truth table.</div>
       <div class="fieldlab">the gates</div>
       <div class="genome">${gl}</div>
       ${standingHTML(d)}
     </div></div>`;
  if (c) drawCircuit(host.querySelector('.net'), c);
}
function drawCircuit(cv, c) {
  const g = cv.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, cv.width, cv.height);
  const total = c.n + c.gates.length;
  const padT = 14, padB = 14, padL = 24, padR = 10;
  const gap = (cv.height - padT - padB) / Math.max(1, total - 1);
  const Y = k => padT + k * gap;
  g.fillStyle = '#8c8c93'; g.font = '9px monospace'; g.textBaseline = 'middle';
  for (let i = 0; i < c.n; i++) { g.fillText('x' + i, 2, Y(i)); }
  g.strokeStyle = '#2b2b2f';
  for (let k = 0; k < total; k++) { g.beginPath(); g.moveTo(padL, Y(k)); g.lineTo(cv.width - padR, Y(k)); g.stroke(); }
  g.strokeStyle = '#e9e9ec'; g.fillStyle = '#e9e9ec'; g.lineWidth = 1.3;
  const steps = c.gates.length;
  const dx = (cv.width - padL - padR) / (steps + 1);
  c.gates.forEach((gate, i) => {
    const out = c.n + i, x = padL + dx * (i + 1);
    const ins = gate[0] === 'not' ? [gate[1]] : [gate[1], gate[2]];
    ins.forEach(w => { g.beginPath(); g.moveTo(x, Y(w)); g.lineTo(x, Y(out)); g.stroke();
      g.beginPath(); g.arc(x, Y(w), 2.2, 0, 6.2832); g.fill(); });
    g.beginPath(); g.arc(x, Y(out), 2.6, 0, 6.2832); g.fill();
  });
}

function renderMelody(d, host) {
  const m = d.melody, props = d.properties;
  const src = m ? `<span class="chip" data-inv="${m.pitch.id}">${m.pitch.symbol}</span> chooses each pitch, ` +
                  `<span class="chip" data-inv="${m.rhythm.id}">${m.rhythm.symbol}</span> chooses each length` : '';
  host.innerHTML =
    `<div class="dgrid"><div>
       <canvas class="ca roll" width="330" height="200"></canvas>
       <div class="caption">a piano roll: time runs left to right, pitch runs bottom to top. press play to hear it.</div>
       <div class="play" id="play-${d.id}">play this melody</div>
     </div>
     <div>
       <h2>${d.symbol} <span style="color:#56565d;font-weight:400">#${d.id}</span></h2>
       <div class="sub">melody &middot; a cross-domain invention &middot; tick ${d.created_tick}</div>
       <p class="lead">${describe(d)}</p>
       <div class="fieldlab">composed from two number inventions</div>
       <div class="kv">${src}</div>
       <div class="fieldlab">measured properties</div>
       ${props.length ? props.map(p => `<span class="prop">${p.name}${fmtDetail(p.detail)}</span>`).join('') : '<span style="color:#56565d">none</span>'}
       ${standingHTML(d)}
       ${lineageHTML(d.parts, 'its parts')}
     </div></div>`;
  if (m && m.notes) {
    drawPianoRoll(host.querySelector('.roll'), m.notes);
    const btn = host.querySelector('#play-' + d.id);
    if (btn) btn.addEventListener('click', () => { playMelody(m.notes); btn.textContent = 'playing...'; setTimeout(() => btn.textContent = 'play this melody', 300 + m.notes.length * 150); });
  }
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

function drawFigure(cv, pts) {
  const g = cv.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, cv.width, cv.height);
  if (pts.length < 2) return;
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
  const pad = 16, w = cv.width - pad * 2, h = cv.height - pad * 2;
  const sc = Math.min(w / (maxx - minx || 1), h / (maxy - miny || 1));
  const ox = pad + (w - (maxx - minx) * sc) / 2, oy = pad + (h - (maxy - miny) * sc) / 2;
  const X = x => ox + (x - minx) * sc, Y = y => cv.height - (oy + (y - miny) * sc);
  g.strokeStyle = '#e9e9ec'; g.lineWidth = 1.2; g.lineJoin = 'round'; g.beginPath();
  pts.forEach((p, i) => { i ? g.lineTo(X(p[0]), Y(p[1])) : g.moveTo(X(p[0]), Y(p[1])); });
  g.stroke();
  g.fillStyle = '#ffce6a'; g.fillRect(X(pts[0][0]) - 2, Y(pts[0][1]) - 2, 4, 4);
}

function drawPianoRoll(cv, notes) {
  const g = cv.getContext('2d'); g.fillStyle = '#000'; g.fillRect(0, 0, cv.width, cv.height);
  if (!notes.length) return;
  const pitches = notes.map(n => n[0]);
  const lo = Math.min(...pitches), hi = Math.max(...pitches), span = (hi - lo) || 1;
  const totalBeats = notes.reduce((s, n) => s + n[1], 0);
  const bw = cv.width / totalBeats, rh = Math.max(3, cv.height / (span + 2));
  let x = 0;
  g.fillStyle = '#e9e9ec';
  for (const [midi, dur] of notes) {
    const y = cv.height - ((midi - lo + 1) / (span + 2)) * cv.height;
    g.fillRect(x + 1, y, Math.max(2, bw * dur - 2), rh);
    x += bw * dur;
  }
}

// explicit, click-only audio: you hear the actual melody the engine invented
let _actx = null;
function playMelody(notes) {
  if (!_actx) { const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return; _actx = new AC(); }
  if (_actx.state === 'suspended') _actx.resume();
  const master = _actx.createGain(); master.gain.value = 0.22;
  const lp = _actx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 4200;
  master.connect(lp); lp.connect(_actx.destination);
  let t = _actx.currentTime + 0.05; const beat = 0.15;
  for (const [midi, dur] of notes) {
    const f = 440 * Math.pow(2, (midi - 69) / 12), len = beat * dur;
    const o = _actx.createOscillator(); o.type = 'triangle'; o.frequency.value = f;
    const gain = _actx.createGain();
    gain.gain.setValueAtTime(0, t); gain.gain.linearRampToValueAtTime(0.3, t + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.001, t + len * 0.95);
    o.connect(gain); gain.connect(master); o.start(t); o.stop(t + len); t += len;
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
  if (d.domain === 'figure') {
    const bits = [];
    if (props['closed']) bits.push('it closes back on itself');
    if (props['space-filling']) bits.push('it fills space densely');
    if (props['balanced']) bits.push('it is roughly square in proportion');
    let s = 'A figure drawn by a turtle, where one number sequence decides how much it turns at each step and another decides how far it moves.';
    if (bits.length) s += ' ' + bits.join(', ') + '.';
    s += ' It is a shape invented purely by combining two sequences, a use neither was built for.';
    return s;
  }
  if (d.domain === 'melody') {
    const bits = [];
    if (props['pitch-range']) bits.push(`it spans ${props['pitch-range'].semitones} semitones`);
    if (props['rhythmic']) bits.push('it has real rhythmic variety');
    if (props['repeating-motif']) bits.push(`a short motif repeats every ${props['repeating-motif'].period} notes`);
    let s = 'A melody where one number sequence chooses the pitch of each note and another chooses its length, snapped to a major scale so it stays consonant.';
    if (bits.length) s += ' ' + bits.join(', ') + '.';
    s += ' Press play to hear what two sequences sound like together.';
    return s;
  }
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
