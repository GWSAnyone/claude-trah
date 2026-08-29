#!/usr/bin/env python3
"""Какой вариант описания Bash подаётся — и есть ли в нём наш пункт.

Вопрос, ради которого написано: правка «prefer dedicated tools bullet»
записана в бинарник, но до модели не доехала ни в печатном прогоне, ни в
живой сессии. Надо отличить две причины: патч сломал подачу — или этот
вариант описания в такой обстановке не подаётся вовсе, и тогда патченый и
штатный бинарники дадут одно и то же.

Использование: bash-variant.py <файл.jsonl> [ещё файлы…]
"""
import json
import sys
from pathlib import Path

МЕТКИ = [
    ("IMPORTANT-пункт", "IMPORTANT: Avoid using this tool"),
    ("наша правка", "This is a tool of action"),
    ("раздел Git", "# Git"),
    ("песочница", "sandbox"),
]


def main() -> int:
    for путь in sys.argv[1:]:
        print(f"═══ {путь}")
        recs = [json.loads(l) for l in Path(путь).read_text().splitlines() if l.strip()]
        видели = set()
        for n, r in enumerate(recs):
            for t in r["body"].get("tools") or []:
                if t.get("name") != "Bash":
                    continue
                d = t["description"]
                if d in видели:
                    continue
                видели.add(d)
                есть = ", ".join(и for и, к in МЕТКИ if к in d) or "ничего из списка"
                print(f"  запрос {n}: {len(d)} символов | {есть}")
        if not видели:
            print("  Bash в запросах не встретился")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
