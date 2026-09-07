---
{
  "id": "tool-edit-single-replacement",
  "route": "binary",
  "why": "у символьного редактора границы берутся из языкового сервера, а не из совпадения текста; переименование и удаление он держит согласованными по всем ссылкам сразу",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "- \\`replace_all: true\\` replaces every occurrence instead.",
      "count": 1
    }
  ],
  "verify": {
    "tool": "Edit",
    "marker": "the boundaries come from the language server",
    "modes": [
      "default"
    ]
  },
  "было": "edit-prefer-symbolic"
}
---

- When the edit covers a whole function, class or section and a symbolic editor is available (replace_symbol_body, insert_after_symbol), prefer it: the boundaries come from the language server instead of from your match, and a rename or a deletion stays consistent across every reference at once.
