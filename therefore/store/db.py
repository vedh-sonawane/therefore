"""Persistence. One SQLite file is the entire world.

Design rules that matter here:
  * Append-only. Nothing is ever DELETEd. Inventions die by having their `status`
    flipped to 'dormant'/'dead' - their genome, results, and lineage stay forever,
    because resurrection digs them back up later.
  * WAL mode, so the engine thread can write while the server threads read.
  * Everything the UI shows traces to a row in here: every property to a discovery,
    every discovery to an experiment, every "first" to a stored novelty receipt.
"""

import json
import os
import sqlite3
import threading
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "therefore.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS civilizations (
    id           INTEGER PRIMARY KEY,
    name         TEXT,
    glyph        TEXT,
    seed         INTEGER,
    laws_json    TEXT,
    taste_json   TEXT,
    lexicon_json TEXT,
    era          INTEGER DEFAULT 0,
    created_tick INTEGER,
    status       TEXT DEFAULT 'alive'
);

CREATE TABLE IF NOT EXISTS inventions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    civ_id        INTEGER,
    name          TEXT,
    symbol        TEXT,
    sig_in_json   TEXT,
    sig_out       TEXT,
    body_json     TEXT,
    parents_json  TEXT,
    parts_json    TEXT,
    origin        TEXT,
    created_tick  INTEGER,
    status        TEXT DEFAULT 'alive',
    wealth        REAL DEFAULT 0,
    uses          INTEGER DEFAULT 0,
    behavior_hash TEXT,
    prefix_json   TEXT,
    total         INTEGER DEFAULT 0,
    score         REAL DEFAULT 0,
    novelty       TEXT DEFAULT 'pending',
    exapted       INTEGER DEFAULT 0,
    exapt_class   TEXT,
    domain        TEXT DEFAULT 'number'
);
CREATE INDEX IF NOT EXISTS idx_inv_civ   ON inventions(civ_id);
CREATE INDEX IF NOT EXISTS idx_inv_behav ON inventions(civ_id, behavior_hash);

CREATE TABLE IF NOT EXISTS experiments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    inv_id       INTEGER,
    kind         TEXT,
    input_json   TEXT,
    output_json  TEXT,
    ops          INTEGER,
    ok           INTEGER,
    error        TEXT,
    created_tick INTEGER
);
CREATE INDEX IF NOT EXISTS idx_exp_inv ON experiments(inv_id);

CREATE TABLE IF NOT EXISTS properties (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    inv_id       INTEGER,
    name         TEXT,
    detail_json  TEXT,
    created_tick INTEGER
);
CREATE INDEX IF NOT EXISTS idx_prop_inv ON properties(inv_id);

CREATE TABLE IF NOT EXISTS novelty (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    inv_id       INTEGER,
    seq_json     TEXT,
    status       TEXT,          -- 'first' | 'known' | 'unchecked' | 'trivial'
    catalog      TEXT,          -- e.g. 'OEIS'
    matches_json TEXT,          -- [{id, name}] when known
    receipt_json TEXT,          -- raw evidence (query url + response summary)
    checked_tick INTEGER
);
CREATE INDEX IF NOT EXISTS idx_nov_inv ON novelty(inv_id);

CREATE TABLE IF NOT EXISTS ledger (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tick     INTEGER,
    inv_id   INTEGER,
    delta    REAL,
    reason   TEXT,
    balance  REAL
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tick        INTEGER,
    civ_id      INTEGER,
    inv_id      INTEGER,
    type        TEXT,
    payload_json TEXT,
    ts          REAL
);

