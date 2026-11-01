"""The local server.

Serves the organism UI and exposes the world as read-only JSON:

    /api/state                live snapshot (ticks, civs, totals)
    /api/stream               Server-Sent Events: births, discoveries, firsts, deaths
    /api/civ/<id>             a civilization's library (lightweight list)
    /api/invention/<id>       full inspection: genome, results, properties,
                              novelty receipt, lineage (parents + parts), ledger
    /api/vault                the vault of FIRSTS

Everything it returns is read straight from SQLite - the same rows the engine wrote.
WAL mode lets these reads run while the engine keeps writing.
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from ..store import Store, DB_PATH
from ..vm import genome as g
from ..engine import exapt
from ..engine.invention import Invention

UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
_CT = {".html": "text/html", ".js": "application/javascript", ".css": "text/css",
       ".json": "application/json", ".svg": "image/svg+xml", ".ico": "image/x-icon",
       ".woff2": "font/woff2"}


def _store():
    return Store(path=DB_PATH, create=False)


def _exaptation_render(st, inv):
    """Recompute the invention's cellular-automaton exaptation for display.

    Loads the civilization's inventions so calls resolve, then evolves the CA whose
    rule is this invention. Cheap enough to do on a click.
    """
    try:
        import json as _json
        rows = st.load_inventions(inv["civ_id"], statuses=["alive", "dormant"])
        reg = {r["id"]: Invention.from_row(r) for r in rows}
        target = reg.get(inv["id"]) or Invention.from_row(inv)
        civ = next((c for c in st.get_civs() if c["id"] == inv["civ_id"]), None)
        laws = _json.loads(civ["laws_json"]) if civ else None
        sp = exapt.spacetime(target, reg, laws, states=4, width=81, steps=81)
        cls = exapt.classify(sp)
        return {"states": sp["states"], "rows": sp["rows"], **cls}
    except Exception:
        return None


def _invention_detail(st, inv_id):
    inv = st.get_invention(inv_id)
    if not inv:
        return None
    props = [{"name": p["name"], "detail": json.loads(p["detail_json"])}
             for p in st.get_properties(inv_id)]
    exps = [{"kind": e["kind"], "input": json.loads(e["input_json"]),
             "output": json.loads(e["output_json"]), "ops": e["ops"],
             "ok": bool(e["ok"]), "error": e["error"], "tick": e["created_tick"]}
            for e in st.get_experiments(inv_id, limit=8)]
    nov = st.get_novelty(inv_id)
    novelty = None
    if nov:
        novelty = {"status": nov["status"], "catalog": nov["catalog"],
                   "matches": json.loads(nov["matches_json"] or "[]"),
                   "receipt": json.loads(nov["receipt_json"] or "{}"),
                   "seq": json.loads(nov["seq_json"] or "[]")}
    parents = json.loads(inv["parents_json"] or "[]")
    parts = json.loads(inv["parts_json"] or "[]")

    def brief(iid):
        r = st.get_invention(iid)
        return {"id": iid, "symbol": r["symbol"], "name": r["name"],
                "prefix": json.loads(r["prefix_json"] or "[]")[:8]} if r else {"id": iid}

    return {
        "id": inv["id"], "civ_id": inv["civ_id"], "symbol": inv["symbol"],
        "name": inv["name"], "origin": inv["origin"], "status": inv["status"],
        "created_tick": inv["created_tick"], "wealth": round(inv["wealth"], 2),
        "uses": inv["uses"], "total": bool(inv["total"]), "score": inv["score"],
        "novelty_status": inv["novelty"],
        "sig": [json.loads(inv["sig_in_json"]), inv["sig_out"]],
        "prefix": json.loads(inv["prefix_json"] or "[]"),
        "genome": json.loads(inv["body_json"]),
        "genome_size": g.size(json.loads(inv["body_json"])),
        "uses_self": g.uses_self(json.loads(inv["body_json"])),
        "properties": props, "experiments": exps, "novelty": novelty,
        "parents": [brief(i) for i in parents],
        "parts": [brief(i) for i in parts],
        "exaptation": _exaptation_render(st, inv),
    }


def _civ_detail(st, civ_id):
    rows = st.load_inventions(civ_id, statuses=["alive", "dormant"])
    invs = []
    for r in rows:
        invs.append({
            "id": r["id"], "symbol": r["symbol"], "name": r["name"],
            "origin": r["origin"], "status": r["status"],
            "wealth": round(r["wealth"], 2), "uses": r["uses"],
            "total": bool(r["total"]), "score": r["score"],
            "novelty": r["novelty"], "prefix": json.loads(r["prefix_json"] or "[]")[:12],
            "parts": json.loads(r["parts_json"] or "[]"),
        })
    civ = next((c for c in st.get_civs() if c["id"] == civ_id), None)
    return {"civ": {"id": civ["id"], "name": civ["name"], "glyph": civ["glyph"],
                    "era": civ["era"], "taste": json.loads(civ["taste_json"])} if civ else None,
            "inventions": invs}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass  # keep the console quiet; the engine narrates instead

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        ext = os.path.splitext(path)[1]
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", _CT.get(ext, "application/octet-stream") +
                         ("; charset=utf-8" if ext in (".html", ".js", ".css") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        if path.startswith("/api/"):
            return self._api(path, parse_qs(u.query))
        # static UI
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        rel = rel.replace("..", "")
        full = os.path.join(UI_DIR, rel)
        if os.path.isfile(full):
            return self._send_file(full)
        return self._send_file(os.path.join(UI_DIR, "index.html"))

    def _api(self, path, qs):
        if path == "/api/stream":
            return self._stream()
        st = _store()
        try:
            if path == "/api/state":
                return self._send_json(st.snapshot())
            if path == "/api/events":
                after = int((qs.get("after", ["0"])[0]) or 0)
                return self._send_json({"events": _events(st, after)})
            if path == "/api/vault":
                return self._send_json({"vault": [
                    {"inv_id": v["inv_id"], "symbol": v["symbol"], "civ_id": v["civ_id"],
                     "seq": json.loads(v["seq_json"] or "[]"),
                     "receipt": json.loads(v["receipt_json"] or "{}"),
                     "tick": v["checked_tick"]} for v in st.get_vault(120)]})
            if path.startswith("/api/civ/"):
                return self._send_json(_civ_detail(st, int(path.rsplit("/", 1)[1])))
            if path.startswith("/api/invention/"):
                d = _invention_detail(st, int(path.rsplit("/", 1)[1]))
                return self._send_json(d or {"error": "not found"}, 200 if d else 404)
            self.send_error(404)
        finally:
            st.close()

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        st = _store()
        # On a fresh connect, start from *now* - the UI already got the backlog via
        # /api/state, and replaying thousands of historical births would be a cacophony.
        # On reconnect the browser sends Last-Event-ID, so we resume precisely.
        last = int(self.headers.get("Last-Event-ID", 0) or 0) or st.last_event_id()
        try:
            while True:
                evs = _events(st, last)
                for e in evs:
                    last = e["id"]
                    chunk = f"id: {e['id']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                    self.wfile.write(chunk.encode("utf-8"))
                self.wfile.write(b": ping\n\n")  # keep-alive comment
                self.wfile.flush()
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            st.close()


def _events(st, after):
    out = []
    for e in st.events_after(after, limit=300):
        out.append({"id": e["id"], "tick": e["tick"], "civ_id": e["civ_id"],
                    "inv_id": e["inv_id"], "type": e["type"],
                    "payload": json.loads(e["payload_json"] or "{}")})
    return out


def serve(port=8000):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    return httpd
