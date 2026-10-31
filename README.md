<div align="center">

# ∴ therefore

### an autonomous invention engine

*It starts with almost nothing and never stops inventing.*
*Every invention follows from the ones before it.*

</div>

---

Most "AI that creates things" asks a language model what to make and then believes the
answer. **therefore** does the opposite. It builds things that **actually run**, runs them,
measures what they do, and only then decides whether it discovered anything. A model never
gets to *claim* a result - the result has to survive execution.

It began this afternoon from a handful of arithmetic primitives. By the time you read this
it has, on its own, re-invented the **Fibonacci numbers**, the **triangular numbers**, and
the **nonnegative integers** - and independently recognised them in the OEIS - while also
producing **hundreds of integer sequences that are not in the OEIS at all**, each one filed
with a receipt.

Nobody told it what Fibonacci was. It found it, the way you'd find it: by trying things and
keeping what worked.

```
python -m therefore
```

No API keys. No paid models. No cloud. No dependencies beyond the Python standard library.
It runs on a normal computer, for free, forever, and when you close it and open it again the
world is exactly where you left it - only older.

---

## What you are looking at

The screen is not a dashboard. It is a single living organism on a dark field, and its mass,
turbulence, colour and pulse are driven by what the engine is *actually doing* right now. You
don't click through pages - you **dive into it**. Inside the organism are its civilizations.
Dive into a civilization and you find its inventions. Click an invention and you see, in full:

- the exact integer sequence it produces,
- its **measured** properties (is it prime-valued? polynomial of what degree? growing how fast?),
- its **novelty receipt** - the literal OEIS query and what came back,
- its **ancestry** and the **parts** it was built from,
- its **wealth** in the internal economy and how many times it's been reused,
- and its **genome**: the little program that *is* the invention.

Each civilization writes in its own alien script - the symbols on the cells are its own. Hover
to translate. Turn the sound on and every birth, discovery and death becomes audible; similar
inventions sound similar, because the sound is derived from how they behave. With the screen
off you can still tell what the engine is doing.

---

## How it actually works

**The substrate.** An invention is not generated source code - it's a typed expression tree in
a tiny virtual machine built for this. That one decision buys everything else:

- **Safety** - nothing arbitrary is ever executed.
- **Measurement** - every operation costs fuel, so *compute is a real, counted resource*. That
  counted cost is what the economy and the shifting laws trade in.
- **Composition** - an invention can call another invention by name, so inventions plug into
  each other and complexity has no ceiling.
- **Determinism** - no randomness, no I/O, a hard fuel cap. The same invention on the same input
  always gives the same answer. Reproducibility isn't a policy; it's structural. *(Verified: in
  testing, 60 of 60 sampled inventions reproduced their stored sequences bit-for-bit.)*

**The loop.** For each civilization, forever:

> spark an idea -> build it -> **run it on real inputs** -> verify it reproduces -> discover its
> measured properties -> check it against the OEIS -> score it by the civilization's taste ->
> release the good ones into the library -> **pay the inventions that were used as parts**

**The economy.** Every living invention pays rent to exist. It earns when something else is built
out of it. Useless inventions go bankrupt and fall dormant; foundational ones grow rich. Nobody
hardcodes what matters - the economy reveals it. *(Nothing is ever deleted - dormant inventions
are kept forever, because the engine is built to dig old failures back up when conditions change.)*

**Proof of novelty.** When an invention produces a structured sequence, therefore asks the OEIS.
If it's known, the invention is tagged with its A-number ("this is A000045, the Fibonacci numbers").
If the catalog has never seen it, it goes into the **vault of firsts** - with the receipt attached.
The wording is always honest: *"not found in OEIS,"* never *"never existed."* Offline, it simply
says *unchecked* and never pretends otherwise.

---

## The honesty guarantees

This project treats impressive-looking nonsense as failure. So:

- Every property shown traces to an experiment that was actually run.
- Every novelty claim traces to a stored catalog response you can re-open.
- Nothing is mocked, placeheld, or asserted on a model's say-so.
- The whole world is one SQLite file you can open and audit yourself.

---

## Try this

```bash
python -m therefore            # open the organism at http://localhost:8000
python -m therefore --dump     # print a text census of the world and exit
python -m therefore --civs 3   # begin (or resume) with three civilizations
```

Open `http://localhost:8000`, let the sound wake up, and watch it think. Dive into a
civilization. Find a gold cell - that's a *first*. Click it and read its receipt.

> **Note for the Claude-in-Chrome extension:** local sites need per-site permission in the
> extension before it can drive them. Any ordinary browser opens `localhost:8000` with no setup.

---

## Where this is going

What exists today is the **working miniature of the whole idea**: one civilization genuinely
inventing, testing, verifying, combining, and persisting, with that real activity driving the
organism. The architecture already has the seams for everything the full engine is meant to become:

- **parallel civilizations** that evolve incompatible formats, make *first contact*, and must
  invent a translator to trade - with **convergent invention** across sealed worlds flagged as
  evidence that a thing is fundamental;
- **exaptation** (testing inventions on problems they were never built for),
  **resurrection** of old failures when the laws change,
- **evolving taste**, **shifting laws** and **mass extinctions** between eras,
- and the **ouroboros**: the engine replacing its own parts with things it invented, and showing -
  permanently, prominently - what percentage of therefore was written by therefore.

That number, climbing, is the whole story.

<div align="center">

**∴**

</div>
