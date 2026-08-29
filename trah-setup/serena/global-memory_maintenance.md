# Memory Maintenance

A shared convention for all ecosystems (SyncedProjects, Projects, asynchronus).
Project specifics live in that project's `mem:core`, not here.

## Discovery Model

- Core principle: progressive discovery through references, building a graph of memories.
- Initially, agents are provided with the list of all memories (names only).
- Agents should read `mem:core` as the top-level entry point (graph root).
  This memory should contain references to other memories covering major project domains.
  The referenced memories shall, in turn, contain references to even more specific memories, and so on.
  The depth of the graph shall depend on the project complexity.
- Use topics/folders to group related memories in order to make the content structure explicit.
  Folders can mirror project structure (e.g. modules like frontend/backend) or topics like debugging, architecture, etc.
- Memory references must use a `mem:` prefix inside backticks — the form is
  mem-colon-name wrapped in backticks (no example is spelled out as a reference,
  otherwise `serena memories check` counts it as dangling).
  The surrounding text should clearly indicate when to read the memory / which content to expect.
  The text should provide more precise guidance than the memory name alone.
- Memories themselves should not contain information about when to read them; this is the responsibility of the referring memory.

## Style

Dense agent notes, not prose docs. Prefer invariants, terse bullets.
Avoid obvious context, rationale, and examples unless they prevent likely mistakes.
Keep guidance durable and generalizable, not task-local.

## Add/update threshold

Add or update memories only with stable, non-obvious project conventions that avoid complex rediscovery in the future.
Do not add: quick-read facts; generic language/framework knowledge; one-off task notes; volatile line-level details; behavior likely to change soon.

## Size

A memory is loaded not at startup but on a `read_memory` call — and **in full**.
A thousand-line file costs about 25 thousand tokens per read, and people stop
opening it at all. The target is **up to 300 lines**; among Serena's maintainers
the median is about 2 KB.

Outgrown that — split by purpose, do not cut content:

```
<area>               core: what it is, layout, entry points
<area>/<topic>       a narrow slice, read for a specific reason
_archive/<what>-<date>  superseded, hidden from the listing
```

## Archive instead of deletion

Do not delete what is superseded; move it into `_archive/` and hide it:

```yaml
# .serena/project.yml
ignored_memory_patterns:
- "_archive/.*"
```

Matching goes through `fullmatch`, not by substring. Hidden memories are
unavailable to `read_memory` as well — reference them by an ordinary file path,
not with the `mem:` prefix.

## Maintenance Actions

- Renaming: `mem:` references are updated automatically by `rename_memory`.
- Reference integrity check: `serena memories check`.
- Add prefixes to bare mentions: `serena memories auto-prefix-references --dry-run`.
- Memory is a hypothesis, code is the truth. On a discrepancy trust the code and
  report the drift. Update only after an explicit "yes" from the owner.
