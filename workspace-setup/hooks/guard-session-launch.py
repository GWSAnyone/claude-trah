#!/usr/bin/env python3
"""PreToolUse-гард: новую сессию Claude Code поднимают только через `launch`.

Сессия, запущенная изнутри агентской, наследует её окружение целиком —
`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, сокет обмена
сообщениями, а у Таусика ещё и `TAUSIK_ROLE`. Последствия видны не сразу
и не тому, кто запускал:

    ⚠ Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker

Такая сессия не пишет транскрипт, не появляется в реестре `claude agents`,
и потому невидима для `state` и нечитаема для `peek`. А унаследованный
`TAUSIK_ROLE` запрещает ей писать код — ровно то, ради чего её подняли.

`launch` снимает эти переменные (`cleanEnv`). Проблема в том, что знание
живёт внутри него: кто запустил `claude` мимо — наступил на грабли снова.
Проверено дважды за один вечер, второй раз — уже зная о первом.

Пропускаем: подкоманды (`agents`, `stop`, `logs`, …), одноразовый `-p`
(он не заводит живую сессию), и сам `launch`.

Exit 2 = блокировка.
"""

import json
import os
import re
import shlex
import sys

# Подкоманды, которые НЕ создают сессию: спрашивают состояние или управляют
# уже существующей.
SAFE_SUBCOMMANDS = frozenset(
    {
        "agents", "stop", "logs", "attach", "doctor", "mcp", "config",
        "plugin", "install", "update", "migrate-installer", "setup-token",
        "resume", "serve", "help",
    }
)

# Флаги, после которых команда — это разовый запрос, а не живая сессия.
ONESHOT_FLAGS = frozenset({"-p", "--print", "-h", "--help", "-v", "--version"})

# Терминалы, которые запускают команду аргументом: `ghostty -e claude …`.
# Без них гард видит `ghostty` и пропускает запуск claude внутри.
TERMINALS = frozenset({"ghostty", "kitty", "alacritty", "foot", "konsole", "xterm", "wezterm"})

_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SPLIT = re.compile(r"\|\||&&|[;\n|&]|\$\(|`|\)")


_HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _strip_heredocs(command: str) -> str:
    """Команда без тел heredoc.

    Внутри `<<'PY' … PY` лежит текст программы или документа: там могут стоять
    и слово `claude`, и бэктики, и точки с запятой. Разбирать это как команды
    значит блокировать безобидное — что гард и сделал при первой же правке
    документации, где `claude` упомянут в тексте.
    """
    lines = command.split("\n")
    out: list[str] = []
    terminator: str | None = None

    for line in lines:
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue  # тело heredoc отбрасываем целиком
        out.append(line)
        if m := _HEREDOC_START.search(line):
            terminator = m.group(2)
    return "\n".join(out)


def launches_session(tokens: list[str]) -> bool:
    """Создаёт ли команда живую сессию Claude Code."""
    if not tokens:
        return False

    # Разворачиваем обёртки: `nohup setsid ghostty -e claude …`.
    i = 0
    while i < len(tokens):
        # `TAUSIK_ROLE=1 claude …` — присваивание стоит перед командой, и
        # именно в такой форме запуск чаще всего и пишут.
        if _ENV_ASSIGN.match(tokens[i]):
            i += 1
            continue
        base = os.path.basename(tokens[i]).lower()
        if base in ("nohup", "setsid", "env", "sudo", "doas", "time", "exec", "command"):
            i += 1
            continue
        if base in TERMINALS:
            # У терминала команда идёт после `-e` / `--command` / `-c`.
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                if tokens[i] in ("-e", "--command", "-c", "--"):
                    i += 1
                    break
                i += 1
            continue
        break

    if i >= len(tokens):
        return False
    if os.path.basename(tokens[i]) != "claude":
        return False

    rest = tokens[i + 1 :]
    for token in rest:
        if token in ONESHOT_FLAGS:
            return False
        if not token.startswith("-") and token in SAFE_SUBCOMMANDS:
            return False
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command:
        return 0

    # `launch` — единственный правильный путь, его не трогаем.
    if re.search(r"(?:^|[\s;&|])launch(?:\s|$)", command):
        return 0

    # Тело heredoc — данные, а не команды. Без вырезания гард блокирует
    # безобидное: скрипт, внутри которого написано слово claude, разбирается
    # как запуск. Поймано собственным гардом при правке этого же плана.
    command = _strip_heredocs(command)

    for segment in _SPLIT.split(command):
        segment = segment.strip()
        if not segment:
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if not launches_session(tokens):
            continue

        sys.stderr.write(
            "BLOCKED: a Claude Code session is raised through `launch`.\n\n"
            "Started directly from here it inherits this session's environment: it "
            "writes no transcript («Transcript saving is off — inherited "
            "CLAUDE_CODE_CHILD_SESSION marker»), does not appear in the `claude agents` "
            "registry, and is therefore invisible to `state` and unreadable by `peek`. "
            "If Tausik is the one starting it, the new session also inherits the ban on "
            "writing code.\n\n"
            f"Command: {segment[:200]}\n\n"
            "The right way:\n"
            "  launch <plan> [--name name] [--bg] [--dry-run]\n\n"
            "Need a one-off request without a live session — `claude -p '<question>'`.\n"
            "State and control: `claude agents`, `claude stop <id>`."
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
