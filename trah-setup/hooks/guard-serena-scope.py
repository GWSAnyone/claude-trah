#!/usr/bin/env python3
"""PreToolUse-гард области поиска Serena.

Часть инструментов Serena принимает путь как НЕОБЯЗАТЕЛЬНЫЙ параметр и при его
отсутствии сканирует весь проект. В корне из полутора десятков крупных сервисов
это бесполезно долго и почти всегда возвращает мусор.

Гард требует явно указать область. Exit 2 = блокировка.
"""

import json
import os
import re
import sys

# tool -> список полей, из которых достаточно ОДНОГО непустого
SCOPE_FIELDS = {
    "find_symbol": ["relative_path"],
    "search_for_pattern": ["relative_path", "paths_include_glob"],
    "replace_in_files": ["relative_path", "paths_include_glob"],
    "find_file": ["relative_path"],
    "replace_content": ["relative_path"],
}

# Значения, которые формально непустые, но означают «весь проект»
WHOLE_PROJECT = {"", ".", "./", "/", "*", "**", "**/*"}

HINT = (
    "Name the scope explicitly: a project directory (`DmTrading`, say), a\n"
    "sub-directory (`DmTrading/internal/decision`) or a particular file.\n"
    "Do not know which project the symbol is in — narrow it down first: `find_file`\n"
    "by file name, or `search_for_pattern` with `paths_include_glob`.\n"
    "\n"
    "Several places at once is not a reason to fall back to `grep`:\n"
    "`paths_include_glob` understands brace expansion, so\n"
    "`{workspace-setup,tools,.serena}/**` covers three branches in ONE call — and\n"
    "the glob alone counts as a scope, `relative_path` may be omitted entirely."
)


def is_scoped(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple)):
        return any(is_scoped(v) for v in value)
    text = str(value).strip()
    return bool(text) and text not in WHOLE_PROJECT


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    match = re.match(r"^mcp__serena__(.+)$", tool_name)
    if not match:
        return 0

    short = match.group(1)
    fields = SCOPE_FIELDS.get(short)
    if not fields:
        return 0

    tool_input = payload.get("tool_input") or {}
    if any(is_scoped(tool_input.get(f)) for f in fields):
        return 0

    # Корень называем по `cwd` вызова, а не строкой в тексте. До 30.08.2026 здесь
    # стояло «the whole SyncedProjects root», и отказ, пришедший в сессии
    # tausozavr, учил неверному факту о том, что именно просканирует Serena.
    корень = os.path.basename(str(payload.get("cwd") or "").rstrip("/")) or "project"

    which = " or ".join(f"`{f}`" for f in fields)
    sys.stderr.write(
        f"BLOCKED: `{short}` was called with no search scope.\n\n"
        f"Without {which} Serena scans the whole {корень} root — that is slow "
        f"and the result is almost always useless.\n\n"
        f"{HINT}"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
