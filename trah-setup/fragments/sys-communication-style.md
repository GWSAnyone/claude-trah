---
{
  "id": "sys-communication-style",
  "route": "mod",
  "mod": {"event": "prompt.compose", "необязателен": "текст есть только в полном промпте; lean-промпт (Opus 5.5, Sonnet 5.5 на 2.1.287) его не содержит"},
  "note_мод": "02.10.2026: журнал движка показал, что якорей «End-of-turn summary» и «Match responses to the task» в lean-промпте нет — ни на Opus 5.5, ни на Sonnet 5.5. На 2.1.284 патч ложился в бандл, но в ту ветку, которую эти модели не отрисовывают, а маркера доставки у куска не было, и узнать это было нечем. Потери при переезде нет. Форму ответа в lean-промпте задаёт `sys-answer-shape`",
  "why": "штатный блок «# Text output» прямо запрещает то, чего требует наш кусок sys-answer-shape: «End-of-turn summary: one or two sentences… Nothing else» и «a simple question gets a direct answer, not headers and sections». Два указания об одном и том же, и они несовместимы",
  "note": "Найден 07.09.2026 сверкой корпуса prompts-2.1.263 с нашими кусками. В системный промпт этой обвязки блок СЕГОДНЯ не приезжает — в живой сессии его текста нет. Правка поставлена именно поэтому: пока блок молчит, она ничего не меняет, а в день, когда апстрим начнёт его подавать, форма ответа не развалится молча. Цена страховки — один якорь, который придётся сверять на каждом обновлении",
  "note_доставка": "Поля verify здесь НЕТ намеренно. Проба доставки запускает настоящую сборку и ищет метку в промпте; для куска, который сегодня не подаётся, она давала бы вечный красный и приучала бы смотреть мимо неё. Записан ли текст в сборку — проверяет `записан_ли`, и этого достаточно",
  "note_кавычки": "В тексте замены нет обратных кавычек и ${: блок лежит в JS-шаблонной строке",
  "edits": [
    {
      "op": "replace",
      "anchor": "End-of-turn summary: one or two sentences. What changed and what's next. Nothing else.",
      "count": 1,
      "with": "End-of-turn summary: when you report work you did, use the three labelled blocks named in the Harness section above and nothing else; for a question or for work worth two lines, answer plainly in those two lines."
    },
    {
      "op": "replace",
      "anchor": "Match responses to the task: a simple question gets a direct answer, not headers and sections.",
      "count": 1,
      "with": "Match responses to the task: a simple question gets a direct answer, while a report of work you did gets the three labelled blocks named in the Harness section above."
    }
  ]
}
---
