#!/usr/bin/env python3
"""Проверки гарда на ожидание внутри хода."""

import importlib.util
import io
import json
import sys
from pathlib import Path

БЛОК, ПРОХОД = 2, 0

СЛУЧАИ = [
    # --- ожидание, запущенное агентом ---
    ("sleep 600", БЛОК),
    ("sleep 0.5", БЛОК),
    ("go build ./... && sleep 300 && curl localhost:8181", БЛОК),
    ("/bin/sleep 10", БЛОК),
    ("usleep 500000", БЛОК),
    ("until curl -sf localhost:8181; do sleep 5; done", БЛОК),
    ("python3 -c 'import time; time.sleep(600)'", БЛОК),
    ("node -e 'setTimeout(() => {}, 600000)'", БЛОК),

    # --- упоминание, а не запуск ---
    ("grep -rn sleep trah-setup/hooks/", ПРОХОД),
    ("echo 'никогда не зови sleep 600'", ПРОХОД),

    # --- законная работа ---
    ("go test ./internal/...", ПРОХОД),
    ("git status --porcelain", ПРОХОД),
    ("python3 trah-setup/hooks/compact-order.test.py", ПРОХОД),
    ("systemctl --user stop buyorderbot", ПРОХОД),
]


def загрузить():
    путь = Path(__file__).resolve().parent / "guard-sleep.py"
    спец = importlib.util.spec_from_file_location("guard_sleep", str(путь))
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def main() -> int:
    гард = загрузить()
    провалов = 0
    for команда, ожидание in СЛУЧАИ:
        груз = json.dumps({"tool_name": "Bash",
                           "tool_input": {"command": команда}})
        прежний = sys.stdin
        sys.stdin = io.StringIO(груз)
        ошибки = io.StringIO()
        прежние_ошибки, sys.stderr = sys.stderr, ошибки
        try:
            код = гард.main()
        finally:
            sys.stdin, sys.stderr = прежний, прежние_ошибки
        добро = код == ожидание
        провалов += not добро
        знак = "✓" if добро else "✗"
        вид = "БЛОК " if ожидание == БЛОК else "ok   "
        print(f"{знак} {вид} {команда}")
    print(f"\nвсего: {len(СЛУЧАИ)}   провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
