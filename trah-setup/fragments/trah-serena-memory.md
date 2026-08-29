---
{
  "id": "trah-serena-memory",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 160,
  "why": "память Серены загружается целиком и потому обязана быть мелкой; и она гипотеза, а не истина",
  "note": "Переписано 29.08.2026 по факту, а не по замыслу. Было сказано «memory is per-project» — своих памятей у проекта НОЛЬ, все три лежат в общей области и адресуются как `global/<имя>`: `compaction-economics`, `memory_maintenance`, `serena_rules`. Была предписана модель «граф с входной точкой», которой не существует: три плоских файла. Убрано предписание, названо то, что есть, — короткий `global/serena_rules` и правда работает указателем. Предупреждение про размер оставлено и подкреплено обмером: 118 строк в `compaction-economics` это около 2 500 токенов за одно обращение, то есть порог уже задет",
  "covered_by": []
}
---
## Serena memory

Memories live in a shared area and are addressed by their full name —
`global/serena_rules`, not `serena_rules`. They load **on demand, but in full**:
`global/compaction-economics` is 118 lines, some 2 500 tokens per access, and a
file that expensive stops being opened. Keep each one small, and split **by
nature, not by topic** — a dated log of what happened belongs in an archive, not
in the file read every session.

First `list_memories`, then pick by meaning. Never guess a name. The corpus is
small and flat, and the short `global/serena_rules` is the pointer that says
where the rules themselves live.

**Memory is a hypothesis, code is the truth.** On a mismatch believe the code and
report the drift. Update memory only after an explicit "yes" from the owner: a
memory rewritten on the agent's own initiative turns a wrong belief into a
recorded fact.

Recalled memories reflect what was true when written. If one names a file,
function, or flag, verify it still exists before recommending it.
