#!/usr/bin/env python3
"""Прокладка перед `serena-hooks remind`: не даёт считать инструменты Serena грепом.

Апстримовый хук (`serena/hooks.py`, `PreToolUseRemindAboutSymbolicToolsHook`)
считает вызов грепом по подстроке в имени инструмента:

    is_grep_call() -> self._tool_name == "grep" or "search_for_pattern" in self._tool_name

Имя приходит в нижнем регистре и целиком, вместе с приставкой MCP, поэтому под
это правило попадает `mcp__serena__search_for_pattern` — собственный инструмент
Serena. Одновременно тот же вызов не засчитывается символьным: в списке
несимвольных подстрок стоит «pattern», и `is_serena_symbolic_tool()` возвращает
ложь, то есть счётчик не сбрасывается.

Итог, воспроизводимый ровно тремя вызовами подряд и без единого грепа:

    Too many consecutive grep calls without using symbolic tools.

Порог — три, и наш уклад велит подавать независимые вызовы одним ходом, так что
пачка из трёх поисков по образцу — обычное дело, а не крайность. Отключить хук
у апстрима нечем: ни флага, ни настройки порогов (`serena-hooks remind --help`).

Что делает прокладка: вызовы Serena, которые апстрим посчитал бы грепом или
чтением, до него просто не доходят — счётчик не растёт. Не сбрасывается тоже, и
это намеренно: сброс дал бы поиску по образцу право маскировать настоящую
очередь из `Read`, ради которой хук и стоит.

ВОРОТА (29.08). Прокладка сидит на пустом сопоставителе, то есть срабатывает на
КАЖДОМ вызове инструмента, а стоит она 79 мс — впятеро дороже любого другого
нашего хука. Из них 70 мс это чужой процесс: `serena-hooks` поднимает свой
питон со своими импортами.

Замер по исходнику апстрима (`ToolUseCounter.update`) показал, что платить за
это в большинстве случаев не за что. Счётчик двигается ровно на трёх видах
вызовов:

  * символьный инструмент Serena — сбрасывает счётчик;
  * греп: инструмент `Grep`, `search_for_pattern` или `Bash` с grep/rg/ag/ack;
  * чтение файла: `Read`, `*read_file*` или `Bash` с cat/head/tail/sed/less/bat.

На `Write`, `Edit`, `ToolSearch`, `Task`, `WebFetch`, `Bash(go test)` и всём
прочем `update()` не делает НИЧЕГО. Поэтому такие вызовы до апстрима больше не
доходят.

Что при этом теряется, честно: у апстрима есть запасная ветка, где отказ
выдаётся на постороннем вызове, если порог уже был перебран РАНЬШЕ. Внутри одной
сессии она недостижима — порог всегда съедается тем же вызовом, который его
перебрал, и счётчики тут же сбрасываются. Ветка живёт для состояния, поднятого
из чужого pickle; её собственный комментарий так и называет это: «stale state».

Выключатель: SERENA_REMIND_GATE=off — тогда апстрим зовётся на каждый вызов, как
было до ворот.
"""

import json
import os
import shutil
import subprocess
import sys

# Подстроки, по которым апстрим относит вызов Serena к грепу или чтению
# (`is_grep_call`, `is_read_call` в ветке claude-code). Держим их здесь списком,
# чтобы при обновлении Serena было видно, что именно сверять.
_MISCOUNTED = ("search_for_pattern", "read_file")

_PREFIX = "mcp__serena__"
_UPSTREAM = ("serena-hooks", "remind", "--client=claude-code")
_TIMEOUT = 12

# Ниже — три набора апстрима, списанные с `serena/hooks.py` дословно. Меняются
# они редко, а сверять их при обновлении Serena проще по одному месту.
# `_NON_SYMBOLIC_SERENA_TOOL_NAME_SUBSTRINGS`:
_NON_SYMBOLIC = (
    "pattern", "read", "diagnostics", "memory", "onboarding", "config",
    "list_file", "find_file", "shell", "dashboard", "restart_language_server",
)
# `_GREP_SHELL_COMMANDS`:
_GREP_SHELL = frozenset(
    ("grep", "rg", "ag", "ack", "fgrep", "egrep", "search_for_pattern"))
# `_READ_SHELL_COMMANDS`:
_READ_SHELL = frozenset(
    ("cat", "head", "tail", "sed", "less", "more", "bat", "get-content", "gc"))


def miscounted(tool_name: str) -> bool:
    """Посчитал бы апстрим этот вызов Serena грепом или чтением."""
    name = tool_name.lower().strip()
    if not name.startswith(_PREFIX):
        return False
    return any(substring in name for substring in _MISCOUNTED)


def symbolic(tool_name: str) -> bool:
    """Символьный инструмент Serena — единственное, что сбрасывает счётчик."""
    name = tool_name.lower().strip()
    return "serena" in name and not any(s in name for s in _NON_SYMBOLIC)


def command_name(tool_input) -> str:
    """Первое слово команды, как его берёт апстрим: basename в нижнем регистре."""
    if not isinstance(tool_input, dict):
        return ""
    команда = str(tool_input.get("cmd") or tool_input.get("command") or "").strip()
    if not команда:
        return ""
    return os.path.basename(команда.split(maxsplit=1)[0]).lower()


def upstream_can_act(tool_name: str, tool_input) -> bool:
    """Может ли апстрим хоть что-то сделать с этим вызовом.

    Ложь — значит `ToolUseCounter.update()` не тронет ни один счётчик, и звать
    чужой процесс не за чем.
    """
    name = tool_name.lower().strip()
    if not name:
        return False
    if "serena" in name:
        return symbolic(name)
    # Встроенный Read сюда больше не пускается. В сессии Э3 (08–13.09.2026)
    # счётчик апстрима 38 раз ответил на Read ошибкой — ход потрачен, а Read шёл
    # дальше, поведение не менялось. Крупное чтение кода теперь отбивает
    # guard-read-code.py, узко и с выходом повтором.
    if name == "grep" or "read_file" in name:
        return True
    первое = command_name(tool_input)
    return bool(первое) and (первое in _GREP_SHELL or первое in _READ_SHELL)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw, strict=False)
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    tool = str(payload.get("tool_name") or payload.get("toolName") or "")
    if miscounted(tool):
        return 0

    ворота = (os.environ.get("SERENA_REMIND_GATE") or "on").strip().lower() != "off"
    if ворота and not upstream_can_act(
            tool, payload.get("tool_input") or payload.get("toolInput")):
        return 0

    upstream = shutil.which(_UPSTREAM[0])
    if upstream is None:
        return 0
    try:
        res = subprocess.run([upstream, *_UPSTREAM[1:]], input=raw,
                             capture_output=True, text=True, timeout=_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return 0
    if res.returncode != 0:
        # Апстрим упал на своём же вводе — так он делает, например, когда в
        # payload нет `session_id`. Это его беда, а не повод ронять чужой вызов:
        # его код возврата и его traceback дальше не идут.
        return 0
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    # Свой отказ апстрим выражает JSON'ом в stdout, а не кодом возврата, так что
    # ноль здесь ничего не теряет.
    return 0


if __name__ == "__main__":
    sys.exit(main())
