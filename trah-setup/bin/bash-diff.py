#!/usr/bin/env python3
"""Чем описание Bash в одном перехвате отличается от другого.

Нужно, чтобы отличить «правка не дошла» от «подаётся другой вариант описания»:
печатная проба и живая сессия дают разную длину, и надо видеть, какие куски
есть в одном и нет в другом.

Использование: bash-diff.py <файл-А.jsonl> <файл-Б.jsonl>
"""
import difflib
import json
import sys
from pathlib import Path


def описание(путь: str) -> tuple[str, list[str]]:
    for строка in Path(путь).read_text().splitlines():
        if not строка.strip():
            continue
        for t in json.loads(строка)["body"].get("tools") or []:
            if t.get("name") == "Bash":
                схема = sorted((t.get("input_schema") or {}).get("properties", {}))
                return t["description"], схема
    return "", []


def main() -> int:
    а, са = описание(sys.argv[1])
    б, сб = описание(sys.argv[2])
    print(f"А: {len(а)} символов, параметры {са}")
    print(f"Б: {len(б)} символов, параметры {сб}\n")
    for строка in difflib.unified_diff(
        а.splitlines(), б.splitlines(), "А", "Б", lineterm="", n=0
    ):
        print(строка[:200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
