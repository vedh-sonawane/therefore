"""Proof of novelty against the OEIS (the On-Line Encyclopedia of Integer Sequences).

The OEIS is free. We query it for a sequence an invention actually produced:

  * matches found  -> the invention is KNOWN; we record which A-numbers it is, so the
                      UI can say "this is A000045, the Fibonacci numbers."
  * no match       -> the invention is, as far as this public catalog knows, a FIRST.
                      We store the receipt (the exact query + the catalog's answer).
  * no network     -> UNCHECKED. We never pretend. "Not found in OEIS" is a claim with
                      evidence; "never existed" is not a claim we are allowed to make.

Results are cached in SQLite, so the same sequence is only ever asked once, and so the
whole thing keeps working offline on everything it has already seen.
"""

import json
import threading
import time
import urllib.parse
import urllib.request

_UA = "therefore-invention-engine/0.1 (local research; +https://oeis.org)"
_MIN_INTERVAL = 1.1          # be polite: >=1.1s between live requests
_lock = threading.Lock()
_last_call = [0.0]


def _query_terms(seq):
    """Pick the terms to search on: trim to a window OEIS handles well."""
    terms = seq[:14]
    # OEIS wants at least a few terms with some variety
    return terms


def _live_lookup(qstr):
    """Hit OEIS. Returns parsed JSON (list or None) or raises on network error."""
    with _lock:
        wait = _MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
    url = "https://oeis.org/search?q=" + urllib.parse.quote(qstr) + "&fmt=json"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_sequence(store, seq, tick):
    """Return a dict: {status, catalog, matches, receipt, seq}.

    status in {'first','known','unchecked','trivial'}.
    """
    distinct = len(set(seq))
    if len(seq) < 6 or distinct < 5:
        # too short / too plain to make any novelty claim responsibly
        return {"status": "trivial", "catalog": "OEIS", "matches": [],
                "receipt": {"reason": "sequence too short or too few distinct values"},
                "seq": seq}

    terms = _query_terms(seq)
    qstr = ",".join(str(x) for x in terms)
    url = "https://oeis.org/search?q=" + urllib.parse.quote(qstr) + "&fmt=json"

    cached = store.oeis_cached(qstr)
    if cached is not None:
        data = json.loads(cached)
    else:
        try:
            data = _live_lookup(qstr)
        except Exception as e:
            return {"status": "unchecked", "catalog": "OEIS", "matches": [],
                    "receipt": {"query": url, "error": repr(e),
                                "note": "offline or rate-limited; not a novelty claim"},
                    "seq": terms}
        store.oeis_store(qstr, json.dumps(data), time.time())

    if not data:  # OEIS returns null/[] for no results
        return {"status": "first", "catalog": "OEIS", "matches": [],
                "receipt": {"query": url, "result_count": 0,
                            "checked_terms": terms,
                            "note": "not found in OEIS as of lookup"},
                "seq": terms}

    matches = []
    for item in data[:5]:
        matches.append({"id": "A%06d" % item.get("number", 0),
                        "name": (item.get("name") or "")[:140]})
    return {"status": "known", "catalog": "OEIS", "matches": matches,
            "receipt": {"query": url, "result_count": len(data)},
            "seq": terms}
