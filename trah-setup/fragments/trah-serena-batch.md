---
{
  "id": "trah-serena-batch",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 140,
  "why": "платится не вызов, а круг: каждый лишний ход пересылает весь контекст заново",
  "note": "Переписано 29.08.2026 по замеру, а не по вкусу. Правило «шли независимое вместе» стояло здесь с самого начала — и сессии всё равно слали по два-три вызова при потолке 32. Причина не в силе формулировки: общее требование не даёт признака, по которому нарушение видно в момент нарушения, и проигрывает привычному ритму «вызвал — прочитал — вызвал». Добавлены две вещи. ПРИЗНАК: пачка из одного вызова — брак, если довод этого вызова не взят из прошлого ответа. ПОРЯДОК: шаг раскладывается на слои (найти — прочитать — связать — записать), и слой уезжает целиком, потому что внутри слоя зависимостей нет по построению.",
  "note_потолок": "Убрано «заполнять потолок — цель, а не исключение». Это неверная мишень: круг обмена бесплатным не станет, но ВЫВОД каждого вызова садится в контекст и пересылается дальше, так что тридцать две выгрузки тел «на всякий случай» стоят дороже сэкономленного хода. Мишень названа честно — число независимых вопросов этого слоя, — а решает, что брать спекулятивно, несимметричность цены: широкий дешёвый вызов стоит пустить по догадке, чтение с телом — только по вероятной нужде",
  "covered_by": []
}
---
## In batches, not one at a time

Serena executes calls one at a time internally, but that is its queue, not your
bill. Your bill is the **round trip**: every extra turn resends the whole
growing context. So all independent requests of one step go out in ONE turn.

**A turn carrying a single call is a defect** — unless that call's argument came
out of the previous answer. There is no other excuse for it, and it is the one
violation you can catch at the moment you commit it.

The ceiling here is 32 concurrent calls. The number to aim for is neither 32 nor
two: it is however many independent questions this layer of the step actually
has. If you can only name two, the step was not planned — it was reacted to.

## How a wide batch is built

Width comes from planning the step in layers. Each layer is one turn, and inside
a layer nothing depends on anything else:

1. **Locate** — `find_file`, `list_dir`, `get_symbols_overview`,
   `search_for_pattern` across every candidate at once. Answers are short and a
   miss costs almost nothing, so this is where width is cheapest: ask about
   everything the step might touch, not only what you are already sure of.
2. **Read** — `find_symbol` with `include_body=true` for every symbol the first
   layer named, together. Here a miss costs real tokens: include a target that
   is probably needed, not one that is merely possible.
3. **Relate** — `find_referencing_symbols`, `find_declaration`,
   `find_implementations` for everything the second layer left open, again all
   at once.
4. **Write** — every edit of the step in one turn, then
   `get_diagnostics_for_file` on what was touched.

Two layers merge into one turn whenever the second does not need the first one's
answer: files whose paths you already know are read in the locating layer, not
after it. Only a call whose argument comes from the previous answer is
serialized — that is the entire list of reasons to wait.

The asymmetry of cost decides what goes in speculatively. A cheap wide call — an
overview, a file list, a pattern search — is worth firing on a hunch. A call
that carries a body back is worth firing on a likely need. "Might be useful one
day" is not a reason to pull a body.

This is the single cheapest habit available to you, and the easiest to lose: the
natural rhythm is call, read, call, read. Resist it. When you catch yourself
issuing a lone call, ask what else this layer needs and send that with it.
