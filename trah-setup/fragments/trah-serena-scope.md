---
{
  "id": "trah-serena-scope",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 120,
  "why": "поиск без области сканирует весь корень и обычно возвращает мусор",
  "covered_by": []
}
---
## A search scope is mandatory

`find_symbol`, `search_for_pattern`, `find_file` and `replace_in_files` take a
path as an **optional** argument — without it the whole project root is scanned.
The values `""`, `"."` and `"*"` do not count as a scope.

Several branches at once is **not** a reason to fall back to `grep`:
`paths_include_glob` understands brace expansion, so a pattern like
`{cmd,internal,tools}/**` covers three of them in one call — and the glob alone
satisfies the scope requirement, `relative_path` may be omitted entirely.

A trap inside the same argument, and it costs a wrong conclusion rather than an
error. `paths_include_glob` is matched against the path **from the project
root**, not from `relative_path`. Ask with `relative_path="trah-setup"` and
`paths_include_glob="{bin,hooks}/*"` together and nothing matches at all: the
answer comes back empty and looks exactly like an honest absence. Measured
29.08.2026 on this repository — the empty result was briefly taken as proof that
the string did not exist anywhere. Either give the glob the whole path from the
root (`trah-setup/{bin,hooks}/*`) or drop `relative_path` and let the glob be
the scope on its own.

This one is not advice. `guard-serena-scope.py` sits on every Serena call as a
PreToolUse hook and answers a scopeless call with exit 2: the call does not
happen, and you learn about it as a tool error. Which field counts as a scope
depends on the tool — `relative_path` for `find_symbol`, either `relative_path`
or `paths_include_glob` for `search_for_pattern`.
