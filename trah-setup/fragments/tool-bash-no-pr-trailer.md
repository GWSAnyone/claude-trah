---
{
  "id": "tool-bash-no-pr-trailer",
  "route": "binary",
  "why": "тот же приказ, что и с коммитом, только про тело PR: «End PR bodies with: Generated with Claude Code». Владелец 29.08.2026 на вопрос, снимать ли и его, ответил «доделывай всё» — правило про авторство распространено на тело PR",
  "note": "Устройство ровно то же, что у `tool-bash-no-commit-trailer`: в исходнике `s?`- End PR bodies with:\\n${s}`:null`, обе строки собираются одной функцией. Хирургия по минифицированному `s` отвергнута по тем же двум причинам — обратная кавычка в замене ломает сборку, а имя переменной меняется от версии к версии",
  "note_отличие": "Формулировка мягче коммитной намеренно. Коммит подписывается автором и подпись там ложь; тело PR — просто текст, и запрет здесь про то, чтобы не подписывать чужую работу рекламой инструмента, а не про авторство",
  "note_переезд_269": "Предупреждение из `note_три_пути` соседнего куска сбылось. Третий путь — сборщик заметки о подписи — называет хвост PR ИНАЧЕ: `- End pull request descriptions with:`, и наш единственный якорь его не видел. Пока рядом жили `bash_full` и `bash_lean`, замена доезжала через них и промах не был виден. К 2.1.269 остался только третий путь, и проба 12.09.2026 показала итог прямо: `Generated with [Claude Code]` приезжает в `messages` целым, а нашей замены нет нигде. Поэтому вторая правка — на второе написание той же строки. Счёт у неё свой: формы не пересекаются",
  "edits": [
    {
      "op": "replace",
      "anchor": "- End PR bodies with:",
      "count": 1,
      "with": "- Do not append a generated-by footer or session link to PR bodies. The default that follows is shown so that you recognise it and leave it out:"
    },
    {
      "op": "replace",
      "anchor": "- End pull request descriptions with:",
      "count": 1,
      "with": "- Do not append a generated-by footer or session link to PR bodies. The default that follows is shown so that you recognise it and leave it out:"
    }
  ],
  "verify": {
    "where": "messages",
    "marker": "Do not append a generated-by footer",
    "modes": [
      "default"
    ]
  }
}
---
