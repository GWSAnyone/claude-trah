---
{
  "id": "trah-serena-ladder",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 110,
  "why": "лестница выбора инструмента — сердце дисциплины",
  "covered_by": []
}
---
## Tool selection ladder

Top to bottom; the first one that fits wins.

1. **You know the symbol** — `find_symbol` (`include_body=true` when the body is
   needed), `get_symbols_overview` — when you need the whole layout of a file.
2. **You are after relations** — `find_referencing_symbols` (who actually calls
   it), `find_declaration` (where it is declared), `find_implementations`.
3. **You are editing a symbol** — `replace_symbol_body`, `insert_before_symbol`,
   `insert_after_symbol`.
4. **Renaming and deletion** — `rename_symbol`, `safe_delete_symbol`.
   They are almost never called, yet they alone keep an edit consistent across
   every reference at once: a text replacement leaves behind calls you did not
   know about, and deleting "by hand" does not check whether the symbol is still
   needed by someone.
5. **An edit inside a file, not on a symbol boundary** — `replace_content` (one
   file), `replace_in_files` (the same text across many). The second has a dry
   run worth using whenever the pattern could catch something you did not mean:
   `dry_run=true` returns every prospective change as a minimal diff with an
   occurrence id, and the second call applies only the ids you picked. The
   `expected_count` guard is the cheap version — a wrong count changes nothing
   and hands you the same list.
6. **You are looking for text, not a symbol** — `search_for_pattern`. The last
   rung, not the first.

Reconnaissance by name, without reading content — `find_file`, `list_dir`.
A question about ANOTHER of the owner's projects, without leaving this session —
`list_queryable_projects`, then `query_project`: it runs a read-only Serena tool
in that project's context. Read-only is the whole of it; work in that tree still
belongs to a session started inside it.
After an edit — `get_diagnostics_for_file` on the edited file: cheaper than a build, catches a typo in
a name, a lost import, a type mismatch.

Why the ladder is ordered exactly this way: symbolic tools understand
**symbols**, while `grep` and line-by-line reading understand lines.
`find_referencing_symbols` finds the real callers; `grep` finds text matches,
including comments, string literals and namesakes from a neighbouring module.
A text answer has to be re-checked by eye, a symbolic one does not.

The saving is not marginal. On a question of the form "who calls this function",
a recursive `grep` returns hundreds of lines — most of them backups, archived
copies and namesakes — and none of them say which function the line sits in.
The symbolic answer returns the real call sites with their enclosing symbol and
boundaries, for a fraction of the tokens and with nothing left to verify by eye.
