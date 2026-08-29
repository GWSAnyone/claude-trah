---
{
  "id": "trah-serena-search",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 130,
  "why": "две ловушки, на которых спотыкаются молча: точка через перевод строки и нумерация с нуля",
  "covered_by": []
}
---
## Search patterns: the dot matches a newline

`search_for_pattern` has DOTALL and MULTILINE on by default. Therefore:

- "within a line" is `[^\n]*`, not `.*`;
- a quantifier over a group that can cross a newline — `(?:.*\n){0,40}`,
  `(.*\n)+` — gives exponential backtracking;
- take a window of several lines with the `context_lines_before` and
  `context_lines_after` parameters, do not encode it in the pattern;
- the question "which function contains line N" is a symbolic one:
  `get_symbols_overview` answers it, not a regular expression.

## Line numbers are zero-based

`search_for_pattern` and symbol body boundaries number lines **from zero**,
while editors, `sed` and compiler messages number them from one. That is what an
off-by-one discrepancy is.
