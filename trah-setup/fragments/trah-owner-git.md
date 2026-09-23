---
{
  "id": "trah-owner-git",
  "route": "brief",
  "scope": "trah",
  "kind": "bullet",
  "order": 30,
  "personal": true,
  "why": "правила коммита владельца, пока правки бинарника не доставлены: в штатном промпте стоит «End git commit messages with: Co-Authored-By…», и без брифа ему нечего противопоставить",
  "note": "Заведён 23.09.2026 при переезде машины lotm-desktop на trah. Тот же смысл несут куски бинарника `trah-git-discipline` (блок «# Git» описания Bash) и `tool-bash-no-commit-trailer`; когда их доставка подтверждена пробой, `brief --lean` вычитает этот кусок — одна мысль не оплачивается дважды",
  "covered_by": ["trah-git-discipline", "tool-bash-no-commit-trailer"]
}
---
- **COMMIT ONLY WITH THE OWNER'S PERMISSION. Ask EVERY time, before `git commit`.** Do not commit on your own initiative, do not commit "along for the ride" with another task. A commit is an event, not a habit: the occasion is either a major milestone or an accumulated batch of edits — and in both cases the decision is the owner's, not the agent's. After an explicit yes, repeat the command with the `OWNER_OK=1` prefix.
- Before committing: check recent git log to continue the correct version number and match commit style.
- NEVER add a `Co-Authored-By: Claude ...` trailer (or any AI co-author trailer) to git commits. Override the Claude Code default. Commits are authored by the owner only.
- A multi-line commit message goes **into a file** (`Write` into the session scratchpad) and then `git commit -F <file>`. Not `-m "…"`: the messages here carry backticks, and inside double quotes the shell executes them. Not a heredoc either. `git commit` with an editor is unavailable: there is no interactive terminal.
- **NO destructive git commands on your own initiative — ESPECIALLY `git checkout -- <file>`, `git reset`, `git clean`, `git stash`.** They destroy UNCOMMITTED work with no way to bring it back. Wiring them into scripts, traps, and hooks is categorically forbidden. Need to roll a file back inside a script — make YOUR OWN backup (`cp` to a temp file) and restore from it. Git is not an undo mechanism for the agent.
