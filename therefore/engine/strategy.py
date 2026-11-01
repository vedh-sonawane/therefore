"""Game strategy: inventing optimal play for a game, verified by exhaustive playout.

The game is the subtraction game (a form of Nim): a pile of tokens, players alternate
removing 1..K, and whoever takes the last token wins. It is fully solved, so we know
exactly how many starting positions the first player can win.

A strategy is a policy: for each pile size, how many tokens to take. The engine hill-climbs
a policy by trying it, as the first player, against a perfect opponent from every starting
pile, and counting how many of the winnable positions it actually wins. When it wins all of
them it has rediscovered optimal play, and that is proven by playing out every game, not
asserted. (For K=3 the optimum is to leave a multiple of 4; the engine finds that on its own.)
"""

K = 3
MAXPILE = 28


def optimal_move(pile, k):
    for m in range(1, min(k, pile) + 1):
        if (pile - m) % (k + 1) == 0:
            return m
    return 1


def winnable_count(k=K, maxpile=MAXPILE):
    return sum(1 for p in range(1, maxpile + 1) if p % (k + 1) != 0)


def _we_win(policy, start, k):
    pile = start
    turn = 0  # 0 = us (policy), 1 = perfect opponent
    while pile > 0:
        if turn == 0:
            mv = policy[pile - 1]
        else:
            mv = optimal_move(pile, k)
        mv = max(1, min(mv, pile))
        pile -= mv
        if pile == 0:
            return turn == 0
        turn ^= 1
    return False


def wins(policy, k=K, maxpile=MAXPILE):
    return sum(1 for s in range(1, maxpile + 1) if _we_win(policy, s, k))


def random_policy(rng, k=K, maxpile=MAXPILE):
    return [rng.randint(1, min(k, p)) for p in range(1, maxpile + 1)]


def improve(policy, rng, k=K, maxpile=MAXPILE, tries=240):
    policy = list(policy)
    best = wins(policy, k, maxpile)
    for _ in range(tries):
        if best >= winnable_count(k, maxpile):
            break
        p = rng.randrange(maxpile)
        old = policy[p]
        policy[p] = rng.randint(1, min(k, p + 1))
        w = wins(policy, k, maxpile)
        if w >= best:
            best = w
        else:
            policy[p] = old
    return policy, best
