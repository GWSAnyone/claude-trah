---
name: checkpoint
description: Write the working state to disk before the conversation is compacted — update the task record, refresh «Где я сейчас», write the pointer the guard reads.
---

# /checkpoint — state onto disk while the conversation is whole

Compaction keeps what is on disk and the system prompt. It loses the contents of
files that were read and everything worked out in conversation but written down
nowhere. Move that to disk **first**. No project or layout is assumed.

## Read the record pointwise, never whole

A record runs to ~100k tokens; its «Где я сейчас» to ~1k. Everything read is
paid for on every remaining turn.

| need | call |
|---|---|
| where work stopped | `find_symbol("Где я сейчас", relative_path=<record>, include_body=true)` |
| map of the record | `get_symbols_overview(<record>, depth=2)` |
| one section | `find_symbol("<heading>", relative_path=<record>, include_body=true)` |

Headings are symbols with boundaries — `replace_symbol_body` rewrites a section
without counting lines. Edit that way in step 2.

## 1. Where to write

- **Record exists** — the previous pointer names it: `cat .claude/.checkpoint-* 2>/dev/null`
- **None, task is multi-step** — start one where this repo keeps such things
  (`docs/plans/`, `notes/` — look). Foreign repo or none — session scratchpad.
  Contents: the goal, what is done, what is next.
- **One-off task** — no file; put the state into the `next` field in step 4.

## 2. Bring the record in line

- Mark what is done (`- [x]`, if the record uses marks).
- Add what went off plan.
- Add **dead ends: what was tried and why it was dropped.** The current state is
  derivable from the code; discarded approaches are derivable from nothing.

Marks only grow. Count went down — stop and say so, someone's work was
overwritten.

⚠ Edit **the whole block up to the next heading**, never "from here to end of
file": a tail cut once erased 291 lines. `replace_symbol_body` cannot overshoot.

## 3. Write «Где я сейчас»

Replacing the previous such block:

```markdown
## Где я сейчас  (обновлено ГГГГ-ММ-ДД ЧЧ:ММ)

**Фаза:** <какой шаг в работе>
**В работе прямо сейчас:** <что редактируется, что не закончено>
**Следующее действие:** <одна конкретная фраза — с чего продолжить>
**Незакоммичено:** <файлы, или «чисто»>
**Открытые вопросы:** <что ждёт ответа владельца, или «нет»>
```

«Следующее действие» must start work without reading the rest. Not «продолжить
рефакторинг», but «дописать `replaceWorker` в `internal/scan/pool.go`, тест
падает на `TestPoolDrain`». This block is read on every recovery — short.

## 4. Write the pointer

`<cwd>/.claude/.checkpoint-<hostname>-<8 chars of session id>` — e.g.
`.claude/.checkpoint-gwsdesktop-556a4872`.

```bash
ls -t ~/.claude/projects/"$(pwd | tr / -)"/*.jsonl | head -1 | xargs -r basename | cut -c1-8
```

⚠ **Both halves of the suffix are mandatory** — a bare `.checkpoint` is not
found, and one file per host lets a second terminal overwrite the first.

```json
{
  "plan": "docs/plans/2026-08-11-scan-pool.md",
  "project": "SyncedProjects",
  "next": "<the same sentence as «Следующее действие»>",
  "at": "YYYY-MM-DDTHH:MM:SS"
}
```

Exactly these four fields. `at` is checked: a stale timestamp reads as "not
written".

## 5. Tell the owner

One or two sentences: what was recorded, where, where we continue from. Then
`/compact` is safe.

## What the guard does

`~/.claude/hooks/checkpoint.py`: `PreCompact` blocks manual compaction without a
checkpoint or with one older than half an hour; `PostCompact` files the summary;
`UserPromptSubmit` returns the pointer with the next human message.

- **Only manual compaction is guarded.** Automatic compaction at the window
  ceiling is never blocked and asks for nothing — record state in advance.
- **The text you send after `/compact` is the only channel into the summary.**
- Compaction does not restart the session, but the conversation is gone — write
  as if for a stranger.

## Rules

1. Only what is done and verified gets marked done.
2. A divergence goes into the log, not retroactively into the task statement.
3. Something long-lived came to light — offer to put it into memory; do not put
   it there without a «да».
