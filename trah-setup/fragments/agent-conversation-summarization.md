---
{
  "id": "agent-conversation-summarization",
  "route": "binary",
  "why": "штатный промпт сжатия велит быть исчерпывающим и вставлять полные куски кода — от этого сводка распухает ровно тем, что и так лежит в файлах, а после сжатия пересылается каждым ходом",
  "note": "раздел труда с хуком PreCompact: патч говорит КАК писать (фаза анализа, стоит выше слота хука и хуку недоступна), хук говорит ЧТО и ЧТО ВЕРНО СЕЙЧАС (перечень разделов и живые факты). Перечисление «вноси ограничения, факты, провалы» отсюда убрано 27.08 — его слово в слово говорит SUMMARY_SPEC, по разделам и точнее. Проверить пробой в ловушку нельзя: сжатие случается посреди сессии. Требование писать сводку по-английски добавлено 27.08: сводку читает только модель, а кириллица стоит в разы дороже той же мысли — глобальное правило «по-русски» про вывод владельцу, не про внутренние тексты",
  "note_якорь": "Из якоря третьей правки 28.08.2026 убран ведущий `\"2. \"`: номер пункта в списке апстрим двигает свободно, и якорь падал бы от простой перестановки. Сама фраза узнаваема и без номера, а нумерация в собранном тексте остаётся апстримовой",
  "note_переезд_273": "16.09.2026, 2.1.273: счёт третьей правки 3 → 2. Апстрим не переформулировал фразу, а убрал её из одного варианта вместе с хвостом `MUST be preserved verbatim in the summary`: в 2.1.269 этих хвостов 3, в 2.1.273 — 2, а вариантов промпта (`Your task is to create a detailed summary`) столько же",
  "edits": [
    {
      "op": "replace",
      "anchor": "This summary should be thorough in capturing technical details, code patterns, and architectural decisions that would be essential for continuing development work without losing context.",
      "count": 1,
      "with": "You are writing for an agent that will resume this work with no other memory, and no human will read it. Write the summary in English whatever language the conversation was held in — the reader is a model, and other alphabets cost several times more tokens for the same text. Optimise for correct continuation per token, not for completeness. File contents do not survive compaction and do not need to be copied into the summary — paths, symbol names and their roles are what you are preserving."
    },
    {
      "op": "replace",
      "anchor": "include full code snippets where applicable",
      "count": 1,
      "with": "quote code only where the exact text is needed to continue — a path with a symbol name is usually enough, and a pasted file body is the most expensive way to say where something lives"
    },
    {
      "op": "replace",
      "anchor": "Double-check for technical accuracy and completeness, addressing each required element thoroughly.",
      "count": 2,
      "with": "Check that nothing load-bearing is missing — and then cut everything that is not load-bearing. A summary that repeats the system prompt, restates a step already finished, or narrates the conversation costs its own length again in every turn that follows."
    },
    {
      "op": "replace",
      "anchor": "Include file names and code snippets where applicable.",
      "count": 1,
      "with": "Include file names; quote code only where the exact text is what must be carried."
    }
  ],
  "было": "compaction-writes-for-an-agent"
}
---
