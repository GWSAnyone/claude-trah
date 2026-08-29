---
name: start
description: |
  Loading a project's context before work — from code and configs, not from memory.
  Use when the user says «подгрузи контекст <X>», «загрузи <X>», «начинаем в <X>»,
  «старт <X>», «контекст <X>», «/start <X>», or just «/start» / «старт» with no
  target (then ask which project, in one short phrase).
  The skill scans the directory and finds the projects and the memory itself — no
  list is hardcoded anywhere, a new project is picked up without editing the
  skill. It checks memory against the real code, shows the divergences and ALWAYS
  stops with the question of what we are doing, instead of diving in blind.
argument-hint: "[проект]"
---

# /start — loading a project's context

Assemble an accurate picture before work begins. Everything asserted comes from
code and configs; memory is a hypothesis to be checked. Answer in **Russian**.

## Scanned before the run

Working directory: !`pwd`

Projects:

!`for d in */; do n="${d%/}"; case "$n" in _*) continue;; esac; m=""; [ -f "$d/CLAUDE.md" ] && m="${m}md "; [ -f "$d/go.mod" ] && m="${m}go "; [ -f "$d/package.json" ] && m="${m}node "; [ -d "$d/docs" ] && m="${m}docs "; [ -d "$d/data" ] && m="${m}data "; g=$(git -C "$d" log -1 --format=%cd --date=short 2>/dev/null); printf '%-18s %-22s %s\n' "$n" "$m" "$g"; done`

Memory:

!`find .serena/memories -name '*.md' 2>/dev/null | sed 's|.*memories/||; s|\.md$||' | sort | tr '\n' ' '; echo`

Plans in progress:

!`find . -maxdepth 3 -path '*/docs/plans/*.md' -not -path './_*' -newermt '-45 days' 2>/dev/null | sort | tail -8; echo`

## 1. Identify the project

Match against **the table above**, not against your memory. Fuzzy and in Russian:
an abbreviation or a fragment is enough. Nothing named — ask «Какой проект
подгружаем?». Several matched — show them and ask. On disk but missing from the
atlas in the root `CLAUDE.md` — say so, the atlas has fallen behind.

## 2. Memory

`list_memories`, then `read_memory` on the fitting ones. **Names need not match
directory names** — choose by meaning, never guess a name. No memory at all is
normal for a new project: say «памяти нет, строю картину по коду», invent nothing.

## 3. Map of the code — one batch, one turn

- `get_symbols_overview` on each entry point (`cmd/*/main.go` or this stack's
  equivalent) and on the packages under `internal/` / `src/`
- the manifest — `go.mod`, `package.json`, `pyproject.toml`

`get_symbols_overview` takes a **file**, not a directory; a specific function is
`find_symbol` with `include_body=true`. Read whole files only when not code.

## 4. The real values

Config as it is on disk, not as the defaults declare: the small JSON/YAML/TOML at
the top of the data or config directory, plus one file from each subdirectory to
see the shape. Name anomalies out loud — orphaned atomic writes (`.tmp-*`), sync
conflicts, debug snapshots. Numbers are **exact constants from the code**.

## 5. The active plan

A fresh file under `docs/plans/` (or wherever this repo keeps them) — read its
«Где я сейчас», count the checkboxes. It outranks memory: that is where work
stopped.

## 6. Memory against reality

Check every substantial claim against what was read. Divergences hide in:
declared defaults vs the live config; the dependency list; routes vs actual
handler registration; intervals, limits, batch sizes; units of measure at the
boundaries of external APIs. Collect them into a separate block.

## 7. Summary, then STOP

Compact, in Russian, only what matters. Do not recite memory back.

1. **Загружено** — project, which memory, how many configs
2. **Стек** — language version, 3–5 key dependencies
3. **Архитектура** — packages, one line per role
4. **Состояние** — exact values from the configs
5. **Расхождения память ↔ код** — separate block, only if any
6. **Где остановились** — from the plan, if there is one

Then **stop and ask what we are doing.** No analysis, no proposed edits, no
diving into a subsystem on your own initiative — an obvious problem may be named
in one line, but the direction is the owner's. Divergences found — ask «Память
отстала на N пунктов. Обновить?» and update only after «да».

## Rules

1. Everything comes from the scan above. **Hardcode nothing** — no name tables,
   no paths, no dates. They rot silently.
2. No absolute paths.
3. Serena for code, `Read` for configs.
4. «Не знаю» is an acceptable answer. Inventing understanding is not.
5. No preamble — straight to step 1.
6. Do not start from `README.md` and `docs/`; they can lie. Lean on the code.
