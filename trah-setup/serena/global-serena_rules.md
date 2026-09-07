# Serena Working Rules — moved into the system prompt

The rules themselves are no longer here. They live in the global brief
`~/.claude/brief.md` (kit source: `claude-trah/trah-setup/fragments/trah-serena-*.md`),
section **"Serena and sequential-thinking — the working rules"**, and the wrapper
`~/.local/bin/claude` feeds that file to every session as the system prompt.

Why the move, measured 22.08.2026: this text was embedded into `initial_prompt`
of both `project.yml`, so every `activate_project` carried about 2 100 tokens.
A session activates the project after every compaction — 59 times in one
measured session, 118 000 tokens for text the model already had in front of it.
The system prompt is one copy in the cached prefix; an activation answer is a
new copy inside the transcript, re-sent on every following turn.

This file is kept as a stub so that `mem:` links do not dangle. Do not put the
rules back here: two copies drift.
