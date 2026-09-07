#!/usr/bin/env python3
"""PreToolUse-гард на ожидание внутри команды.

Владелец 01.09.2026: «ЗАБЛОКИРУЙ НАХУЙ СЛИПЫ ВСЕ, Я ЗАЕБАЛСЯ СИДЕТЬ ПО 10 МИНУТ
В ОЖИДАНИИ СКРИПТА СЛИП». Причина в том, чем ожидание оборачивается на его
стороне: пока команда спит, ход не кончается, терминал занят и вмешаться нельзя.
Десять минут сна в скрипте — это десять минут, которые он сидит и смотрит.

Дешёвая замена есть и она лучше по всем статьям: запустить работу фоном
(`run_in_background`) и получить вызов обратно, когда она кончится, либо
дождаться условия инструментом `Monitor`. И то и другое возвращает ход владельцу
немедленно.

Ловится ожидание, ЗАПУЩЕННОЕ АГЕНТОМ: `sleep` командой, `time.sleep` внутри
однострочника интерпретатора, busy-wait через `until … sleep`. Ожидание внутри
файла проекта (тесты зовут `time.sleep(0.4)`, чтобы дать сокету дочитать строку)
гарду не видно и запрещать его нечем: он смотрит на команду, а не на исходники.

Exit 2 = блокировка, stderr уходит модели. Exit 0 = пропустить.
"""

import json
import re
import sys

# Правила ищутся по всей строке команды: `sleep` живёт и вторым звеном конвейера
# (`foo && sleep 600`), и внутри `-c` у интерпретатора.
#
# Якорь на начало сегмента здесь не годится, а голое слово `sleep` — годится
# слишком хорошо: оно попало бы в `grep -rn sleep`, то есть в чтение. Поэтому
# перед словом требуется либо начало строки, либо оператор оболочки.
ПРАВИЛА = [
    (
        r"(?:^|[;&|]|&&|\|\||\bthen\b|\bdo\b|\belse\b)\s*(?:command\s+)?"
        r"(?:/usr/bin/|/bin/)?u?sleep\s+[\d.]",
        "sleep freezes the turn: while it waits, nothing can be answered and the\n"
        "owner sits watching the terminal. Ten minutes of sleep is ten minutes of his time.\n"
        "Run the work with run_in_background and you will be called back when it ends,\n"
        "or wait on a condition with the Monitor tool. Both give the turn back at once.",
    ),
    (
        r"\b(?:python3?|perl|ruby|node|php)\b[^\n]{0,400}?"
        r"(?:time\.sleep|asyncio\.sleep|setTimeout|Time\.sleep|usleep)\s*\(",
        "A sleep inside an interpreter one-liner is the same wait, only hidden from the shell.\n"
        "Run the work with run_in_background, or wait on a condition with the Monitor tool.",
    ),
]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    команда = str((payload.get("tool_input") or {}).get("command") or "")
    if not команда:
        return 0
    for образец, причина in ПРАВИЛА:
        if re.search(образец, команда, re.IGNORECASE):
            sys.stderr.write(f"BLOCKED (a wait inside the turn).\n\n{причина}\n")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
