"""The Invention: the atomic unit. It keeps its whole identity forever -
its genome, its ancestry (parents), its parts (inventions it calls), its
measured behaviour, its economic balance, its novelty standing.
"""

import hashlib
from dataclasses import dataclass, field

from ..vm import genome as g


@dataclass
class Invention:
    id: int
    civ_id: int
    name: str
    symbol: str
    sig_in: tuple
    sig_out: str
    body: list
    parents: list = field(default_factory=list)
    parts: list = field(default_factory=list)
    origin: str = "spark"
    created_tick: int = 0
    status: str = "alive"
    wealth: float = 0.0
    uses: int = 0
    behavior_hash: str = ""
    prefix: list = field(default_factory=list)
    total: bool = False
    score: float = 0.0
    novelty: str = "pending"

    # ---- VM protocol: the interpreter only needs id/body/sig_in/sig_out ----

    def to_row(self):
        import json
        return {
            "civ_id": self.civ_id, "name": self.name, "symbol": self.symbol,
            "sig_in_json": json.dumps(list(self.sig_in)), "sig_out": self.sig_out,
            "body_json": g.dumps(self.body),
            "parents_json": json.dumps(self.parents),
            "parts_json": json.dumps(self.parts),
            "origin": self.origin, "created_tick": self.created_tick,
            "status": self.status, "wealth": self.wealth, "uses": self.uses,
            "behavior_hash": self.behavior_hash,
            "prefix_json": json.dumps(self.prefix),
            "total": int(self.total), "score": self.score, "novelty": self.novelty,
        }

    @staticmethod
    def from_row(r):
        import json
        return Invention(
            id=r["id"], civ_id=r["civ_id"], name=r["name"], symbol=r["symbol"],
            sig_in=tuple(json.loads(r["sig_in_json"])), sig_out=r["sig_out"],
            body=g.loads(r["body_json"]),
            parents=json.loads(r["parents_json"] or "[]"),
            parts=json.loads(r["parts_json"] or "[]"),
            origin=r["origin"], created_tick=r["created_tick"], status=r["status"],
            wealth=r["wealth"], uses=r["uses"], behavior_hash=r["behavior_hash"],
            prefix=json.loads(r["prefix_json"] or "[]"),
            total=bool(r["total"]), score=r["score"], novelty=r["novelty"])


def behavior_hash(prefix, total):
    """A stable fingerprint of what an invention *does*, used for dedup within a
    civilization and for detecting convergent invention across civilizations."""
    import json
    payload = json.dumps([prefix, bool(total)], separators=(",", ":"))
    return hashlib.sha1(payload.encode()).hexdigest()[:16]
