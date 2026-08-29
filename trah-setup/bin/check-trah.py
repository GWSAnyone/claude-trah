#!/usr/bin/env python3
"""Сторож №2: дошла ли правка до модели.

Проверяет не то, что записано в бинарник, а то, что уехало в запросе — это
единственная проверка, которая закрывает дыру tweakcc (он проверяет запись,
но не доставку).

Использование: check-trah.py <файл.jsonl>
"""
import json
import sys
from pathlib import Path

# Опознавательные обрывки наших правок: инструмент -> кусок текста.
МЕТКИ = {
    "Bash": "This is a tool of action",
    "Read": "prefer it: it returns the symbol you asked about",
    "Edit": "the boundaries come from the language server",
    "Grep": "Text search is the last resort",
}


def main() -> int:
    recs = [json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
    tools = {}
    for r in recs:
        for t in r["body"].get("tools") or []:
            tools[t.get("name", "?")] = json.dumps(t, ensure_ascii=False)

    print(f"инструментов в запросе: {len(tools)}\n")
    плохо = 0
    for имя, кусок in МЕТКИ.items():
        if имя not in tools:
            print(f"  ?  {имя}: инструмента нет в этой сессии — проверить нечего")
            continue
        if кусок in tools[имя]:
            print(f"  ✓  {имя}: правка дошла")
        else:
            print(f"  ✗  {имя}: правки НЕТ в описании")
            плохо += 1
    return 1 if плохо else 0


if __name__ == "__main__":
    raise SystemExit(main())
