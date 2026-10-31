"""Each civilization writes in its own script.

A civilization is handed one alien alphabet (a Unicode block) and names every
invention with glyphs drawn from it. To an outsider the names are unreadable symbols;
hovering in the UI reveals the human translation. The point is to feel like you are
looking at something that was not made for you.
"""

# (name, first codepoint, count) - real Unicode blocks, each visually distinct.
SCRIPTS = [
    ("runic", 0x16A0, 75),
    ("tifinagh", 0x2D30, 70),
    ("glagolitic", 0x2C00, 94),
    ("coptic", 0x2C80, 120),
    ("georgian", 0x10A0, 80),
    ("cherokee", 0x13A0, 85),
    ("vai", 0xA500, 160),
    ("ogham", 0x1680, 29),
]

# emblem candidates for a whole civilization (mathematical signs, not pictographs)
EMBLEMS = "∴∵⊕⊗⊙⊛⊚⊘⊝⊞⊠⟐⟡⌖⍟⟁"


def pick_script(idx):
    return SCRIPTS[idx % len(SCRIPTS)]


def civ_emblem(idx):
    return EMBLEMS[idx % len(EMBLEMS)]


def make_symbol(script, n):
    """Deterministic 1-3 glyph symbol for the n-th invention of a civ."""
    name, start, count = script
    g = []
    x = n + 1
    # mix the ordinal into a short, stable glyph string
    for _ in range(1 + (n % 2) + (1 if n > 50 else 0)):
        g.append(chr(start + (x % count)))
        x = x * 1103515245 + 12345
        x = (x >> 3) % 1_000_003
    return "".join(g)
