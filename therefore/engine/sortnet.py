"""Sorting networks: a real, open discovery problem the engine can attack and win.

A sorting network is a fixed sequence of compare-and-swap operations on N wires that
sorts ANY input. Finding networks with as few comparators as possible is a genuine,
still-open research problem for larger N. Crucially, correctness is cheap and total to
verify: by the 0/1 principle, a comparator network sorts every input if and only if it
sorts every binary input, so testing all 2^N zero/one vectors proves it exactly.

The engine seeds with a network that definitely works (the bubble-sort network) and then
discovers smaller ones by removing redundant comparators and perturbing the structure,
re-verifying exhaustively at every step. Every network it keeps is provably a correct
sorting algorithm. Nothing here is asserted; it is all checked.
"""

# Best known comparator counts for small N (used only to describe how close it got).
KNOWN_OPT = {2: 1, 3: 3, 4: 5, 5: 9, 6: 12, 7: 16, 8: 19, 9: 25, 10: 29, 11: 35, 12: 39}


def bubble(n):
    """A network that is guaranteed to sort: bubble sort as comparators."""
    net = []
    for i in range(n):
        for j in range(n - 1 - i):
            net.append((j, j + 1))
    return net


def _apply(net, bits):
    a = list(bits)
    for i, j in net:
        if a[i] > a[j]:
            a[i], a[j] = a[j], a[i]
    return a


def is_valid(net, n):
    """Exhaustive proof via the 0/1 principle: sorts all 2^N binary inputs."""
    for x in range(1 << n):
        bits = [(x >> k) & 1 for k in range(n)]
        a = bits[:]
        for i, j in net:
            if a[i] > a[j]:
                a[i], a[j] = a[j], a[i]
        # check sorted (ascending)
        ok = True
        for k in range(n - 1):
            if a[k] > a[k + 1]:
                ok = False
                break
        if not ok:
            return False
    return True


def depth(net, n):
    """Parallel depth: how many layers if independent comparators run at once."""
    layer_of_wire = [0] * n
    layers = 0
    for i, j in net:
        d = max(layer_of_wire[i], layer_of_wire[j]) + 1
        layer_of_wire[i] = layer_of_wire[j] = d
        layers = max(layers, d)
    return layers


def prune(net, n):
    """Remove every comparator whose removal still leaves a valid network."""
    net = list(net)
    changed = True
    while changed:
        changed = False
        for k in range(len(net)):
            trial = net[:k] + net[k + 1:]
            if is_valid(trial, n):
                net = trial
                changed = True
                break
    return net


def improve(net, n, rng, tries=40):
    """Try to find a smaller valid network than `net`. Returns the best found."""
    best = prune(net, n)
    for _ in range(tries):
        cand = list(best)
        roll = rng.random()
        if roll < 0.5 and len(cand) > 1:
            # drop a random comparator then re-prune
            del cand[rng.randrange(len(cand))]
        elif roll < 0.8 and len(cand) > 2:
            # reorder a segment (can expose new redundancies)
            a = rng.randrange(len(cand)); b = rng.randrange(len(cand))
            cand[a], cand[b] = cand[b], cand[a]
        else:
            # replace a comparator with a fresh random one
            i = rng.randrange(n - 1); j = rng.randrange(i + 1, n)
            cand[rng.randrange(len(cand))] = (i, j)
        if is_valid(cand, n):
            cand = prune(cand, n)
            if len(cand) < len(best):
                best = cand
    return best
