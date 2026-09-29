---
{
  "id": "code-subagent-brief-interactive",
  "route": "binary",
  "why": "бриф подагента (`--append-subagent-system-prompt-file`, обёртка кладёт туда `~/.claude/agent-brief.md` с брифом каталога) не доезжал до подагентов в терминале. Флаг разбирается при любом запуске: общий обработчик читает файл, кладёт текст в `appendSubagentSystemPrompt` опций CLI и включает `CLAUDE_CODE_ENABLE_APPEND_SUBAGENT_PROMPT`. Но дальше текст передают только `-p` и stream-json (VS Code): в их опциях инструментов поле есть. Интерактивный режим собирает опции инструментов без него (рядом лежат только `customSystemPrompt`, `appendSystemPrompt`, `systemPromptSnapshot`), и в месте, где подагент получает бриф, опция пуста. Справка флага так и пишет: «only works with --print»",
  "note_проба": "29.09.2026, TUI на 2.1.284, флаг передан обёрткой: researcher, senior-reviewer, test-writer и implementer ответили «НЕТ» на заголовок «Brief for a subagent», а researcher перечислил заголовки своего промпта — только его собственный текст. Через `claude -p` тот же бриф доходил",
  "note_как": "Две правки. Первая: функция, которая включает переменную окружения, получает текст брифа первым аргументом — сохраняем его в `globalThis.__trahSubagentBrief`. Взято `arguments[0]`, а не имя параметра: минифицированное имя меняется от версии к версии, а якорь по тексту переменной окружения переживает переименования. Вторая: в месте, где подагент решает, приклеивать ли бриф, пустая опция заполняется из глобала через `??=`. Присваивание стоит последним звеном цепочки `&&`, поэтому прежние условия (переменная окружения, не форк, не изолированный контекст) проверяются как раньше. И оно пишет в опции контекста, откуда их копирует вложенный подагент, поэтому бриф доходит и на следующий уровень. В `-p` и stream-json опция уже заполнена, и `??=` её не трогает",
  "note_якорь": "Второй якорь содержит минифицированное имя `n` — стабильнее в этом месте ничего нет. При переезде на новую версию счётчик якорей это поймает и сборка остановится",
  "edits": [
    {
      "op": "replace",
      "anchor": "CLAUDE_CODE_ENABLE_APPEND_SUBAGENT_PROMPT=\"1\"}",
      "count": 1,
      "with": "CLAUDE_CODE_ENABLE_APPEND_SUBAGENT_PROMPT=\"1\";globalThis.__trahSubagentBrief=arguments[0]}"
    },
    {
      "op": "replace",
      "anchor": "n.options.appendSubagentSystemPrompt?n.options.appendSubagentSystemPrompt:void 0",
      "count": 1,
      "with": "(n.options.appendSubagentSystemPrompt??=globalThis.__trahSubagentBrief)?n.options.appendSubagentSystemPrompt:void 0"
    }
  ]
}
---
