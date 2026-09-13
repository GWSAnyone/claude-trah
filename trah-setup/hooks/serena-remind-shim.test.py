#!/usr/bin/env python3
"""Проверка прокладки перед `serena-hooks remind`.

Главное здесь — первый случай: три подряд `mcp__serena__search_for_pattern` и
ни одного грепа. Апстрим на третьем отвечает отказом «слишком много грепа»;
прокладка обязана этот отказ снять, не сняв настоящий — на очереди из `Grep`.
"""

import json
import os
import shutil
import subprocess
import sys
import uuid

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serena-remind-shim.py")


def подать(имя: str, сессия: str, прямо: bool = False):
    """Один вызов хука. `прямо` — мимо прокладки, сразу апстриму."""
    payload = json.dumps({"session_id": сессия, "tool_name": имя, "tool_input": {}})
    команда = (["serena-hooks", "remind", "--client=claude-code"] if прямо
               else [sys.executable, HOOK])
    res = subprocess.run(команда, input=payload, capture_output=True, text=True)
    return res.returncode, res.stdout


def отказ(вывод: str) -> bool:
    """Есть ли в ответе deny — апстрим выражает его в JSON, а не кодом выхода."""
    try:
        данные = json.loads(вывод)
    except ValueError:
        return False
    решение = данные.get("hookSpecificOutput", {}).get("permissionDecision")
    return решение == "deny"


def очередь(имя: str, сколько: int = 3, прямо: bool = False) -> bool:
    """Подать `сколько` одинаковых вызовов в свежей сессии. Был ли отказ."""
    сессия = f"проба-{uuid.uuid4()}"
    было = False
    for _ in range(сколько):
        _, вывод = подать(имя, сессия, прямо)
        было = было or отказ(вывод)
    shutil.rmtree(os.path.expanduser(f"~/.serena/hook_data/{сессия}"), ignore_errors=True)
    return было


def main() -> int:
    провалов = 0

    def check(имя: str, ок: bool, подробность: str = "") -> None:
        nonlocal провалов
        if not ок:
            провалов += 1
        print(f"{'✓' if ок else '✗'} {имя}" + (f"  — {подробность}" if not ок and подробность else ""))

    есть_апстрим = shutil.which("serena-hooks") is not None

    # ── то, ради чего прокладка ──────────────────────────────────────────────
    check("три search_for_pattern подряд — отказа нет",
          not очередь("mcp__serena__search_for_pattern"))

    if есть_апстрим:
        # Без прокладки тот же ряд отказ даёт. Если этот случай однажды
        # перестанет проходить — значит апстрим починили и прокладку пора снять.
        check("апстрим на том же ряду отказывает (иначе прокладка не нужна)",
              очередь("mcp__serena__search_for_pattern", прямо=True))
    else:
        print("· апстрим не установлен — сверка с ним пропущена")

    # ── то, что прокладка ломать не имеет права ──────────────────────────────
    if есть_апстрим:
        check("очередь из Grep по-прежнему получает отказ", очередь("Grep"))
        check("символьный вызов Serena отказа не вызывает",
              not очередь("mcp__serena__find_symbol", сколько=5))

    # ── прокладка не имеет права ломать вызов ────────────────────────────────
    res = subprocess.run([sys.executable, HOOK], input="не json",
                         capture_output=True, text=True)
    check("битый ввод не ломает вызов", res.returncode == 0, res.stderr[:90])

    res = subprocess.run([sys.executable, HOOK], input="", capture_output=True, text=True)
    check("пустой ввод не ломает вызов", res.returncode == 0, res.stderr[:90])

    # Апстрим требует session_id и без него падает — прокладка обязана
    # проглотить это молча, а не уронить чужой вызов.
    res = subprocess.run([sys.executable, HOOK],
                         input=json.dumps({"tool_name": "Grep", "tool_input": {}}),
                         capture_output=True, text=True)
    check("payload без session_id не ломает вызов", res.returncode == 0, res.stderr[:90])

    # ── ворота: чужой процесс не поднимается там, где ему нечего делать ──────
    sys.path.insert(0, os.path.dirname(HOOK))
    прокладка = __import__("serena-remind-shim")

    ворота = [
        # имя инструмента, команда, зовём ли апстрим
        ("mcp__serena__find_symbol", "", True),      # символьный — сбрасывает счётчик
        ("mcp__serena__list_dir", "", True),         # у апстрима тоже символьный
        ("mcp__serena__read_memory", "", False),     # «read» в списке несимвольных
        ("mcp__serena__get_diagnostics_for_file", "", False),
        ("Grep", "", True),
        ("Read", "", False),                          # отбивает guard-read-code.py
        ("Write", "", False),
        ("Edit", "", False),
        ("ToolSearch", "", False),
        ("Task", "", False),
        ("", "", False),
        ("Bash", "grep -rn токен .", True),
        ("Bash", "rg токен", True),
        ("Bash", "cat README.md", True),
        ("Bash", "sed -n '1,20p' файл", True),
        ("Bash", "/usr/bin/grep токен файл", True),  # basename, как у апстрима
        ("Bash", "go build ./...", False),
        ("Bash", "git status --porcelain", False),
        ("Bash", "python3 tools/мерка.py", False),
        # Первое слово — не grep: апстрим разбирает только его, и мы тоже.
        ("Bash", "ls -la | grep токен", False),
    ]
    for имя, команда, ждём in ворота:
        вход = {"command": команда} if команда else {}
        итог = прокладка.upstream_can_act(имя, вход)
        подпись = f"{имя or '(пусто)'}{' + ' + команда if команда else ''}"
        check(f"ворота: {подпись} → {'зовём' if ждём else 'мимо'}",
              итог is ждём, f"вышло {итог}")

    if есть_апстрим:
        # Наблюдаемый признак: апстрим заводит свой файл счётчика. Нет файла —
        # значит процесс и не поднимался.
        def счётчик_завёлся(имя: str, команда: str, ворота_вкл: bool) -> bool:
            сессия = f"ворота-{uuid.uuid4()}"
            вход = {"command": команда} if команда else {}
            payload = json.dumps({"session_id": сессия, "tool_name": имя,
                                  "tool_input": вход})
            окр = dict(os.environ,
                       SERENA_REMIND_GATE="on" if ворота_вкл else "off")
            subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True, env=окр)
            папка = os.path.expanduser(f"~/.serena/hook_data/{сессия}")
            был = os.path.exists(os.path.join(папка, "tool_use_counter.pkl"))
            shutil.rmtree(папка, ignore_errors=True)
            return был

        check("сборка мимо апстрима: счётчик не заведён",
              not счётчик_завёлся("Bash", "go build ./...", True))
        check("без ворот та же сборка апстрим поднимает",
              счётчик_завёлся("Bash", "go build ./...", False))
        check("греп в шелле апстриму доходит",
              счётчик_завёлся("Bash", "grep -rn токен .", True))
        check("три грепа в шелле подряд по-прежнему дают отказ",
              очередь("Grep"))

    # ── разбор имени ─────────────────────────────────────────────────────────
    случаи = [
        ("mcp__serena__search_for_pattern", True),
        ("MCP__SERENA__SEARCH_FOR_PATTERN", True),
        ("mcp__serena__find_symbol", False),
        ("mcp__serena__read_memory", False),
        ("Grep", False),
        ("Read", False),
        ("mcp__other__search_for_pattern", False),
    ]
    for имя, ждём in случаи:
        check(f"разбор имени: {имя} → {'придержать' if ждём else 'пропустить'}",
              прокладка.miscounted(имя) is ждём)

    print(f"\nпровалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
