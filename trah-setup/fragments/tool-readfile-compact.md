---
{
  "id": "tool-readfile-compact",
  "route": "either",
  "why": "Read описывает себя как способ читать файл целиком; символьное чтение отдаёт запрошенный символ, остальное в контекст не попадает",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "- Reading a directory, a missing file, or an empty file returns an error or system reminder rather than content.",
      "count": 1
    }
  ],
  "verify": {
    "tool": "Read",
    "marker": "prefer it: it returns the symbol you asked about",
    "modes": [
      "default"
    ]
  },
  "было": "read-prefer-symbolic"
}
---

- When the file is source code in the active project and a symbolic reader is available (get_symbols_overview, find_symbol), prefer it: it returns the symbol you asked about instead of the whole file, and the rest never enters the context. This tool is the right one for a couple of known lines, for non-code files, for anything outside the project, and for images, PDFs and notebooks.
