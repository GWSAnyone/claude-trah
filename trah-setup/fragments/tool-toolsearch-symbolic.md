---
{
  "id": "tool-toolsearch-symbolic",
  "route": "mod",
  "mod": {"event": "tool.describe", "tool": "ToolSearch"},
  "why": "самая широкая точка из всех, что у нас есть. Описание `ToolSearch` читается ровно в тот миг, когда агент решает, какие инструменты у него вообще есть, — и доезжает до КАЖДОГО типа агента, включая те, чьи собственные промпты мы не патчим (Plan, senior-reviewer, statusline-setup и любой заведённый позже). Символьный слой у всех у них отложен, и без подсказки первый же вопрос про код уходит в текстовый поиск",
  "note": "Куски `agent-explore` и `agent-general-purpose` говорят то же самое, но только двум типам агентов. Здесь та же мысль ставится в общий канал: тип агента может быть заведён завтра файлом в `.claude/agents/`, и его промпт мы не увидим вовсе, а `ToolSearch` он получит",
  "note_якорь": "Взята первая строка описания. По счёту в 2.1.247 она встречается дважды, из них одна копия — область байткода bun, скрипту правок не видная; сборка подтвердила единственное видимое совпадение",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "Fetches full schema definitions for deferred tools so they can be called.",
      "count": 1
    }
  ],
  "verify": {
    "tool": "ToolSearch",
    "marker": "The symbolic code layer lives behind this tool",
    "modes": [
      "default"
    ]
  }
}
---

The symbolic code layer lives behind this tool and is the reason to call it early. A question about code — what a function does, who calls it, where a type is declared — is answered by find_symbol, find_referencing_symbols and find_declaration, and an edit on a function or class boundary by replace_symbol_body; none of them exist for you until their schemas are fetched, so a session that has not fetched them turns every such question into a regular expression over text. Fetch them before the first file operation, not after a text search has already answered badly.
