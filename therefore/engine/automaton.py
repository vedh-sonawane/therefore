"""Native cellular automata: inventing rules directly, for their own behaviour.

Unlike exaptation (which borrows a number function as a rule), here a rule is invented as
a thing in itself: a totalistic rule table that says, for each possible sum of a cell's
neighbourhood, what the cell becomes next. The engine mutates these tables and keeps the
ones whose space-time behaviour is genuinely complex or chaotic rather than dying or
settling. Behaviour is measured from the actual evolved pattern, reusing the same honest
classifier the exaptation domain uses.
"""

from . import exapt


def random_rule(states, rng):
    hi = 3 * (states - 1)
    return [rng.randrange(states) for _ in range(hi + 1)]


def mutate_rule(table, states, rng):
    t = list(table)
    i = rng.randrange(len(t))
    t[i] = rng.randrange(states)
    return t


def spacetime(table, states, width=81, steps=81):
    row = [0] * width
    row[width // 2] = states - 1
    rows = [row]
    for _ in range(steps - 1):
        nxt = [0] * width
        for i in range(width):
            s = row[(i - 1) % width] + row[i] + row[(i + 1) % width]
            nxt[i] = table[s]
        row = nxt
        rows.append(row)
    return {"states": states, "rows": rows, "table": table}


def evaluate(table, states):
    st = spacetime(table, states)
    return st, exapt.classify(st)


def rule_signature(table, states):
    return [states] + list(table)
