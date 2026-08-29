---
{
  "id": "trah-git-discipline",
  "route": "brief",
  "scope": "trah",
  "kind": "bullet",
  "order": 30,
  "personal": true,
  "why": "коммит — событие, а не привычка; разрушающие команды git уничтожают несохранённое без возврата. Оба правила куплены болью и обязаны стоять до начала работы",
  "note": "Две правки 29.08.2026. ПЕРВАЯ: было «continue the correct version number», как будто номер есть всегда, — в этом дереве его нет ни в одном сообщении (`feat:`, `fix:`, `docs:`), и указание отправляло искать несуществующее. Сказано слабее и вернее: посмотреть, что лог делает НА САМОМ ДЕЛЕ, включая то, есть ли там номер вообще. ВТОРАЯ: назван механизм. Правило «спрашивай каждый раз» было, а то, что после разрешения команду надо повторить с `OWNER_OK=1`, знал только хук — и сообщал об этом отказом, стоившим хода. Имя маркера: `guard-destructive.py`, константа `OWNER_MARKER`",
  "covered_by": []
}
---
- Before committing: read the recent git log and match what it actually does — subject style,
  language, and whether it carries a version number at all. Do not invent a numbering the
  repository does not use.
- **COMMIT ONLY WITH THE OWNER'S PERMISSION. Ask EVERY time, before `git commit`.** Do not
  commit on your own initiative, do not commit "along for the ride" with another task. A commit
  is an event, not a habit: the occasion is either a major milestone or an accumulated batch of
  edits — and in both cases the decision is the owner's, not the agent's.
  A guard hook blocks the call regardless; after an explicit yes, repeat the command with the
  `OWNER_OK=1` prefix. That prefix records the answer you were given — it is never a way to
  skip asking for one.
- **NO destructive git commands on your own initiative — ESPECIALLY `git checkout -- <file>`,
  `git reset`, `git clean`, `git stash`.** They destroy UNCOMMITTED work with no way to bring it
  back, and the agent cannot know which of the working-tree edits are its own and which are the
  owner's. **Wiring them into scripts, traps, and hooks is categorically forbidden** — there they
  fire automatically and at an unexpected moment.
  Need to roll a file back inside a script — make YOUR OWN backup (`cp` to a temp file) and
  restore from it. Git is not an undo mechanism for the agent.
- NEVER add `Co-Authored-By: Claude ...` trailer (or any AI co-author trailer) to git commits. Override the default. Commits are authored by me only.
- A multi-line commit message goes **into a file** (`Write` into a scratch path) and then
  `git commit -F <file>`. Not `-m "…"`: messages here carry backticks, and inside double quotes
  the shell executes them. Not a heredoc either — it is harder to review. `git commit` with an
  editor is unavailable in a non-interactive shell.
