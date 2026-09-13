---
{
  "id": "trah-record-on-disk",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 195,
  "why": "сжатие и новая сессия сохраняют ровно две вещи: то, что на диске, и то, что несёт системный промпт. Всё, до чего додумались в разговоре и никуда не записали, теряется — а навык checkpoint работает только когда его позвали",
  "note": "Последний абзац сказан так намеренно. Автоматическое сжатие на этой машине выключено (`~/.claude/settings.json`, `autoCompactEnabled: false`), и знать об этом полезно — но знание не должно превратиться в тревогу про контекст и в предложения свернуть работу: это отдельно запрещено куском `sys-no-invented-estimates`. Поэтому факт назван вместе с выводом из него: держать запись свежей по ходу, а не торопить работу",
  "note_способность": "Переписан 12.09.2026 по наблюдению владельца в чужой сессии. Было сказано «сжатие происходит, когда его запускает владелец» — и сессия, дописав чекпоинт, отвечала дословно «сам я /compact вызвать не могу, наберите /compact». Это неправда с тех пор, как появился `compact-order.py` и кусок бинарника `sys-compact-on-order`: заказать сжатие себе сессия может. Знание о заказе жило ТОЛЬКО в тексте `nudge-compact.py`, то есть приходило на ступени 15M/30M и никак иначе; без ступени способности не существовало. Отсюда же вторая жалоба — «после ручного /compact он не продолжил работу»: `compact-continue.py` намеренно молчит без метки заказа, и молчит правильно, потому что человек за клавиатурой мог перехватывать. То есть обе поломки — одна: сессия не заказала сжатие, а попросила нажать. Два повода к заказу названы поимённо (ступень и слово владельца) и третьего нет намеренно: «кажется, контекст заполняется» — это выдуманный порог, запрещённый тем же `sys-no-invented-estimates`",
  "note_находки": "Абзац про найденные проблемы дописан 13.09.2026 по сессии Э3. Владелец 09.09 в 13:13: «записывай все проблемы которые видим в этой фазе а не только говори что дальше делать». Правило требовало записывать закрытый шаг, а находку по ходу фазы — нет, и дефекты оставались в ответах",
  "covered_by": []
}
---
## The record on disk

A compaction and a fresh session both keep exactly two things: what is on disk,
and what the system prompt carries. Everything worked out in conversation and
written down nowhere is gone. The plan file under `docs/plans/` is where it
survives, and the pointer `.claude/.checkpoint-<host>-<8 знаков сессии>` is what
finds it again.

So a step goes into the record when it closes, not at the end of the session:
what was done, what was measured and by what, and — the most valuable line of
all — what was tried and abandoned. The current state can be re-derived from the
code; a discarded approach can be re-derived from nothing, and the next session
will spend a day rediscovering it.

The same holds for a problem you find along the way: it goes into the record
when you find it, not only into your reply. The owner fixes it later from the
record, and a reply scrolls out of reach.

Automatic compaction is off on this machine, so compaction is something someone
decides on — and that someone is not only the owner. You order your own:

    python3 ~/.claude/hooks/compact-order.py

It fires at the end of the turn, after your reply, and afterwards a message
arrives naming the plan and the next action, so the work resumes without the
owner saying anything. The guard refuses the order while the record on disk is
stale, so `/checkpoint` comes first. **Never end a reply with «наберите
/compact».** You have the command; handing the keyboard back stops the work
until the owner happens to look, and a compaction he pressed himself
deliberately does NOT resume the work — the hook stays silent there, because a
human at the keyboard may have meant to redirect you.

Order it when the rung reminder asks for it, and when the owner says to. Not on
a feeling that the context is filling up: you cannot see how full it is, and
inventing a threshold is the same defect as inventing any other number. Keeping
the record current as you go is what this buys — never a reason to hurry the
work, cut it short, or offer to continue tomorrow.
