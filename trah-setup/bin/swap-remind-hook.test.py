#!/usr/bin/env python3
"""Проверка `swap-remind-hook.py` — на поддельном доме, host не трогается.

Скрипт правит `~/.claude/settings.json`, поэтому проверять его на живой машине
нельзя. Он умеет `--home`, и все случаи ниже идут в свежий временный каталог.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

СКРИПТ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swap-remind-hook.py")

НАСТРОЙКИ = """{
  "permissions": {
    "allow": [
      "mcp__serena__*"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__serena__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /дом/.claude/hooks/guard-serena-scope.py",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "serena-hooks remind --client=claude-code",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
"""


def дом_с_настройками(корень: str, текст: str = НАСТРОЙКИ) -> Path:
    дом = Path(корень)
    (дом / ".claude").mkdir(parents=True, exist_ok=True)
    (дом / ".claude/settings.json").write_text(текст, encoding="utf-8")
    return дом


def запустить(дом: Path, *флаги: str):
    res = subprocess.run([sys.executable, СКРИПТ, "--home", str(дом), *флаги],
                         capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


def команда_хука(дом: Path) -> str:
    данные = json.loads((дом / ".claude/settings.json").read_text(encoding="utf-8"))
    записи = данные["hooks"]["PreToolUse"]
    for запись in записи:
        for х in запись.get("hooks", []):
            if "remind" in х["command"] or "shim" in х["command"]:
                return х["command"]
    return ""


def main() -> int:
    провалов = 0

    def check(имя: str, ок: bool, подробность: str = "") -> None:
        nonlocal провалов
        if not ок:
            провалов += 1
        print(f"{'✓' if ок else '✗'} {имя}" + (f"  — {подробность}" if not ок and подробность else ""))

    # ── показ ничего не пишет ────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as врем:
        дом = дом_с_настройками(врем)
        было = (дом / ".claude/settings.json").read_text(encoding="utf-8")
        код, вывод = запустить(дом, "--dry-run")
        стало = (дом / ".claude/settings.json").read_text(encoding="utf-8")
        check("--dry-run: код 0", код == 0, вывод[:120])
        check("--dry-run: настройки не тронуты", было == стало)
        check("--dry-run: прокладка не скопирована",
              not (дом / ".claude/hooks/serena-remind-shim.py").exists())

    # ── настоящая перестановка ───────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as врем:
        дом = дом_с_настройками(врем)
        код, вывод = запустить(дом)
        check("перестановка: код 0", код == 0, вывод[:160])

        команда = команда_хука(дом)
        check("команда хука указывает на прокладку", "serena-remind-shim.py" in команда, команда)
        check("апстрим из настроек убран", "serena-hooks remind" not in
              (дом / ".claude/settings.json").read_text(encoding="utf-8"))
        check("прокладка скопирована",
              (дом / ".claude/hooks/serena-remind-shim.py").is_file())

        текст = (дом / ".claude/settings.json").read_text(encoding="utf-8")
        try:
            данные = json.loads(текст)
            разбирается = True
        except ValueError:
            данные, разбирается = {}, False
        check("настройки остались разбираемым JSON", разбирается)
        check("соседний хук на месте",
              разбирается and any("guard-serena-scope" in х["command"]
                                  for з in данные["hooks"]["PreToolUse"]
                                  for х in з.get("hooks", [])))
        check("timeout соседней записи не потерян",
              разбирается and данные["hooks"]["PreToolUse"][1]["hooks"][0]["timeout"] == 15)

        копии = list((дом / ".claude").glob("settings.json.bak-*"))
        check("копия настроек снята", len(копии) == 1, str(копии))
        check("копия — это ИСХОДНЫЕ настройки",
              bool(копии) and "serena-hooks remind" in копии[0].read_text(encoding="utf-8"))
        check("временный файл за собой убран",
              not list((дом / ".claude").glob("settings.json.new-*")))
        check("откат назван в выводе", f"cp {копии[0]}" in вывод if копии else False,
              вывод[-200:])

        # ── откат той самой командой ─────────────────────────────────────────
        shutil.copy2(копии[0], дом / ".claude/settings.json")
        check("после отката вернулся апстрим",
              "serena-hooks remind" in команда_хука(дом), команда_хука(дом))

    # ── повторный запуск безвреден ───────────────────────────────────────────
    with tempfile.TemporaryDirectory() as врем:
        дом = дом_с_настройками(врем)
        запустить(дом)
        первые = (дом / ".claude/settings.json").read_text(encoding="utf-8")
        код, вывод = запустить(дом)
        check("повтор: код 0", код == 0, вывод[:120])
        check("повтор: сказано «уже переставлено»", "уже переставлено" in вывод, вывод[:120])
        check("повтор: настройки не тронуты",
              первые == (дом / ".claude/settings.json").read_text(encoding="utf-8"))
        check("повтор: второй копии не наплодил",
              len(list((дом / ".claude").glob("settings.json.bak-*"))) == 1)

    # ── отказы вместо порчи ──────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as врем:
        дом = дом_с_настройками(врем, НАСТРОЙКИ.replace(
            '"command": "serena-hooks remind --client=claude-code",',
            '"command": "что-то другое",'))
        код, вывод = запустить(дом)
        check("нет строки апстрима — отказ, а не правка", код == 1, вывод[:120])

    with tempfile.TemporaryDirectory() as врем:
        двойные = НАСТРОЙКИ.replace(
            """      {
        "matcher": "",""",
            """      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "serena-hooks remind --client=claude-code",
            "timeout": 15
          }
        ]
      },
      {
        "matcher": "",""")
        дом = дом_с_настройками(врем, двойные)
        код, вывод = запустить(дом)
        check("две строки апстрима — отказ, вслепую не правит", код == 1, вывод[:120])
        check("при отказе настройки не тронуты",
              "serena-remind-shim" not in
              (дом / ".claude/settings.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as врем:
        дом = Path(врем)
        (дом / ".claude").mkdir(parents=True)
        код, вывод = запустить(дом)
        check("нет settings.json — отказ, а не падение", код == 1, вывод[:120])

    print(f"\nпровалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
