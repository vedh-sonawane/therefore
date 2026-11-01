"""Other domains, built by composing number inventions.

The engine invents functions. Here it takes those functions and composes them into
objects that live in different domains entirely:

  * a FIGURE: a turtle walks a path. One number invention decides how much it turns at
    each step, another decides how far it moves. Two sequences become a drawn shape.
  * a MELODY: one number invention decides the pitch of each note, another its length.
    Two sequences become something you can hear.

These are genuine cross-domain inventions: the number inventions are their real parts,
so lineage and the economy flow across the boundary. And they are perceivable - a figure
is drawn, a melody is played - which is the point. Everything is computed deterministically
from the referenced functions, so it is as reproducible as everything else.
"""

import math

from ..vm import run

FIG_N = 110
MEL_N = 32
SCALE = [0, 2, 4, 5, 7, 9, 11]   # a major scale, so melodies stay consonant
FUEL = 40_000


def _series(inv, registry, laws, n):
    out = []
    for i in range(n):
        r = run(inv, [i], registry, laws=laws, fuel=FUEL)
        if r.ok and isinstance(r.value, int) and not isinstance(r.value, bool):
            out.append(r.value)
        else:
            break
    return out


# ---- figures ---------------------------------------------------------------
def build_figure(turn_inv, step_inv, registry, laws, n=FIG_N):
    turns = _series(turn_inv, registry, laws, n)
    steps = _series(step_inv, registry, laws, n)
    m = min(len(turns), len(steps))
    x = y = ang = 0.0
    pts = [(0.0, 0.0)]
    for i in range(m):
        ang += (turns[i] % 24) * (math.pi / 12.0)   # 24 possible headings
        d = 1 + (abs(steps[i]) % 7)
        x += math.cos(ang) * d
        y += math.sin(ang) * d
        pts.append((round(x, 2), round(y, 2)))
    return pts


def measure_figure(pts):
    props = []
    if len(pts) < 30:
        return props, False, 0.0
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    w = max(xs) - min(xs); h = max(ys) - min(ys)
    if w < 2 or h < 2:
        return props, False, 0.0  # a line or a dot
    cells = {(round(x), round(y)) for x, y in pts}
    coverage = len(cells) / max(1.0, w * h)
    closed = math.dist(pts[0], pts[-1]) < 3.0
    props.append(("bounded", {"w": round(w, 1), "h": round(h, 1)}))
    if closed:
        props.append(("closed", {}))
    if coverage > 0.5:
        props.append(("space-filling", {"coverage": round(coverage, 2)}))
    if 0.8 < (w / h) < 1.25:
        props.append(("balanced", {}))
    score = 2.0 + len(pts) / 40.0 + (1.5 if closed else 0) + coverage * 2.0
    interesting = len(cells) >= 20
    return props, interesting, round(score, 2)


def figure_signature(pts):
    # a compact, stable fingerprint: coarse grid cells visited, for dedup
    cells = sorted({(round(x / 2), round(y / 2)) for x, y in pts})
    return cells[:80]


# ---- melodies --------------------------------------------------------------
def build_melody(pitch_inv, rhythm_inv, registry, laws, n=MEL_N):
    ps = _series(pitch_inv, registry, laws, n)
    rs = _series(rhythm_inv, registry, laws, n)
    m = min(len(ps), len(rs))
    notes = []
    for i in range(m):
        deg = SCALE[ps[i] % len(SCALE)]
        octave = (abs(ps[i]) // len(SCALE)) % 3
        midi = 48 + deg + 12 * octave
        dur = 1 + (abs(rs[i]) % 4)
        notes.append([midi, dur])
    return notes


def measure_melody(notes):
    props = []
    if len(notes) < 10:
        return props, False, 0.0
    pitches = [nn[0] for nn in notes]
    durs = [nn[1] for nn in notes]
    distinct_p = len(set(pitches))
    rng = max(pitches) - min(pitches)
    moves = sum(1 for i in range(1, len(pitches)) if pitches[i] != pitches[i - 1])
    props.append(("in-scale", {}))
    props.append(("pitch-range", {"semitones": rng}))
    if len(set(durs)) > 1:
        props.append(("rhythmic", {"patterns": len(set(durs))}))
    # periodicity: does a short motif repeat?
    for p in range(2, 6):
        if len(pitches) > 2 * p and all(pitches[i] == pitches[i - p] for i in range(p, len(pitches))):
            props.append(("repeating-motif", {"period": p})); break
    interesting = distinct_p >= 4 and rng >= 3 and moves >= len(notes) // 2
    score = 2.0 + distinct_p / 4.0 + rng / 12.0 + (len(set(durs)) - 1) * 0.8
    return props, interesting, round(score, 2)


def melody_signature(notes):
    return [nn[0] for nn in notes][:40]
