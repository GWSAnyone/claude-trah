#!/usr/bin/env python3
"""Проверки `nudge-batch.py`. Токенов не стоит.

Напоминание будит модель, поэтому лишнее стоит хода. Главное здесь — что оно
приходит ровно один раз на цепочку, а не на каждую одиночную пачку после порога.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


sys.path.insert(0, str(Path(__file__).resolve().parent))
путь = Path(__file__).resolve().parent / "nudge-batch.py"
спец = importlib.util.spec_from_file_location("nudge_batch", str(путь))
хук = importlib.util.module_from_spec(спец)
спец.loader.exec_module(хук)

отправлено: list[str] = []
хук.sockmsg.послать = lambda текст, *а, **к: отправлено.append(текст) or ""


def пачка(ширина: int, session: str = "s1", инструмент: str = "Bash", **лишнее) -> int:
    payload = {"session_id": session,
               "tool_calls": [{"tool_name": инструмент} for _ in range(ширина)], **лишнее}
    прежний = sys.stdin
    sys.stdin = io.StringIO(json.dumps(payload))
    try:
        return хук.main()
    finally:
        sys.stdin = прежний


with tempfile.TemporaryDirectory() as d:
    os.environ["TMPDIR"] = d
    os.environ.pop("TRAH_BATCH_STREAK", None)

    for _ in range(7):
        пачка(1)
    check("семь одиночек — молчит", отправлено == [], str(отправлено))
    пачка(1)
    check("восьмая — одно напоминание", len(отправлено) == 1, str(len(отправлено)))
    check("текст называет порог", отправлено and отправлено[0].startswith("8 tool batches"))
    for _ in range(10):
        пачка(1)
    check("дальше по цепочке — молчит", len(отправлено) == 1, str(len(отправлено)))
    пачка(3)
    for _ in range(8):
        пачка(1)
    check("после широкой пачки — новая цепочка, новое напоминание",
          len(отправлено) == 2, str(len(отправлено)))

    пачка(0)
    check("пустая пачка счёт не трогает",
          json.loads((Path(d) / "nudge-batch" / "s1.json").read_text())["подряд"] == 8)
    for _ in range(8):
        пачка(1, session="s2", agent_id="a1")
    check("пачки подагента не считаются", len(отправлено) == 2, str(len(отправлено)))
    for _ in range(7):
        пачка(1, session="s3")
    check("сессии считаются раздельно", len(отправлено) == 2, str(len(отправлено)))

    os.environ["TRAH_BATCH_STREAK"] = "3"
    for _ in range(3):
        пачка(1, session="s4")
    check("порог из окружения", len(отправлено) == 3, str(len(отправлено)))
    os.environ["TRAH_BATCH_STREAK"] = "мусор"
    check("кривой порог — умолчание", хук.порог() == 8, str(хук.порог()))

    os.environ["NUDGE_BATCH"] = "off"
    for _ in range(8):
        пачка(1, session="s5")
    check("выключатель", len(отправлено) == 3, str(len(отправлено)))
    os.environ.pop("NUDGE_BATCH")

    отправлено.clear()
    for _ in range(8):
        пачка(1, session="s6")
    check("цепочка Bash — подсказка про &&", len(отправлено) == 1 and "&&" in отправлено[-1],
          str(отправлено))
    for _ in range(8):
        пачка(1, session="s7", инструмент="mcp__serena__find_symbol")
    check("цепочка чтений — подсказка про чтение",
          len(отправлено) == 2 and "Most of them were reads" in отправлено[-1], str(отправлено))
    for _ in range(8):
        пачка(1, session="s8", инструмент="Edit")
    check("цепочка правок — подсказка про правки",
          len(отправлено) == 3 and "Most of them were edits" in отправлено[-1], str(отправлено))
    for i in range(8):
        пачка(1, session="s9", инструмент=("Bash", "Read", "Edit", "Agent")[i % 4])
    check("смесь без большинства — без подсказки",
          len(отправлено) == 4 and "Most of them" not in отправлено[-1], str(отправлено))
    пачка(1, session="s10")
    пачка(2, session="s10", инструмент="Read")
    for _ in range(8):
        пачка(1, session="s10", инструмент="Read")
    check("широкая пачка стирает прежние имена",
          len(отправлено) == 5 and "Most of them were reads" in отправлено[-1], str(отправлено))

    прежний = sys.stdin
    sys.stdin = io.StringIO("не json")
    try:
        check("мусор — выход 0", хук.main() == 0)
    finally:
        sys.stdin = прежний

print(f"  {всего - провалов}/{всего} проверок прошло")
sys.exit(1 if провалов else 0)
