---
{
  "id": "sys-harness-instructions",
  "route": "either",
  "why": "строка блока Harness делает конечной точкой встроенные файловые инструменты: «предпочитай их командам оболочки». Для нас это середина лестницы, а не вершина — над ними стоит символьный слой. Строка приезжает в КАЖДУЮ сессию главного потока и читается как последнее слово о выборе инструмента",
  "note": "здесь же — весь мандат на батчинг, и здесь он не случайно. Отдельный внутренний блок `System Prompt: Parallel tool call note` выглядит более прицельным местом, но в промпт этой обвязки он не попадает вовсе: проба 26.08.2026 не нашла в системном промпте ни одной его фразы. Строка блока Harness, наоборот, приезжает в КАЖДУЮ сессию главного потока и доставка её проверена пробой. Число 32 названо явно, потому что оно не выводится ниоткуда: в CLI зашито `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY ?? 10`, и потолок поднимает запускающая сторона — служба и обёртка в режиме trah",
  "note_число": "Число 32 зашито в бинарь, а берётся из ЗАПУСКАЮЩЕЙ стороны, и это осознанное расхождение. Сессия мимо обёртки получит бинарь, обещающий 32 при живом потолке 10 — но последствие безобидное: лишние вызовы встают в очередь, ошибки не бывает. Свести в один источник значило бы собирать текст куска на лету из той же переменной, что ставит обёртка; цена больше пользы",
  "note_одиночка": "Строка про одиночный вызов добавлена 29.08.2026 по замеру поведения, а не по вкусу: правило «шли независимое вместе» стояло в брифе с самого начала, а сессии слали по два-три вызова в пачке при потолке 32. Общее указание проигрывает привычному ритму «вызвал — прочитал — вызвал», потому что не даёт признака, по которому нарушение видно в момент нарушения. Признак назван: пачка из одного вызова, чей довод не взят из прошлого ответа, — брак. Порядок построения широкой пачки живёт в брифе, в разделе про пачки: здесь для него нет места",
  "note_якорь": "Из якоря 28.08.2026 убран ведущий `\" - \"`: маркер списка апстрим меняет свободно, а сама фраза узнаваема и без него. Замена укорочена вдвое по той же дате — доводы про батчи слово в слово стоят в брифе, а бриф доезжает в ту же системную область (проверено пробой). Здесь оставлено то, чего в брифе нет: символьный слой как верхняя ступень и число 32",
  "edits": [
    {
      "op": "replace",
      "anchor": "Prefer the dedicated file/search tools over shell commands when one fits. Independent tool calls can run in parallel in one response.",
      "count": 1,
      "with": "Prefer the dedicated file/search tools over shell commands when one fits; and where a symbolic code layer is available (find_symbol, find_referencing_symbols, replace_symbol_body), prefer that over both — it answers with the symbol you asked about instead of every line that happens to mention the name, and it edits on boundaries the language server knows rather than on a text match. Up to 32 independent tool calls run concurrently in one response, and the cost is the round trip, not the call: plan the whole step before acting, then fire all of it at once — reconnaissance together, writes together, speculative calls included. Only calls whose arguments come from a previous answer are serialized, so a response carrying a single call is a defect unless that call is one of those; before sending a lone call, ask what else this step needs and send it in the same response."
    }
  ],
  "verify": {
    "where": "system",
    "marker": "where a symbolic code layer is available",
    "modes": [
      "default"
    ]
  },
  "было": "harness-symbolic-layer"
}
---
