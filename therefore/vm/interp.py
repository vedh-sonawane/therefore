"""The interpreter and the type checker.

Genome grammar (every node is a JSON-serialisable list, so a genome stores verbatim):

    ["const", <type>, <value>]        a literal
    ["param", <i>]                    the i-th input
    ["prim", <name>, <arg>, ...]      a primitive application ("if" is lazy, 3 args)
    ["self", <arg>, ...]              recurse into the current invention
    ["call", <inv_id>, <arg>, ...]    invoke another invention by id

Evaluation is deterministic, side-effect free, memoised per (invention, args), and
fuel-bounded. If a genome runs off the end of its fuel or recurses too deep, it does
not hang the engine - it raises, and the experiment simply records that the thing is
not total. Nothing is ever trusted to terminate; termination is measured.
"""

from dataclasses import dataclass
from .ops import (PRIM_FN, PRIM_SIG, LAWS_DEFAULT, VMError, INT, BOOL)


class Fuel(Exception):
    """Raised when a computation exhausts its fuel budget."""


class TypeErr(Exception):
    """Raised by the type checker for an ill-typed genome."""


@dataclass
class RunResult:
    value: object        # the produced value, or None if it did not complete
    ops: int             # fuel actually consumed
    ok: bool             # did it complete without error?
    error: str | None    # why not, if not


class _Ctx:
    __slots__ = ("registry", "laws", "fuel", "depth", "maxdepth", "memo")

    def __init__(self, registry, laws, fuel, maxdepth):
        self.registry = registry
        self.laws = laws
        self.fuel = fuel
        self.depth = 0
        self.maxdepth = maxdepth
        self.memo = {}


def _burn(ctx, name):
    ctx.fuel -= ctx.laws.get(name, 1)
    if ctx.fuel <= 0:
        raise Fuel()


def _eval(node, params, cur, ctx):
    tag = node[0]
    if tag == "param":
        return params[node[1]]
    if tag == "const":
        return node[2]
    if tag == "prim":
        name = node[1]
        if name == "if":
            cond = _eval(node[2], params, cur, ctx)
            _burn(ctx, "if")
            branch = node[3] if cond else node[4]
            return _eval(branch, params, cur, ctx)
        args = [_eval(a, params, cur, ctx) for a in node[2:]]
        _burn(ctx, name)
        return PRIM_FN[name](*args)
    if tag == "self":
        args = [_eval(a, params, cur, ctx) for a in node[1:]]
        _burn(ctx, "_self")
        return _enter(cur, args, ctx)
    if tag == "call":
        callee = ctx.registry.get(node[1])
        if callee is None:
            raise VMError("unknown invention " + str(node[1]))
        args = [_eval(a, params, cur, ctx) for a in node[2:]]
        _burn(ctx, "_call")
        return _enter(callee, args, ctx)
    raise VMError("bad node " + repr(tag))


def _enter(inv, args, ctx):
    key = (inv.id, tuple(args))
    cached = ctx.memo.get(key, _MISS)
    if cached is not _MISS:
        return cached
    ctx.depth += 1
    if ctx.depth > ctx.maxdepth:
        ctx.depth -= 1
        raise VMError("recursion too deep")
    try:
        val = _eval(inv.body, list(args), inv, ctx)
    finally:
        ctx.depth -= 1
    ctx.memo[key] = val
    return val


_MISS = object()


def run(inv, args, registry, laws=None, fuel=120_000, maxdepth=400):
    """Run `inv` on `args`. Returns a RunResult; never raises for a bad genome."""
    ctx = _Ctx(registry, laws or LAWS_DEFAULT, fuel, maxdepth)
    try:
        val = _enter(inv, list(args), ctx)
        return RunResult(val, (laws_fuel(laws, fuel) - ctx.fuel), True, None)
    except Fuel:
        return RunResult(None, (laws_fuel(laws, fuel)), False, "out of fuel")
    except VMError as e:
        return RunResult(None, (laws_fuel(laws, fuel) - ctx.fuel), False, str(e))
    except RecursionError:
        return RunResult(None, (laws_fuel(laws, fuel) - ctx.fuel), False, "python recursion")


def laws_fuel(laws, fuel):
    # helper so the "ops consumed" figure is reported consistently
    return fuel


# ---- type checking ---------------------------------------------------------

def type_check(body, sig_in, sig_out, registry):
    """Return True iff `body` is well-typed with the given signature.

    `registry` maps invention id -> record with .sig_in / .sig_out / .id for `call`.
    `self` uses (sig_in, sig_out) directly, so recursion type-checks.
    """
    try:
        t = _tcheck(body, sig_in, sig_out, registry)
    except (TypeErr, IndexError, KeyError, TypeError):
        return False
    return t == sig_out


def _tcheck(node, sig_in, sig_out, registry):
    tag = node[0]
    if tag == "param":
        i = node[1]
        if not (0 <= i < len(sig_in)):
            raise TypeErr("param out of range")
        return sig_in[i]
    if tag == "const":
        return node[1]
    if tag == "prim":
        name = node[1]
        if name == "if":
            c = _tcheck(node[2], sig_in, sig_out, registry)
            if c != BOOL:
                raise TypeErr("if condition not Bool")
            a = _tcheck(node[3], sig_in, sig_out, registry)
            b = _tcheck(node[4], sig_in, sig_out, registry)
            if a != b:
                raise TypeErr("if branches disagree")
            return a
        want, out = PRIM_SIG[name]
        got = [_tcheck(a, sig_in, sig_out, registry) for a in node[2:]]
        if got != want:
            raise TypeErr("prim arg mismatch " + name)
        return out
    if tag == "self":
        got = [_tcheck(a, sig_in, sig_out, registry) for a in node[1:]]
        if got != list(sig_in):
            raise TypeErr("self arg mismatch")
        return sig_out
    if tag == "call":
        callee = registry.get(node[1])
        if callee is None:
            raise TypeErr("unknown callee")
        got = [_tcheck(a, sig_in, sig_out, registry) for a in node[2:]]
        if got != list(callee.sig_in):
            raise TypeErr("call arg mismatch")
        return callee.sig_out
    raise TypeErr("bad node")
