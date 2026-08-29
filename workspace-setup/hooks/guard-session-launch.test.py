#!/usr/bin/env python3
"""Проверки гарда запуска сессий. Запуск: python3 guard-session-launch.test.py"""

import json
import os
import subprocess
import sys

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard-session-launch.py")

BLOCK = True
PASS = False

CASES = [
    # --- должно блокироваться: создаётся живая сессия ---
    ("claude", BLOCK),
    ("claude --name work", BLOCK),
    ("claude -n work 'сделай X'", BLOCK),
    ("claude --bg --model sonnet 'задача'", BLOCK),
    ("ghostty -e claude --name work", BLOCK),
    ("nohup setsid ghostty -e claude -n work 'задача'", BLOCK),
    ("cd /tmp && claude --name x", BLOCK),
    ("TAUSIK_ROLE=1 claude --name x", BLOCK),
    ("kitty -e claude", BLOCK),

    # --- должно проходить: живой сессии не создаётся ---
    ("claude agents --json", PASS),
    ("claude stop 83d548af", PASS),
    ("claude logs 83d548af", PASS),
    ("claude attach 83d548af", PASS),
    ("claude doctor", PASS),
    ("claude --help", PASS),
    ("claude --version", PASS),
    ("claude -p 'посчитай что-нибудь'", PASS),
    ("claude --print 'разовый запрос'", PASS),

    # --- launch: единственный правильный путь ---
    ("launch inventory-round2", PASS),
    ("launch tausik-supervisor --bg --model sonnet", PASS),
    ("cd ~ && launch план --name x", PASS),

    # --- упоминание, а не запуск ---
    ("echo 'запусти claude --name x'", PASS),
    ("grep -rn 'claude --name' docs/", PASS),
    ("cat /tmp/launch-test.log", PASS),

    # --- обычная работа не задета ---
    ("go build ./cmd/state", PASS),
    ("git status", PASS),

    # --- тело heredoc — данные, а не команды ---
    # Поймано собственным гардом: он заблокировал правку документации,
    # где слово claude стоит внутри питоновского скрипта.
    ("python3 - <<'PY'\nprint('запусти claude руками')\nPY", PASS),
    ("cat <<EOF > /tmp/x\nclaude --name x\nEOF", PASS),
    ("python3 - <<'PY'\nt = t.replace('claude', 'launch')\nPY", PASS),
    # но команда ПОСЛЕ закрытого heredoc проверяется как обычно
    ("python3 - <<'PY'\nprint(1)\nPY\nclaude --name work", BLOCK),
]


def run(cmd: str) -> bool:
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 2


def main() -> int:
    failed = 0
    for cmd, want in CASES:
        got = run(cmd)
        ok = got == want
        failed += not ok
        print(f"  {'✓' if ok else '✗'} {'БЛОК' if got else 'ok  '}  {cmd[:60]}")

    # Битый вход не должен ронять хук: упавший гард молчит там, где обязан
    # блокировать.
    proc = subprocess.run([sys.executable, HOOK], input="не json",
                          capture_output=True, text=True)
    ok = proc.returncode == 0
    failed += not ok
    print(f"  {'✓' if ok else '✗'} битый вход не роняет хук")

    print(f"\nвсего: {len(CASES) + 1}   провалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
