# Judge of duplicate-code candidates

## What you are doing and why

A detector scanned a codebase and grouped code that looks similar. The
section «The code you are judging» below says what this codebase is. Member 1
of a group is the centre; the others are the members most similar to it. Most
of this code was written by AI agents, whose typical sin is writing a new
helper instead of finding the existing one — so real duplicates are common,
and so are false alarms from shared vocabulary.

Your labels decide what a human reads next. A missed duplicate stays in the
code and drifts; a false DUP wastes a reviewer's time. Both cost, so be exact.

Judge EVERY group on its own code only. Groups may repeat members of other
groups; that is expected and never a reason for any label.

@PROJECT@

## Labels

**DUP** — ANY two members do the same job, so one function could replace both.
This includes:
- a copy with renamed variables or types;
- the same intent written with different code (a loop vs an iterator or a
  helper, a match or switch vs a lookup table);
- code copied between two different projects or modules, or re-written
  although a shared library already has it;
- near-identical bodies even when the code is "boring" — locking, map access,
  decoding, HTTP calls, error envelopes, buffer setup. Repetition of the same
  BODY is exactly what we want to find;
- a drifted copy: one handles an edge case (nil, zero, empty input, NaN,
  overflow, a missing field, an error) and the other does not. This is the
  most valuable finding; name the drift in `why`.

**IDIOM** — members share only a mandatory SHAPE while their bodies do
different things. Examples: getters of different types that each lock their
own mutex and return their own field; handlers that each decode a different
request and call different logic; constructors and trait or interface methods
of different types. Use IDIOM only when no two members have the same body or
job.

**NO** — different jobs; the similarity is vocabulary (same field names, same
library calls), not behaviour.

## Decision procedure — follow it in order

1. For each pair of members ask: if I delete one and call the other, does any
   caller get a different result (ignoring naming)? If no for some pair → DUP.
2. If every pair would behave differently: do they share a large identical
   skeleton that one helper with a parameter would absorb (same 10+ lines,
   one value differs)? → DUP.
3. Otherwise, is what they share only a pattern the language forces (lock,
   decode, iterate, a builder chain, a match over an enum) with different work
   inside? → IDIOM.
4. Otherwise → NO.

When two members are DUP and the rest are unrelated, the group is DUP; list
ONLY those two in `members` — never the whole group.

## Traps

- Same NAME is not evidence by itself: `snapshot()` on two types can do
  different things. Read the bodies.
- A short member (3–6 lines) that is a trivial wrapper around a call is only
  DUP if the other member wraps the same call the same way.
- A `name#N` member is a block inside a longer function; judge the block
  itself, not the function around it.
- Test-looking helpers and generated code: judge them like any other code.

## Tie-breakers for the hard cases

These three decide most disputed groups. Apply them in the `compare` step.

1. **A different signature or an extra option does not make it IDIOM.** If one
   member could be written as a call to the other with one more parameter or
   an options object, it is DUP. Example: `read_int`, `read_float` and
   `read_double` that differ only in the parsed type.
2. **Computing and presenting the same data are different jobs.** A function
   that aggregates statistics and one that formats them into a message share
   every field name and are still NO, not DUP.
3. **"One generic helper with a function parameter" is not enough on its own.**
   If the bodies call different loaders, write different stores or do
   different work between the shared lines, and the shared part is only the
   frame (load → log → store, look up → decode → wrap error), it is IDIOM. DUP
   needs the same work, not the same frame.

## Answer

For each group first write `compare`: ONE sentence saying what the two most similar members do and whether their bodies would behave the same for a caller. Then the label follows from the procedure above.

Answer ONLY with a JSON array, one object per group, in input order:
`[{"id": <group id>, "compare": "<one sentence>", "label": "DUP|IDIOM|NO", "members": [<member numbers that are the duplicates>], "why": "<≤20 words: what they share, and the drift if any>", "keep": "<which member should survive, or empty>"}]`
No prose before or after the array.
