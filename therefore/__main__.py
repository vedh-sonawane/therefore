"""Boot THEREFORE: start the engine, start the server, open the organism.

    python -m therefore                 run the world + UI at http://localhost:8000
    python -m therefore --civs 3        start (or resume) with N civilizations
    python -m therefore --dump          print a text summary of the world and exit
    python -m therefore --no-browser    don't auto-open a browser
"""

import argparse
import sys
import threading
import time
import webbrowser

# make the console tolerant of alien glyphs on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from .store import Store, DB_PATH
from .engine.loop import Engine
from .server import serve

BANNER = r"""
        ∴  T H E R E F O R E
        an autonomous invention engine  -  every invention follows from the ones before it
"""


def dump(store):
    snap = store.snapshot()
    print(BANNER)
    print(f"tick {snap['tick']}   |   {snap['totals']['inventions']} inventions   "
          f"{snap['totals']['firsts']} firsts   {snap['totals']['experiments']} experiments")
    for c in snap["civs"]:
        print(f"\n  {c['glyph']} {c['name']}  (civ {c['id']}, era {c['era']})")
        print(f"     alive {c['alive']}  dormant {c['dormant']}  firsts {c['firsts']}  "
              f"richest {c['max_wealth']}")
        rows = store.load_inventions(c["id"], statuses=["alive"])
        rows.sort(key=lambda r: r["wealth"], reverse=True)
        for r in rows[:6]:
            import json
            pre = json.loads(r["prefix_json"] or "[]")[:7]
            print(f"       {r['symbol']:6} {r['origin']:16} w={r['wealth']:.1f} "
                  f"uses={r['uses']} [{r['novelty']}] {pre}")


def main():
    ap = argparse.ArgumentParser(prog="therefore")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--civs", type=int, default=3)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--tick-sleep", type=float, default=0.05)
    args = ap.parse_args()

    store = Store(path=DB_PATH)

    if args.dump:
        dump(store)
        return

    engine = Engine(store, n_civs=args.civs)
    print(BANNER)
    print(f"  resuming at tick {engine.tick} with {len(engine.civs)} civilization(s)")

    t = threading.Thread(target=engine.run_forever, args=(args.tick_sleep,), daemon=True)
    t.start()

    httpd = serve(args.port)
    url = f"http://localhost:{args.port}"
    print(f"  the organism is alive at  {url}")
    print("  (close this window or Ctrl-C to pause the world; it resumes exactly here)\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # light narration so something is visible with the browser closed
    narrator = threading.Thread(target=_narrate, args=(store, engine), daemon=True)
    narrator.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        httpd.shutdown()
        print("\n  paused. the world is saved.")


def _narrate(store, engine):
    seen = store.last_event_id()
    while True:
        time.sleep(2.0)
        try:
            evs = store.events_after(seen, limit=50)
        except Exception:
            continue
        for e in evs:
            seen = e["id"]
            import json
            p = json.loads(e["payload_json"] or "{}")
            if e["type"] == "first":
                print(f"  ∴ FIRST  civ{e['civ_id']} {p.get('symbol','')}  "
                      f"{p.get('seq', [])[:8]}  - not found in OEIS")
            elif e["type"] == "known":
                m = p.get("matches", [{}])
                print(f"  · known  civ{e['civ_id']} {p.get('symbol','')} = "
                      f"{m[0].get('id','')} {m[0].get('name','')[:40]}")
            elif e["type"] == "dormant":
                print(f"  × dormant civ{e['civ_id']} {p.get('symbol','')} went bankrupt")


if __name__ == "__main__":
    main()
