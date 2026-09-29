# Global rules — in the system prompt

Who you are, commit discipline and destructive git commands, output language, this
machine's traps, Serena discipline — all of it is fed to the session by the
**system prompt**, through the wrapper (`claude` → `~/.local/claude-wrapper/claude.cmd`
on Windows, `~/.local/bin/claude` elsewhere). The source it is assembled from:
`~/.claude/brief.md`, built from `trah-setup/fragments/` of the kit named in
`~/.claude/trah-kit-path`.

**If you are reading this and the rules are not in context — open
`~/.claude/brief.md` first thing, before any work.** That means the wrapper did
not fire, and then EVERY rule is missing, not just some.

**A subagent does not open `brief.md`.** It is the main session's brief, with
the main session's persona and answer format. A subagent's rules are
`~/.claude/agent-brief.md`, which the kit appends to its system prompt. If the
section «Brief for a subagent» is missing from your context, open that file
instead.
