---
{
  "id": "tool-bash-prefer-dedicated",
  "route": "mod",
  "mod": {"event": "tool.describe", "tool": "Bash"},
  "why": "Bash описывает себя как способ читать и править — это инструкция в точке решения, и она прямо спорит с нашей дисциплиной",
  "note": "обе правки — замены общего куска, а не целых предложений: в исходнике два варианта этого пункта, один кончается точкой, другой двоеточием и списком. Общий якорь накрывает оба, хвост каждого остаётся своим. В режимах bypassPermissions и plan пункт не подаётся вовсе — там харнесс убирает его сам и присылает вместо него сообщение «работай через Bash», и чинится это переписыванием сообщения режима, а не здесь",
  "note_backticks": "в тексте замены НЕТ обратных кавычек, и это не стилистика. Описания инструментов лежат в бинаре внутри JS-шаблонных строк: обратная кавычка закрывает строку, и собранная копия падает с SyntaxError ещё до первого запроса. Проверено болью 26.08.2026 — сборка отбилась на `grep`. То же касается ${...}: это подстановка в шаблоне",
  "note_search": "правило о текстовом поиске живёт ЗДЕСЬ, а не в описании Grep. Инструментов `Grep` и `Glob` в этой обвязке нет вовсе: проверено ловушкой 26.08.2026 на патченой и на штатной сборке, с отложенной загрузкой и без — 59 инструментов, ни одного из двух. Значит единственный способ устроить текстовый поиск руками — `grep`/`rg`/`find` через этот инструмент, и предупреждать надо в его описании. Прежний кусок `tool-grep-compact` патчил описание, которое не отправляется никогда, и был удалён",
  "note_хук": "Приписка про хук стоит в НАЧАЛЕ второй замены, а не в конце — и это не вкус. У якоря два хвоста: в одном варианте пункта дальше идёт точка, в другом двоеточие и список. Фраза, приписанная в конец, во втором варианте оказалась бы перед двоеточием и подписала бы собой чужой список. Смысл приписки: описание говорило «избегай», а `nudge-serena.py` в режиме block просто отказывает, и модель узнавала об этом только потерянным ходом",
  "edits": [
    {
      "op": "replace",
      "anchor": "IMPORTANT: Avoid using this tool to run ",
      "count": 2,
      "with": "IMPORTANT: This is a tool of action — running programs, builds, tests, git, checking the environment. It is not a reading or an editing tool: the whole output of a read lands in the context and is re-sent on every later turn, and an in-place edit is blind, so a pattern that fired in the wrong place is exactly as silent as one that fired correctly. Avoid running "
    },
    {
      "op": "replace",
      "anchor": "Instead, use the appropriate dedicated tool as this will provide a much better experience for the user",
      "count": 2,
      "with": "A hook enforces this line rather than suggesting it: with its blocking mode on, a read or a text search of a project file through this tool is refused outright and the turn is lost. Instead, use the appropriate dedicated tool. For source files in the active project, a symbolic tool (find_symbol, replace_symbol_body) beats both this tool and a whole-file read; the plain file tools are right outside the project and for a couple of known lines. The same holds for searching: grep, rg and find through this tool are the last resort, not the first move. A question about code is answered by find_symbol or find_referencing_symbols, which return the real symbol and its real callers; search_for_pattern covers text that is not a symbol. A shell text match also collects comments, string literals and namesakes from elsewhere in the tree, does not say which function a line sits in, and every hit then has to be re-checked by eye — reach for it outside the project, or when nothing symbolic fits"
    }
  ],
  "verify": {
    "tool": "Bash",
    "marker": "This is a tool of action",
    "modes": [
      "default",
      "acceptEdits"
    ]
  },
  "было": "bash-is-action"
}
---
