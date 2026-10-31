"""Types, primitive operations, their type signatures, and their costs ("laws").

A "law table" maps each primitive name to the amount of fuel it burns. Civilizations
run under different law tables, and eras can rewrite them (a cheap op becoming
expensive is what a "shifting law" literally is). Costs are kept here as the DEFAULT
set; the engine copies and mutates them per civilization.
"""

# ---- types -----------------------------------------------------------------
# A value's type is a bare string tag. Phase 1 lives mostly in Int (we build
# integer sequences), but the tags exist so other domains slot in untouched.
INT = "Int"
BOOL = "Bool"
SEQ = "IntSeq"
GRID = "Grid"

# Absolute-value ceiling for any Int. Past this, a computation is declared to have
# overflowed and is treated as non-total. This keeps values bounded (so sequences
# stay checkable against OEIS and costs stay finite) without hand-proving anything.
MAG_CAP = 10 ** 15


class VMError(Exception):
    """A computation that is not well-defined: div by zero, overflow, bad recursion."""


def _cap(x):
    if x > MAG_CAP or x < -MAG_CAP:
        raise VMError("overflow")
    return x


def _pow(a, b):
    if b < 0:
        raise VMError("negative exponent")
    if b > 120:
        raise VMError("exponent too large")
    if a in (0, 1, -1):
        return a ** b if a != -1 else (1 if b % 2 == 0 else -1)
    # bound the magnitude before paying for a huge multiply
    if b > 60:
        raise VMError("exponent too large")
    return _cap(a ** b)


def _idiv(a, b):
    if b == 0:
        raise VMError("division by zero")
    return a // b


def _mod(a, b):
    if b == 0:
        raise VMError("modulo by zero")
    return a % b


# Each entry: name -> (fn, [arg type tags], out type tag)
# NOTE: `if` is NOT here - it is special-cased by the interpreter so its branches
# evaluate lazily (and so recursion can have a real base case).
_PRIMS = {
    "add":    (lambda a, b: _cap(a + b),        [INT, INT], INT),
    "sub":    (lambda a, b: _cap(a - b),        [INT, INT], INT),
    "mul":    (lambda a, b: _cap(a * b),        [INT, INT], INT),
    "idiv":   (_idiv,                            [INT, INT], INT),
    "mod":    (_mod,                             [INT, INT], INT),
    "pow":    (_pow,                             [INT, INT], INT),
    "min":    (lambda a, b: a if a < b else b,  [INT, INT], INT),
    "max":    (lambda a, b: a if a > b else b,  [INT, INT], INT),
    "neg":    (lambda a: _cap(-a),              [INT], INT),
    "abs":    (lambda a: abs(a),                [INT], INT),
    "inc":    (lambda a: _cap(a + 1),           [INT], INT),
    "dec":    (lambda a: _cap(a - 1),           [INT], INT),
    "square": (lambda a: _cap(a * a),           [INT], INT),
    "sign":   (lambda a: (a > 0) - (a < 0),     [INT], INT),
    "lt":     (lambda a, b: a < b,              [INT, INT], BOOL),
    "le":     (lambda a, b: a <= b,             [INT, INT], BOOL),
    "gt":     (lambda a, b: a > b,              [INT, INT], BOOL),
    "ge":     (lambda a, b: a >= b,             [INT, INT], BOOL),
    "eq":     (lambda a, b: a == b,             [INT, INT], BOOL),
    "and":    (lambda a, b: a and b,            [BOOL, BOOL], BOOL),
    "or":     (lambda a, b: a or b,             [BOOL, BOOL], BOOL),
    "not":    (lambda a: not a,                 [BOOL], BOOL),
}

# Public views
PRIM_FN = {k: v[0] for k, v in _PRIMS.items()}
PRIM_SIG = {k: (v[1], v[2]) for k, v in _PRIMS.items()}  # name -> (arg_tags, out_tag)
PRIM_SIG["if"] = (None, None)  # special-cased; handled in interp

# Default fuel cost per primitive. Cheap to compare, dearer to multiply/raise.
LAWS_DEFAULT = {name: 1 for name in _PRIMS}
LAWS_DEFAULT.update({
    "mul": 2, "idiv": 3, "mod": 3, "pow": 6, "square": 2,
    "if": 1,
    "_call": 2,   # cost of entering another invention
    "_self": 2,   # cost of a recursive self-call
})

# The handful of primitives that only make sense when a Bool is wanted.
BOOL_PRIMS = [n for n, (_, out) in PRIM_SIG.items() if out == BOOL and n != "if"]
INT_PRIMS = [n for n, (args, out) in PRIM_SIG.items()
             if out == INT and n != "if" and all(a == INT for a in (args or []))]
