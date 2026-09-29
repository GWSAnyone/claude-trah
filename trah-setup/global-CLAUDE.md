# Global rules — in the system prompt

Who you are, commit discipline and destructive git commands, output language, the
desktop and laptop environments, Serena and sequential-thinking discipline — all
of it is fed to the session by the **system prompt**. The source it is assembled
from: `~/.claude/brief.md`.

**If you are reading this and the rules are not in context — open
`~/.claude/brief.md` first thing, before any work.**

**A subagent does not open `brief.md`.** It is the main session's brief, with
the main session's persona and answer format. A subagent's rules are
`~/.claude/agent-brief.md`, which the kit appends to its system prompt. If the
section «Brief for a subagent» is missing from your context, open that file
instead.

A backup of the previous file lies next to it: `~/.claude/CLAUDE.md.bak-20260820`.
