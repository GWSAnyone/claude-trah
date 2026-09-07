---
{
  "id": "tool-write-whole-file",
  "route": "binary",
  "why": "последний файловый инструмент, чьё описание ничего не знает о нашей дисциплине. Оно отправляет за частичной правкой к Edit — и на этом останавливается: ни про символьный редактор, ни про то, что полная перезапись отправляет текст файла целиком ещё раз",
  "note": "Якорем взята ПЕРВАЯ строка описания, хотя по смыслу вставка просилась после «For partial changes, use Edit instead». Причина техническая и проверена счётом по 2.1.247: подстрока «already Read» встречается НОЛЬ раз, «For partial changes, use » — обрывается перед подстановкой. Имена инструментов в этом описании подставляются переменными, поэтому целых предложений с ними в исходнике нет, и любой якорь с именем инструмента промахнётся молча",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "Writes a file to the local filesystem, overwriting if one exists.",
      "count": 1
    }
  ],
  "verify": {
    "tool": "Write",
    "marker": "A file that already exists is cheaper to change in place",
    "modes": [
      "default"
    ]
  }
}
---

A file that already exists is cheaper to change in place: a full rewrite sends its entire text again, and where the change covers a whole function, class or section, a symbolic editor (replace_symbol_body, insert_after_symbol) cuts on boundaries the language server knows rather than on your match. Reach for a whole-file write when the file is new, or when so much of it changes that the old text is not worth sending as context for the new.
