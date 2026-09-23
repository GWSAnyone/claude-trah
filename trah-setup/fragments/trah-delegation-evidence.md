---
{
  "id": "trah-delegation-evidence",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 185,
  "why": "подагент без третьего пункта возвращает «проверил, всё чисто», и это неотличимо от «ничего не нашёл, потому что смотрел не туда»",
  "note": "Перенесено 23.09.2026 из куска `delegation-evidence` tausozavr",
  "covered_by": []
}
---
## Delegating: ask for evidence, not for a verdict

A subagent returns **evidence, not a conclusion**. Always require three things
of it, in the briefing:

1. what exactly it read, and what it searched with;
2. its findings, each with the file, the line and the code as it stands;
3. separately — **what it did NOT check, and why**.

An empty list of findings is a normal answer. An empty list of unchecked ground
means the list was never filled in.
