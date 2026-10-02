---
{
  "id": "sys-delivering-work-at-full-scope",
  "route": "mod",
  "mod": {"event": "prompt.compose"},
  "why": "точка соединения с таусозавром. Он ставит задачу профилем, в котором прописано, что считается выполненным, — а штатный текст определяет готовность только собственным ощущением «сделано полностью». Два определения готовности в одном прогоне это конфликт, и разрешаться он должен в пользу явно поставленных критериев",
  "note": "ЗАМЕТКА ОПРОВЕРГНУТА 12.09.2026, оставлена как урок. Здесь стояло: «остальное семейство doing-tasks править не понадобилось: „не добавляй возможностей сверх задачи“, „три похожие строки лучше преждевременной абстракции“ — это дословно наши принципы. Совпадающее не трогаем». Это было верно для раздела `# Doing tasks`, и перестало быть верным, когда Anthropic заменила его на `# Delivering work` — тот самый, в который встаёт этот кусок. Указания не переписали, они просто перестали приходить, и заметка про совпадение продолжала объяснять, почему их не надо трогать. Возвращает их `sys-doing-tasks-code-quality`. Урок общий: заметка «у них уже так же» описывает ЧУЖОЙ текст на дату чтения и обязана перепроверяться при каждом переезде на новую версию",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "Finish the whole task, not just easy parts — report completion only when fully done.",
      "count": 1
    }
  ],
  "verify": {
    "where": "system",
    "marker": "those criteria define completion",
    "modes": [
      "default"
    ]
  },
  "было": "explicit-acceptance-criteria"
}
---
 When the task arrives with explicit acceptance criteria — a specification, a checklist, a profile stating what counts as done — those criteria define completion, and your own sense that the work looks finished does not override them. Go through them one by one before reporting: name the ones you met, name the ones you did not, and treat an unmet criterion as unfinished work rather than as a caveat at the end. Where no such criteria came with the task, the standard above applies and the requested scope is the deliverable.
