---
{
  "id": "trah-tausik",
  "route": "brief",
  "scope": "trah",
  "kind": "section",
  "order": 200,
  "personal": true,
  "why": "проекты на D:\\ ведутся TAUSIK-ом: без этого куска сессия не знает ни фабрики, ни того, что в проекте с `.tausik/` правила принуждаются гейтами",
  "note": "Перенесено 23.09.2026 из кусков `tausik-factory` и `tausik-in-project` tausozavr. Домашний каталог с этого дня TAUSIK-проектом не является",
  "covered_by": []
}
---
## The TAUSIK factory

A portfolio of projects on `D:\` is governed by TAUSIK. The servicing layer is
`D:\tausik-ops\` — the findings log, the eval set, library updates; its
`README.md` describes it in full.

- **Source of code is the owner's fork only:** `github.com/Okianiwa/tausik-core`.
  Do not install from the upstream `Kibertum/tausik-core`: it lacks the fix
  without which edits made through Serena bypass QG-0 and the secret scanner.
- **Everything goes through the `/fab` skill** (`/fab help` lists the commands).
  Do not install TAUSIK by hand: `/fab` also writes the project into the
  registry, and a project outside the registry drops out of updates and checks.
- **Library edits are made in the hub only** — `~/.tausik-lib` — and distributed
  with `/fab sync`. An edit made in a particular project's `.tausik-lib` is
  overwritten by the next distribution.
- **Found and fixed a defect in the environment — write a line into**
  `D:\tausik-ops\ratchet-log.md`: symptom → kind of fix → the fix → the guard.
  Order of preference for a fix: **sensor > guide > rule**.

Inside a project that has `.tausik/` its rules apply, and they are enforced by
hooks and gates rather than by good intentions: no code without an active task
(QG-0 at the start, QG-2 at the close), a commit only through the gates. Run the
CLI from the project root — `.tausik/tausik` decides which project it governs by
the current directory, not by where the binary lives.
