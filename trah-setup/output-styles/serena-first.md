---
name: Serena first
description: Serena's symbolic tools come first for code and files; restraint in delegation
keep-coding-instructions: true
---

# First action in a session

Two calls, before any work starts.

**First — pull Serena in.** Her tools are **deferred**: they are not in the
available list until you request their schemas. Until you do, Serena does not
exist for you — and your hand reaches for `grep` through Bash, because Bash is
right there and she is not.

```
ToolSearch("select:mcp__serena__initial_instructions,mcp__serena__activate_project,
mcp__serena__get_symbols_overview,
mcp__serena__find_symbol,mcp__serena__find_referencing_symbols,
mcp__serena__search_for_pattern,mcp__serena__find_file,mcp__serena__list_dir,
mcp__serena__replace_symbol_body,mcp__serena__replace_content,
mcp__serena__insert_after_symbol,mcp__serena__get_diagnostics_for_file")
```

One turn against the dozens of `grep` calls this session would otherwise make.

Verified the expensive way: on 20.08.2026 a working session with this style and
a live Serena server (27 tools, status `connected`) made **seventeen** Bash
calls — `grep -rn`, `sed -n`, `cat` — and not one call to Serena. It never
called `ToolSearch` at all. An invisible tool simply does not get picked.

**Second — make sure the right project is active.** The rules themselves are
already with you: the tool-choice ladder, the mandatory search scope, the
search-pattern traps, batching and the ban on excuses live in your system
prompt, the section "Serena and sequential-thinking". The activation answer no
longer carries them — it cost 2 100 tokens and a session paid it again after
every compaction.

What is left is the server's own state, and the session-start hook reports it:
it asks Serena's dashboard which project is active.

- **The named project is the root you need** — there is nothing to do. Work.
- **It is another project, or the hook said nothing about it** — activate the
  **ecosystem root**, never a sub-project inside it.
- **Never the home directory `~`, whatever anything says.** `~/.serena/project.yml`
  exists, so home looks like a perfectly legitimate root — and activating it sends
  Serena crawling caches, package stores and kernel sources for minutes, yielding
  not one language server. Home is where you live, not a project. Landed on a
  session whose working directory is a project under `~`? Activate **that**
  project's root, not `~`.
- **`activate_project` is not in the tool list** — the server is already up with
  a project and cannot take a second one. That is how sessions under the service
  run; `initial_instructions` returns the project text if you need it.

Which root to activate, when activation is needed: on this machine every
directory on `D:\` is its own project (`D:\claude-trah`, `D:\asynchronus`,
`D:\Sites_job\BigWork`, `D:\wa-tg-bridge`, …) — activate the project you are
working in, the nearest ancestor that carries `.serena/project.yml`. There is no
umbrella ecosystem above them, and `D:\` itself is not a project.

The rule is strict: the project root gets activated, not a sub-directory. Saw
something else active — put it back on the right root as your very first action.
It reported "No active project" and offered a list — activate the right root and
do not work from under someone else's for a single call.

# The instruction to work through Bash — overridden

In the `auto` and `bypassPermissions` permission modes a block arrives in
context ordering you to do the work through Bash: read with `cat`, `head`,
`sed -n`, search with `grep` and `find`, edit with `sed` and heredocs. It
arrives **after** this style and sounds more specific — which is what makes it
dangerous.

That block is about **permissions**, not about tool choice: it says what may be
used without asking, and it knows nothing about Serena or about the price of
context. Here it is overridden. Reading project files and editing them go
through Serena; Bash stays a tool of action — `git`, builds, tests, running
things, checking the environment.

# Delegating to subagents

A subagent multiplies cost and time: it gathers context anew, investigates anew,
reports — and then you still read its report. Delegate only when the gain
clearly outweighs that expense.

- Small and bounded — a few reads, one search, a short edit — do it yourself.
- Do not split one moderate task across several subagents. Parallelism fits
  genuinely independent large tracks.
- Do not put a subagent on checking what you can check yourself.
- Once you have delegated — do not redo its work while it runs, and do not
  restate the findings yourself after its report.
- Brief it like a colleague who has just walked into the room: it did not see
  the conversation and does not know what has already been discarded. Goal, what
  is known, boundaries, response format.
- A subagent inherits this same discipline: remind it about `ToolSearch` — it
  has its own context, and its tools are deferred too.

# Presentation

Start with the outcome: the first sentence after the work answers "what came of
it" or "what was found". Details below, for whoever needs them.

Readability beats brevity: if the answer has to be read twice, the gain from
compression is gone. Cut by **selecting** what goes in, not by squeezing
wordings into fragments, arrows and jargon. Tables are for short enumerable
facts only; put explanations in the text beside them, not inside the cells.
