---
{
  "id": "trah-serena-symbol-names",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 125,
  "why": "как называть символ и почему пустой ответ — не «нет такого». Пришло 28.08.2026 из редакции службы: раздел был только там, а работаем мы в режиме, и цену этого знания уже заплатили — тридцать вызовов в одном заходе, двадцать пустых по одной причине",
  "covered_by": []
}
---
## An empty answer is not "no such symbol"

`find_symbol` returns `[]` for a name path that does not match, and it does so
**silently** — no error, no hint that the shape of the name was wrong. That
makes a mistyped name path indistinguishable from an honest absence, and a whole
batch can go out and come back empty without a word.

Three shapes cost a batch each; know them before you write the name.

**A method is not always under its type.** In Go the language server reports
methods **flat**, at file level, not nested under the receiver. So
`tokenUsage/context` and `Proc/noteBatch` both return `[]`, while the bare
`context` and `noteBatch` return the real thing. Measured 27.08.2026 on
`tausozavr`: of thirty calls in one batch, twenty came back empty for this reason
alone. In Go, ask by the **bare method name**; do not build `Type/method`.

Other languages nest normally — `MyClass/my_method` is right for Python and
TypeScript. The rule is per-language, and the cheap way to settle it is
`get_symbols_overview` on the file: it shows the tree the server actually has.

**A leading comment is not part of the body.** `include_body=true` returns the
symbol from its signature line down. The comment block **above** it stays out —
and in a well-commented file that block is where the reasoning lives: why the
formula is this one, what was measured, on what date, against which live traffic.
`context` comes back as three lines of `func … { return … }` and looks trivial;
the paragraph explaining what counts as input is invisible.

Need it: a targeted `Read` with `offset`/`limit` over the lines just **before**
`start_line` — not the file as a block. Body boundaries are zero-based, editor
lines are one-based; that off-by-one is the same one as everywhere else.

**Overloads and name collisions are indexed.** A type and a method sharing a
name come back as two entries, `Inventory[0]` (Struct) and `Inventory[1]`
(Method). Append the index to address one of them: `Inventory[1]`.
