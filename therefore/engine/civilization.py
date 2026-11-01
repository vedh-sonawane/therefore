"""A civilization: an isolated world with its own seed, its own laws (op costs),
its own taste, and its own script. It owns a library of inventions and keeps an
in-memory registry so the VM can resolve calls between them.
"""

import random

from ..vm.ops import LAWS_DEFAULT
from . import lexicon, taste
from .invention import Invention


class Civilization:
    def __init__(self, row):
        import json
        self.id = row["id"]
        self.name = row["name"]
        self.glyph = row["glyph"]
        self.seed = row["seed"]
        self.laws = json.loads(row["laws_json"])
        self.taste = json.loads(row["taste_json"])
        lex = json.loads(row["lexicon_json"])
        self.script = tuple(lex["script"])          # (name, start, count)
        self.era = row["era"]
        self.registry = {}        # inv_id -> Invention (all statuses, so calls resolve)
        self.ordinal = 0          # how many inventions this civ has produced

    # -- registry ------------------------------------------------------------
    def register(self, inv):
        self.registry[inv.id] = inv
        self.ordinal = max(self.ordinal, inv.id)

    def callables(self):
        """Ids of alive, total number inventions - the parts spark/combine build on."""
        return [i.id for i in self.registry.values()
                if i.status == "alive" and i.total and i.domain == "number"]

    def alive_total(self):
        """Alive, total number inventions (the number-domain working set)."""
        return [i for i in self.registry.values()
                if i.status == "alive" and i.total and i.domain == "number"]

    # -- naming --------------------------------------------------------------
    def new_symbol(self):
        return lexicon.make_symbol(self.script, len(self.registry))

    def rng_for_tick(self, tick):
        return random.Random((self.seed * 2654435761 + tick * 40503) & 0xFFFFFFFF)


def create_civilization(store, name, idx, tick, rng):
    """Mint a fresh civilization with its own laws/taste/script, persist it."""
    # laws: start from default, perturb a few op costs so cost-landscapes differ
    laws = dict(LAWS_DEFAULT)
    for op in rng.sample(list(laws.keys()), k=min(4, len(laws))):
        laws[op] = max(1, laws[op] + rng.choice([-1, 1, 2, 3]))
    tst = taste.default_taste(rng)
    script = lexicon.pick_script(idx)
    glyph = lexicon.civ_emblem(idx)
    seed = rng.randint(1, 2_000_000_000)
    lex = {"script": list(script)}
    civ_id = store.insert_civ(name, glyph, seed, laws, tst, lex, tick)
    row = {
        "id": civ_id, "name": name, "glyph": glyph, "seed": seed,
        "laws_json": _j(laws), "taste_json": _j(tst), "lexicon_json": _j(lex),
        "era": 0, "created_tick": tick, "status": "alive",
    }
    return Civilization(row)


def _j(x):
    import json
    return json.dumps(x)