CREATE TABLE IF NOT EXISTS oeis_cache (
    q        TEXT PRIMARY KEY,
    response TEXT,
    ts       REAL
);
"""


def _j(x):
    return json.dumps(x, separators=(",", ":"))


class Store:
    """A thread-local-ish connection wrapper. Open one per thread that uses it."""

    def __init__(self, path=DB_PATH, create=True):
        if create:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._lock = threading.Lock()
        if create:
            self.conn.executescript(SCHEMA)
            self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Add columns that newer versions introduced, for worlds created earlier."""
        existing = {r["name"] for r in self.conn.execute("PRAGMA table_info(inventions)")}
        for col, ddl in (("exapted", "INTEGER DEFAULT 0"), ("exapt_class", "TEXT"),
                         ("domain", "TEXT DEFAULT 'number'")):
            if col not in existing:
                try:
                    self.conn.execute(f"ALTER TABLE inventions ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
        self.conn.commit()

    # -- exaptation ----------------------------------------------------------
    def get_unexapted(self, civ_id, limit=4):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM inventions WHERE civ_id=? AND status='alive' AND total=1 "
            "AND COALESCE(domain,'number')='number' AND COALESCE(exapted,0)=0 "
            "ORDER BY wealth DESC LIMIT ?",
            (civ_id, limit)).fetchall()]

    def set_exapted(self, inv_id, cls):
        with self._lock:
            self.conn.execute(
                "UPDATE inventions SET exapted=1, exapt_class=? WHERE id=?", (cls, inv_id))
            self.conn.commit()

    # -- meta ----------------------------------------------------------------
    def get_meta(self, key, default=None):
        r = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_meta(self, key, value):
        with self._lock:
            self.conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
            self.conn.commit()

    # -- civilizations -------------------------------------------------------
    def insert_civ(self, name, glyph, seed, laws, taste, lexicon, tick):
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO civilizations(name,glyph,seed,laws_json,taste_json,"
                "lexicon_json,era,created_tick,status) VALUES(?,?,?,?,?,?,?,?, 'alive')",
                (name, glyph, seed, _j(laws), _j(taste), _j(lexicon), 0, tick))
            self.conn.commit()
            return cur.lastrowid

    def get_civs(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM civilizations ORDER BY id").fetchall()]

    def update_civ(self, civ_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self.conn.execute(f"UPDATE civilizations SET {cols} WHERE id=?",
                              (*fields.values(), civ_id))
            self.conn.commit()

    # -- inventions ----------------------------------------------------------
    def insert_invention(self, row):
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO inventions(civ_id,name,symbol,sig_in_json,sig_out,"
                "body_json,parents_json,parts_json,origin,created_tick,status,"
                "wealth,uses,behavior_hash,prefix_json,total,score,novelty,domain) "
                "VALUES(:civ_id,:name,:symbol,:sig_in_json,:sig_out,:body_json,"
                ":parents_json,:parts_json,:origin,:created_tick,:status,:wealth,"
                ":uses,:behavior_hash,:prefix_json,:total,:score,:novelty,:domain)", row)
            self.conn.commit()
            return cur.lastrowid

    def update_invention(self, inv_id, **fields):
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock:
            self.conn.execute(f"UPDATE inventions SET {cols} WHERE id=?",
                              (*fields.values(), inv_id))
            self.conn.commit()

    def bump_use_and_wealth(self, inv_id, earn, tick, reason="used-as-part"):
        with self._lock:
            self.conn.execute(
                "UPDATE inventions SET uses=uses+1, wealth=wealth+? WHERE id=?",
                (earn, inv_id))
            bal = self.conn.execute("SELECT wealth FROM inventions WHERE id=?",
                                    (inv_id,)).fetchone()["wealth"]
            self.conn.execute(
                "INSERT INTO ledger(tick,inv_id,delta,reason,balance) VALUES(?,?,?,?,?)",
                (tick, inv_id, earn, reason, bal))
            self.conn.commit()

    def charge_rent(self, civ_id, amount, tick):
        """Rent every alive invention; return ids that just went bankrupt."""
        with self._lock:
            self.conn.execute(
                "UPDATE inventions SET wealth=wealth-? WHERE civ_id=? AND status='alive'",
                (amount, civ_id))
            dead = [r["id"] for r in self.conn.execute(
                "SELECT id FROM inventions WHERE civ_id=? AND status='alive' AND wealth<=0",
                (civ_id,)).fetchall()]
            if dead:
                qmarks = ",".join("?" * len(dead))
                self.conn.execute(
                    f"UPDATE inventions SET status='dormant' WHERE id IN ({qmarks})", dead)
            self.conn.commit()
            return dead

    def bulk_status(self, ids, status):
        if not ids:
            return
        with self._lock:
            q = ",".join("?" * len(ids))
            self.conn.execute(
                f"UPDATE inventions SET status=? WHERE id IN ({q})", (status, *ids))
            self.conn.commit()

    def load_inventions(self, civ_id=None, statuses=None):
        q = "SELECT * FROM inventions"
        conds, args = [], []
        if civ_id is not None:
            conds.append("civ_id=?"); args.append(civ_id)
        if statuses:
            conds.append("status IN (%s)" % ",".join("?" * len(statuses)))
            args.extend(statuses)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    def get_invention(self, inv_id):
        r = self.conn.execute("SELECT * FROM inventions WHERE id=?", (inv_id,)).fetchone()
        return dict(r) if r else None

    def find_behavior(self, civ_id, behavior_hash):
        r = self.conn.execute(
            "SELECT id FROM inventions WHERE civ_id=? AND behavior_hash=? LIMIT 1",
            (civ_id, behavior_hash)).fetchone()
        return r["id"] if r else None

    def find_behavior_global(self, behavior_hash, exclude_civ=None):
        """Any civ (other than exclude_civ) that invented the same behaviour."""
        if exclude_civ is None:
            rows = self.conn.execute(
                "SELECT id,civ_id FROM inventions WHERE behavior_hash=?",
                (behavior_hash,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id,civ_id FROM inventions WHERE behavior_hash=? AND civ_id<>?",
                (behavior_hash, exclude_civ)).fetchall()
        return [dict(r) for r in rows]

    # -- experiments / properties / novelty ----------------------------------
    def insert_experiment(self, inv_id, kind, inp, out, ops, ok, error, tick):
        with self._lock:
            self.conn.execute(
                "INSERT INTO experiments(inv_id,kind,input_json,output_json,ops,ok,"
                "error,created_tick) VALUES(?,?,?,?,?,?,?,?)",
                (inv_id, kind, _j(inp), _j(out), ops, int(ok), error, tick))
            self.conn.commit()

    def insert_property(self, inv_id, name, detail, tick):
        with self._lock:
            self.conn.execute(
                "INSERT INTO properties(inv_id,name,detail_json,created_tick) VALUES(?,?,?,?)",
                (inv_id, name, _j(detail), tick))
            self.conn.commit()

    def insert_novelty(self, inv_id, seq, status, catalog, matches, receipt, tick):
        with self._lock:
            self.conn.execute(
                "INSERT INTO novelty(inv_id,seq_json,status,catalog,matches_json,"
                "receipt_json,checked_tick) VALUES(?,?,?,?,?,?,?)",
                (inv_id, _j(seq), status, catalog, _j(matches), _j(receipt), tick))
            self.conn.commit()

    def get_properties(self, inv_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT name,detail_json FROM properties WHERE inv_id=? ORDER BY id",
            (inv_id,)).fetchall()]

    def get_experiments(self, inv_id, limit=20):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM experiments WHERE inv_id=? ORDER BY id DESC LIMIT ?",
            (inv_id, limit)).fetchall()]

    def get_novelty(self, inv_id):
        r = self.conn.execute(
            "SELECT * FROM novelty WHERE inv_id=? ORDER BY id DESC LIMIT 1",
            (inv_id,)).fetchone()
        return dict(r) if r else None

    def get_vault(self, limit=200):
        return [dict(r) for r in self.conn.execute(
            "SELECT n.*, i.symbol, i.name AS inv_name, i.civ_id FROM novelty n "
            "JOIN inventions i ON i.id=n.inv_id WHERE n.status='first' "
            "ORDER BY n.id DESC LIMIT ?", (limit,)).fetchall()]

    # -- oeis cache ----------------------------------------------------------
    def oeis_cached(self, q):
        r = self.conn.execute("SELECT response FROM oeis_cache WHERE q=?", (q,)).fetchone()
        return r["response"] if r else None

    def oeis_store(self, q, response, ts):
        with self._lock:
            self.conn.execute(
                "INSERT INTO oeis_cache(q,response,ts) VALUES(?,?,?) "
                "ON CONFLICT(q) DO UPDATE SET response=excluded.response, ts=excluded.ts",
                (q, response, ts))
            self.conn.commit()

    # -- events --------------------------------------------------------------
    def add_event(self, tick, civ_id, inv_id, etype, payload):
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO events(tick,civ_id,inv_id,type,payload_json,ts) "
                "VALUES(?,?,?,?,?,?)",
                (tick, civ_id, inv_id, etype, _j(payload), time.time()))
            self.conn.commit()
            return cur.lastrowid

    def events_after(self, after_id, limit=200):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?",
            (after_id, limit)).fetchall()]

    def last_event_id(self):
        r = self.conn.execute("SELECT MAX(id) AS m FROM events").fetchone()
        return r["m"] or 0

    # -- snapshots for the UI ------------------------------------------------
    def snapshot(self):
        tick = int(self.get_meta("tick", 0) or 0)
        civs = []
        for c in self.get_civs():
            counts = self.conn.execute(
                "SELECT status, COUNT(*) n FROM inventions WHERE civ_id=? GROUP BY status",
                (c["id"],)).fetchall()
            by = {r["status"]: r["n"] for r in counts}
            wealth = self.conn.execute(
                "SELECT COALESCE(SUM(wealth),0) w, COALESCE(MAX(wealth),0) mx "
                "FROM inventions WHERE civ_id=? AND status='alive'", (c["id"],)).fetchone()
            firsts = self.conn.execute(
                "SELECT COUNT(*) n FROM novelty n JOIN inventions i ON i.id=n.inv_id "
                "WHERE i.civ_id=? AND n.status='first'", (c["id"],)).fetchone()["n"]
            taste_top = None
            try:
                import json as _json
                tv = _json.loads(c["taste_json"] or "{}")
                if tv:
                    taste_top = max(tv, key=tv.get)
            except Exception:
                pass
            civs.append({
                "id": c["id"], "name": c["name"], "glyph": c["glyph"],
                "era": c["era"], "status": c["status"],
                "alive": by.get("alive", 0), "dormant": by.get("dormant", 0),
                "total": sum(by.values()),
                "wealth": round(wealth["w"], 2), "max_wealth": round(wealth["mx"], 2),
                "firsts": firsts, "taste_top": taste_top,
            })
        return {
            "tick": tick,
            "civs": civs,
            "totals": {
                "inventions": self.conn.execute(
                    "SELECT COUNT(*) n FROM inventions").fetchone()["n"],
                "firsts": self.conn.execute(
                    "SELECT COUNT(*) n FROM novelty WHERE status='first'").fetchone()["n"],
                "experiments": self.conn.execute(
                    "SELECT COUNT(*) n FROM experiments").fetchone()["n"],
            },
            "last_event": self.last_event_id(),
        }

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
