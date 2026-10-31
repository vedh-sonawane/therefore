"""Genome helpers: constructors, structural analysis, (de)serialisation.

A genome is just nested lists, so JSON is its storage format verbatim.
"""

import json
from .ops import INT, BOOL


# ---- constructors (readability only; a genome is still plain lists) --------
def const(value, t=INT):
    return ["const", t, value]


def param(i):
    return ["param", i]


def prim(name, *args):
    return ["prim", name, *args]


def iff(cond, then, otherwise):
    return ["prim", "if", cond, then, otherwise]


def selfcall(*args):
    return ["self", *args]


def call(inv_id, *args):
    return ["call", inv_id, *args]


# ---- analysis --------------------------------------------------------------
def walk(node):
    """Yield every node in the tree, pre-order."""
    yield node
    tag = node[0]
    if tag in ("prim",):
        for a in node[2:]:
            yield from walk(a)
    elif tag == "self":
        for a in node[1:]:
            yield from walk(a)
    elif tag == "call":
        for a in node[2:]:
            yield from walk(a)
    # const / param are leaves


def referenced_ids(node):
    """Invention ids this genome calls - i.e. the parts it is built from."""
    out = set()
    for n in walk(node):
        if n[0] == "call":
            out.add(n[1])
    return out


def uses_self(node):
    return any(n[0] == "self" for n in walk(node))


def size(node):
    """Total node count - a rough structural-complexity measure."""
    return sum(1 for _ in walk(node))


def depth(node):
    tag = node[0]
    if tag == "prim":
        kids = node[2:]
    elif tag == "self":
        kids = node[1:]
    elif tag == "call":
        kids = node[2:]
    else:
        return 1
    return 1 + (max((depth(k) for k in kids), default=0))


def dumps(node):
    return json.dumps(node, separators=(",", ":"))


def loads(s):
    return json.loads(s)
