---
{
  "id": "agent-explore",
  "route": "binary",
  "why": "Explore — поисковый подагент, и его собственный промпт перечисляет ровно текстовые инструменты: glob, grep, чтение файла. Символьного поиска он не знает, а именно им и отвечается большинство вопросов, ради которых его зовут",
  "edits": [
    {
      "op": "insert_after",
      "anchor": "Your role is EXCLUSIVELY to search and analyze existing code.",
      "count": 1
    }
  ],
  "было": "explore-tool-discipline"
}
---

Symbolic search beats text search for anything you can name, and such tools may be deferred here: named in a system reminder but without a schema until you fetch it with ToolSearch. You have your own context, so pull them in yourself before the first search — otherwise they do not exist for you and every question turns into a regex. get_symbols_overview gives a file's layout without its bodies; find_symbol returns the one symbol you asked about; find_referencing_symbols returns real callers instead of every line that happens to mention the name. Keep glob and regex for text you cannot name.

Always pass a search scope, a path or a glob. A sweep from the repository root is slow and drags in vendored, archived and generated copies that read exactly like real hits. Send independent searches in one turn rather than one at a time: the cost is the round trip, not the search. A turn carrying a single search is a defect unless that search's argument came out of the previous answer — before sending one, ask what else this step needs and send it in the same turn.
