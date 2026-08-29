---
{
  "id": "trah-record-on-disk",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 195,
  "why": "сжатие и новая сессия сохраняют ровно две вещи: то, что на диске, и то, что несёт системный промпт. Всё, до чего додумались в разговоре и никуда не записали, теряется — а навык checkpoint работает только когда его позвали",
  "note": "Последний абзац сказан так намеренно. Автоматическое сжатие на этой машине выключено (`~/.claude/settings.json`, `autoCompactEnabled: false`), и знать об этом полезно — но знание не должно превратиться в тревогу про контекст и в предложения свернуть работу: это отдельно запрещено куском `sys-no-invented-estimates`. Поэтому факт назван вместе с выводом из него: держать запись свежей по ходу, а не торопить работу",
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

Automatic compaction is off on this machine: it happens when the owner runs it,
and the guard refuses a manual one without a fresh checkpoint. That is a reason
to keep the record current as you go — never a reason to hurry the work, cut it
short, or offer to continue tomorrow.
