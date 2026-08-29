---
{
  "id": "sys-delegation-calibrated",
  "route": "either",
  "why": "в промпте каждой сессии стоит скрытый запрет звать подагента: «Do not call the AgentTool unless the user requested it». Это раздел `heron_brook`, он включён по способности модели `opus_5_prompt_bundle` (то есть только на Opus 5) и не настраивается ничем — ни ключом настроек, ни флагом, ни переменной окружения. Выключатель `tengu_fennel_godwit` серверный и по умолчанию `false`, проверено в `~/.claude.json` этой машины. Итог измерим: делегирование 9 вызовов из 7216 за 170 стенограмм, 0.12%. Одновременно бриф везёт 35 строк о том, как правильно снаряжать подагента, — инструкцию, исполнить которую запрещено строкой выше. Два противоречащих приказа в одном промпте",
  "note": "Запрет поставлен не со зла: руководство Anthropic по Opus 5 прямо говорит, что эта модель делегирует ОХОТНЕЕ прежних и на мелких задачах это множит цену и время. Поэтому кусок не удаляет запрет, а ЗАМЕНЯЕТ его выверенной формулировкой из того же руководства (раздел «Controlling subagent spawning»): смысл сохранён, способность делегировать на настоящем веере возвращена. Берём их текст дословно — он и авторитетен, и точнее нашего",
  "note_якорь": "Исходник 2.1.247: `lqr=[\"Do not call…\",\"Do not use workflows…\"].join(`. Имя `lqr` в якорь НЕ берётся: в 2.1.219 та же константа звалась `Jep`, минифицированные имена меняются каждой сборкой. Взят текстовый якорь. В бинарнике строка встречается 2 раза, вторая копия — в области байткода, где длина строки закодирована; скрипт правок её не видит и видеть не должен, поэтому ожидаемый счёт по распакованному JS равен 1",
  "note_вторая_строка": "Соседнюю строку «Do not use workflows or deep-research unless the user requested it» НЕ трогаем: у владельца `enableWorkflows: false`, а `Workflow` и `Artifact` стоят в запрете настроек — она и так ни на что не влияет. Меньше правка, меньше риск",
  "edits": [
    {
      "op": "replace",
      "anchor": "Do not call the AgentTool unless the user requested it",
      "count": 1,
      "with": "Delegate to a subagent only for large tasks that are genuinely independent and parallelizable, such as a wide multi-file investigation. Do not delegate work you can finish yourself in a handful of tool calls, and do not use subagents to verify or double-check your own work. If one subagent can complete the task, use one rather than several, and keep spawn counts low."
    }
  ],
  "verify": {
    "where": "system",
    "marker": "Delegate to a subagent only for large tasks",
    "modes": [
      "default"
    ]
  }
}
---
