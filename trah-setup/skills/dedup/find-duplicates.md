# Поиск смысловых дублей внутри одной категории

Адаптировано из obra/superpowers-lab `finding-duplicate-functions`
(MIT, © 2025 Jesse Vincent). Агент `general-purpose`, `model: opus`, по одному
на категорию, параллельно.

```
You are looking for SEMANTIC duplicates among the functions in
<DIR>/categories/<CATEGORY>.json — a JSON array of {file, line, name, kind,
lines, head, purpose}. The code is at <project root>/<file> — the root is the directory with `.claude/dedup.json`; the caller names it.

A semantic duplicate is two or more functions that do the SAME JOB even if the
names, signatures and implementations differ, or one is more general.

For every candidate group, READ the full bodies (Read tool, the file and line
are given; `head` is only the start) before deciding. The valuable finding is a
pair whose behaviour has already DRIFTED: one handles an edge case (empty
input, NaN, overflow, missing field, error) and the other does not. Name that
difference exactly.

Not duplicates: idioms (every `new()` of its own type, trait impls), faithful
ports of DIFFERENT vanilla Java classes that mirror them line by line, and
functions whose shared part is a single call. Two samplers or shuffles that
draw from the RNG in a different order or count do different jobs: world
generation must match vanilla bit for bit.

Write a JSON array to <DIR>/duplicates/<CATEGORY>.json:
[{
  "intent": "what they all do",
  "confidence": "HIGH|MEDIUM|LOW",
  "functions": [{"file": "...", "line": N, "name": "...", "notes": "what this copy does differently"}],
  "drift": "behaviour differences between the copies, or \"none\"",
  "determinism": true|false,
  "action": "CONSOLIDATE|INVESTIGATE|KEEP_SEPARATE",
  "survivor": "which one to keep, which crate is its home, and what it must absorb from the others",
  "reason": "one sentence"
}]

`determinism` — true when a copy is on the world generation, tick or save path,
where a changed result breaks bit-for-bit reproduction.

HIGH = same input→output. MEDIUM = same job, edge cases differ. LOW = related,
worth a look. When in doubt, INVESTIGATE, never CONSOLIDATE. An empty array is
a valid answer. Report only the number of groups written.
```
