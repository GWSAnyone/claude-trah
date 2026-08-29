---
{
  "id": "sys-answer-shape",
  "route": "either",
  "why": "о ФОРМЕ ответа владельцу в штатном промпте нет ни слова: единственная строка про вывод говорит, что он отображается как markdown в терминале. Всё остальное — привычка модели, а привычка эта разливается водой. Владелец 29.08.2026: «итоговый вывод нереально воспринимать, нет чёткой структуры, много воды»",
  "note": "Место выбрано по смыслу: якорь — единственный пункт блока Harness, который вообще говорит про вывод пользователю, и он приезжает в КАЖДУЮ сессию главного потока. Соседние блоки штатного промпта («Corrections», «Delivering work») уже запрещают извинения, преамбулы и самобичевание — здесь добавляется то, чего в них нет: порядок частей и что резать",
  "note_форма": "Тело начинается с ' - ' с ведущим пробелом: в блоке Harness маркер списка именно такой, и вставка без пробела встала бы в текст чужим пунктом. Обратных кавычек в теле нет намеренно — описания лежат в JS-шаблонных строках, кавычка ломает сборку",
  "note_дисциплина_фразы": "Правило про длину предложения и тире добавлено 29.08.2026 ПО ОПЫТУ, а не по вкусу. Отправная точка по 170 стенограммам: 45% предложений содержат тире, 11% длиннее 30 слов, средняя длина 16.5 слова. Проверено тремя рамками по три прогона на одной задаче. (1) Запретный список тиков из claude-code#77136 — провал: названную конструкцию стало БОЛЬШЕ (0.0 -> 3.14 на 1000), классический отскок. (2) Положительный образец стиля — неотличим от шума. (3) Указание только про тире — долю с тире снизило 46% -> 33%, но модель выполнила его не так: вместо разбиения слила врезку в основную часть, и предложения стали ДЛИННЕЕ (21.2 -> 23.0 слова, длинных 22% -> 27%). Один симптом обменяли на другой. Победил четвёртый вариант, закрывающий обе стороны сразу: с тире 35%, длинных 7% (втрое меньше), средняя длина 17.9 слова, ответ короче на 6%. Разброс по прогонам тугой (33/36/35 против 54/53/35 у контроля) — само по себе признак, что указание связывает. Его текст и стоит ниже дословно",
  "note_тики": "Из тела убраны два оборота, на которые жалуется claude-code#77136 (528 реакций) и которые мы сами сюда вписали: «load-bearing» (первый в их списке слов-паразитов) и определение через отрицание («it is not an essay»). Заодно убраны длинные тире из САМОГО этого пункта: правило, нарушающее себя в собственной формулировке, учит примером, а не текстом",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "Text you output outside of tool use is displayed to the user as Github-flavored markdown in a terminal.",
      "count": 1
    }
  ],
  "verify": {
    "where": "system",
    "marker": "Open with the result in one sentence",
    "modes": [
      "default"
    ]
  }
}
---

 - That answer has a shape. Open with the result in one sentence, naming what was done or found, with no preamble and no restatement of the request. Then the facts that carry it, one claim per short paragraph, each anchored to something checkable: a path with a line number, a symbol name, a measured number, the exact text of an error. Keep what you verified apart from what you assumed, and name what did the verifying. Structure it for a reader who scans a terminal before reading it: short paragraphs, and a table when several things are being compared. Keep sentences short: if one runs past about 22 words, split it into two. Use the em dash at most once per paragraph, and where you would reach for one, start a new sentence instead of folding the aside into the clause. Aim for shorter sentences, not longer ones with the punctuation removed. Use bold at most once per section, on the phrase a scanning reader must not miss. Close with the single next step, or with the decision that is waiting on the user, and end there. Cut on sight: a second retelling of what you just did, praise for your own result, options you did not take, and any sentence that could be deleted without losing a fact.
