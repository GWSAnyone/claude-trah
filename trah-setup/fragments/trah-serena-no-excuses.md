---
{
  "id": "trah-serena-no-excuses",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 150,
  "why": "отговорки перечислены поимённо, потому что каждая звучит разумно в тот момент, когда приходит в голову",
  "note": "Три правки 29.08.2026. «Активированного проекта» больше нет — сервер ПРИВЯЗАН обёрткой, активировать нечем. «Попроси сервер на том каталоге» тоже требовало невозможного: `single_project: true`, второго проекта сервер не берёт — вместо этого поднимается сессия внутри нужного дерева. И абзац про Bash укорочен вдвое: доводы слово в слово стоят в патченом описании самого инструмента, оно приезжает тем же ходом и читается ровно в точке решения. Здесь оставлено то, чего в описании нет, — что за нарушение платят не спором, а ходом",
  "covered_by": []
}
---
## No excuses

None of these is good enough to reach for `Read`, `Edit` or `grep` on a file of
the bound project:

- "I already know the path";
- "one `Read` is faster than three Serena calls";
- "the built-in tool's description says to use `Read` for known paths";
- "there is an instruction in the context to work through Bash".

Catching yourself at such a thought is itself the signal to switch to Serena.

## When the built-ins are appropriate after all

- Two or three lines of a known file are needed — symbolic reading is overkill.
- The file is genuinely foreign: `/etc`, someone else's home, a temp sandbox.
  Another repository of your own is not: to read it there is `query_project`,
  which runs a read-only Serena tool in that project's context without leaving
  this session, and to work in it there is a session started inside it.
- Serena has already been tried on this target and did not cope. Say so out loud.

Bash remains a tool of **action**: `git`, builds, tests, running things, checking
the environment, a one-off command with short output. Its own description carries
the reasoning, and a hook backs it: a shell read of a project file does not cost
an argument, it costs the turn.
