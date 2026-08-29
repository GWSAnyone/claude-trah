#!/usr/bin/env python3
"""Доехала ли дисциплина до промпта подагента.

Пробой в ловушку это не проверить: подагент запускается уже после ответа
модели, а ловушка ответа не даёт. Нужен прозрачный отвод и настоящий прогон, в
котором подагент действительно запустился.

Отвод — `relay.py`, он же и пишет улов. Прогон стоит настоящих токенов:

    python3 relay.py 8802 /tmp/sub.jsonl &
    ANTHROPIC_BASE_URL=http://127.0.0.1:8802 claude --print 'задача с подагентом'
    python3 check-subagent.py /tmp/sub.jsonl

Обмер 29.08.2026 таким прогоном: оба куска доехали — `agent-explore` и
`agent-general-purpose` нашлись в двенадцати запросах из девятнадцати.

Использование: check-subagent.py <улов.jsonl>
"""
import json
import sys
from pathlib import Path

МЕТКИ = {
    "общий подагент": "Before your first search, pull in the symbolic code tools",
    "Explore": "Symbolic search beats text search for anything you can name",
}
ПОРЧА = ("â€", "Ð", "Ã©", "â")


def системный(запись: dict) -> str:
    с = запись["body"].get("system")
    if isinstance(с, list):
        return "\n".join(б.get("text", "") for б in с if isinstance(б, dict))
    return с or ""


def main() -> int:
    записи = [
        json.loads(s)
        for s in Path(sys.argv[1]).read_text().splitlines()
        if s.strip()
    ]
    print(f"запросов в улове: {len(записи)}")
    итог = {и: 0 for и in МЕТКИ}
    покалечено = 0
    for n, з in enumerate(записи):
        текст = системный(з)
        for имя, метка in МЕТКИ.items():
            if метка in текст:
                итог[имя] += 1
                print(f"  ✓  запрос {n}: промпт «{имя}» с нашей дисциплиной")
        if any(след in текст for след in ПОРЧА):
            покалечено += 1
            print(f"  ✗  запрос {n}: следы битой кодировки в системном промпте")
    for имя, сколько in итог.items():
        if not сколько:
            print(f"  ·  «{имя}»: в этом улове не встретился")
    return 1 if покалечено else 0


if __name__ == "__main__":
    raise SystemExit(main())
