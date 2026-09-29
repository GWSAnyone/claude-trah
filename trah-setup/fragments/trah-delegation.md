---
{
  "id": "trah-delegation",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 180,
  "why": "подагент не видел разговора и не наследует ни настроек, ни инструментов. Плохо снаряжённый — переоткрывает отброшенное и возвращает ответ не на тот вопрос, а платится дважды",
  "note": "ТРЕТИЙ приказ активировать проект, найденный 29.08.2026, — и последний. Два первых убраны из `trah-serena-intro` и `trah-serena-no-excuses` тем же днём; этот прятался в снаряжении подагента и потому пережил обе чистки. Подагент наследует ТОТ ЖЕ MCP-сервер, привязанный обёрткой к одному проекту (`single_project: true`), так что активировать ему нечем и незачем — а инструкция заставляла его тратить ход на поиск несуществующего инструмента",
  "note_сокращение": "Списки «когда делегировать» и «когда нет» убраны 29.08.2026: их работу забрал кусок `sys-delegation-calibrated`, который стоит ВЫШЕ в промпте и говорит то же самое дословной формулировкой Anthropic. Осталось ровно то, чего в нём нет: цена вопроса, довод про гигиену контекста, оговорка про доверие и — главное — как подагента снаряжать. Раздел ужат с 35 строк до 22",
  "covered_by": [
    "sys-delegation-calibrated"
  ]
}
---
## Delegation: how to brief one

The harness already says when to delegate and when not to. Two things it leaves
out, and both cost you if you miss them.

**The price.** A subagent runs its own conversation with its own context; you pay
for its whole run plus your reading of its report. That is the arithmetic behind
the harness rule, and it is also the case FOR delegating when the reading alone
would fill your context with material you will never need again. Do not delegate
anything whose answer you would have to re-derive yourself before you trusted it.

**The briefing.** Write it for a colleague who has just walked into the room: it
did not see the conversation and does not know what has already been ruled out.
Every brief states, explicitly and in the task text itself:

1. **The goal** — the question to answer or the change to make, in one sentence.
2. **What is already established** — findings, decisions, and dead ends it must
   not reopen.
3. **The boundaries** — which directories, which files, what it must not touch,
   and whether it may edit at all or only read.
4. **Who else is working next to it** — directories another agent or the owner
   is editing right now, and whether the machine is free for a build.
5. **The shape of the answer** — a list, a table, a verdict, a file and a
   digest. Say what you will do with the answer, so it knows what to leave out.

Do not spend the brief on the environment. The kit appends
`~/.claude/agent-brief.md`, followed by the directory brief, to every
subagent's system prompt. That text covers the deferred Serena tools and where
they are blind, the hooks with their exact limits, anchors
(`path` › `Symbol` — «fragment» instead of `file:line`), evidence marks, and
the git, secrets and build rules. Until 29.09.2026 your own prompt was the only
channel, and the same fifteen lines were pasted into almost every task.

**Which agent.**
- `researcher` (Sonnet): anything outside the owner's code — the web, other
  repositories, mods, fetching, cloning or decompiling sources. It writes a
  report file and returns a digest.
- `senior-reviewer` (Sonnet): a map of code already on disk, the owner's or
  foreign. The answer comes in its message.
- `implementer` (session model): a designed change in the owner's code, proven
  by the build and tests.
- `test-writer` (Sonnet): tests for a module.
- `critical-reviewer` (session model): judging finished work.
- `general-purpose`: only when none of these fits. Explore is switched off.

**Every answer is also on disk.** A hook saves each subagent's final message,
with its brief, to `.claude/agent-reports/` of the session's directory, one file
per agent, named by date, type, task and id. A summary keeps two lines of a
twenty-thousand-character map; the file keeps all of it. Put that path in the
plan next to the finding, and after a compaction open the file instead of
running the agent again.

An unbriefed subagent is not a cheap helper. It is a second full-price
conversation that has to guess what you meant.
