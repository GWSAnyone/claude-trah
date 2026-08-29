---
{
  "id": "trah-serena-not-only-code",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 115,
  "why": "самая частая отговорка — «файл не код». Она неверна: половина Серены работает с любым текстом",
  "covered_by": []
}
---
## Serena is not only about code

The symbolic half needs a language server, while the other half works with
**any** text file: markdown, JSON, YAML, configs, logs, plans.
`search_for_pattern` searches non-code files by default; `replace_content` and
`replace_in_files` edit any text.

Markdown is parsed symbolically on top of that: a heading is a symbol with
boundaries, and `replace_symbol_body` replaces a whole section, up to the next
heading's boundary, without counting lines.

"The file is not code" is not on its own a reason to fall back to the built-in
tools.
