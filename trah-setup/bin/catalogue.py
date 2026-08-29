#!/usr/bin/env python3
"""Опись кусков штатного промпта, сверенная с нашими правками.

ОТКУДА БЕРЁТСЯ. Форк tweakcc везёт извлечённый корпус:
`data/prompts/prompts-<версия>.json` — для 2.1.247 это 6077 записей, у каждой
`name`, `id`, `description` и `pieces` (текст, разрезанный по местам подстановок
`${…}`). Тот же корпус опубликован отдельно: github.com/Piebald-AI/claude-code-
system-prompts. Подбирать якоря вслепую по 250-мегабайтному бинарнику больше не
нужно.

ГРАНИЦА ДОВЕРИЯ. Корпус НЕПОЛОН. Проверено 29.08.2026: строк
`End git commit messages with` и `Co-Authored-By` в `prompts-2.1.247.json` нет
вовсе, а в бинарнике они есть. Опись — карта, источник истины — бинарь; чего в
описи не нашлось, ищется байтовым счётом по файлу версии.

    catalogue.py                          сводка: что мы уже патчим
    catalogue.py --groups                 категории по префиксу id
    catalogue.py --grep <подстрока>       искать по имени, описанию и тексту
    catalogue.py --show <id>              текст одного куска
    catalogue.py --free [префикс]         незанятое, крупные сверху
    catalogue.py --delivered <снимок>     что из описи реально уезжает
    catalogue.py --delivered <..> --which <префикс>

Каталог снимка делает `snapshot.py`; сверка идёт по самому длинному куску
записи, поэтому это НИЖНЯЯ оценка: кусок, разрезанный подстановками на мелкие
части, в ответ не попадёт, даже если уезжает.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

КОРПУС = Path(os.environ.get(
    "TWEAKCC_PROMPTS", Path.home() / ".local/share/tweakcc-fixed/data/prompts"))
КУСКИ = Path(__file__).resolve().parent.parent / "fragments"
# Прицел один на весь комплект и лежит в version.txt: номер, вписанный сюда
# вторым экземпляром, разъезжается с настоящим молча.
ВЕРСИЯ = (Path(__file__).resolve().parent.parent / "version.txt").read_text().strip()


def корпус(версия: str) -> list[dict]:
    д = json.loads((КОРПУС / f"prompts-{версия}.json").read_text(encoding="utf-8"))
    записи = []
    for э in д.get("prompts") or []:
        куски = э.get("pieces") or []
        записи.append({
            "id": э.get("id") or "",
            "name": э.get("name") or "",
            "описание": э.get("description") or "",
            # Метка подстановки нужна глазу: без неё соседние куски слипаются и
            # читаются как одна фраза, которой в промпте не бывает.
            "текст": "${…}".join(куски),
            "куски": куски,
        })
    return записи


def наши() -> dict[str, list[str]]:
    """id нашего куска -> якоря, по которым он цепляется за бинарник."""
    из = {}
    for ф in sorted(КУСКИ.glob("*.md")):
        текст = ф.read_text(encoding="utf-8")
        if not текст.startswith("---"):
            continue
        try:
            мета = json.loads(текст.split("---", 2)[1])
        except json.JSONDecodeError:
            continue
        if мета.get("route") == "brief":
            continue
        якоря = [e.get("anchor", "") for e in мета.get("edits", []) if e.get("anchor")]
        if якоря:
            из[мета["id"]] = якоря
    return из


def занятость(записи: list[dict], н: dict[str, list[str]]) -> dict[str, list[str]]:
    """id записи корпуса -> наши куски, которые её трогают."""
    занято: dict[str, list[str]] = {}
    for наш, якоря in н.items():
        for з in записи:
            цельный = "".join(з["куски"])
            if any(я in цельный for я in якоря):
                занято.setdefault(з["id"], []).append(наш)
    return занято


def доставка(записи: list[dict], снимок: str) -> list[dict]:
    """Записи, чей самый длинный кусок нашёлся в снимке."""
    вышло = []
    for з in записи:
        длинный = max(з["куски"], key=len) if з["куски"] else ""
        if len(длинный) >= 40 and длинный in снимок:
            вышло.append(з)
    return вышло


def строка(з: dict, занято: dict[str, list[str]]) -> str:
    метка = " ← " + ", ".join(занято[з["id"]]) if з["id"] in занято else ""
    return f"{len(з['текст']):6}  {з['id']}{метка}\n        {з['name']}"


def main() -> int:
    д = sys.argv[1:]
    версия = next((a for a in д if a[:1].isdigit()), ВЕРСИЯ)
    записи = корпус(версия)
    н = наши()
    занято = занятость(записи, н)

    if "--show" in д:
        по_ид = {з["id"]: з for з in записи}
        з = по_ид.get(д[д.index("--show") + 1])
        if not з:
            print("нет такого id")
            return 1
        print(f"{з['name']}\n{з['описание']}\n{'-' * 60}\n{з['текст']}")
        return 0

    if "--grep" in д:
        игла = д[д.index("--grep") + 1].lower()
        for з in записи:
            if (игла in з["name"].lower() or игла in з["описание"].lower()
                    or игла in з["текст"].lower()):
                print(строка(з, занято))
        return 0

    if "--groups" in д:
        for имя, n in Counter("-".join(з["id"].split("-")[:2])
                              for з in записи).most_common():
            print(f"{n:5}  {имя}")
        return 0

    if "--delivered" in д:
        каталог = Path(д[д.index("--delivered") + 1])
        снимок = "\n".join(ф.read_text(encoding="utf-8", errors="replace")
                           for ф in каталог.glob("*.txt"))
        доехало = доставка(записи, снимок)
        группы: dict[str, list[int]] = {}
        for з in записи:
            г = "-".join(з["id"].split("-")[:2])
            группы.setdefault(г, [0, 0])[1] += 1
        for з in доехало:
            группы["-".join(з["id"].split("-")[:2])][0] += 1
        print(f"снимок: {len(снимок)} знаков, записей корпуса {len(записи)}")
        for г, (сколько, всего_) in sorted(группы.items(), key=lambda x: -x[1][0]):
            if сколько:
                print(f"{сколько:5} / {всего_:<5} {г}")
        if "--which" in д:
            префикс = д[д.index("--which") + 1]
            for з in sorted(доехало, key=lambda з: -len(з["текст"])):
                if з["id"].startswith(префикс):
                    print(строка(з, занято))
        return 0

    if "--free" in д:
        i = д.index("--free")
        префикс = д[i + 1] if len(д) > i + 1 and not д[i + 1].startswith("-") else ""
        свободные = [з for з in записи
                     if з["id"].startswith(префикс) and з["id"] not in занято]
        for з in sorted(свободные, key=lambda з: -len(з["текст"]))[:60]:
            print(строка(з, занято))
        print(f"\nсвободных в «{префикс or 'всё'}»: {len(свободные)}")
        return 0

    print(f"версия {версия}: записей {len(записи)}, знаков "
          f"{sum(len(з['текст']) for з in записи)}")
    нашлись = {и for v in занято.values() for и in v}
    print(f"наших правок бинарника: {len(н)}, нашли своё место: {len(нашлись)}")
    пропавшие = set(н) - нашлись
    if пропавшие:
        print("в корпусе не нашлись (искать в бинарнике): "
              + ", ".join(sorted(пропавшие)))
    print("\nзанятые записи корпуса:")
    for ид, наши_ in sorted(занято.items()):
        print(f"  {ид}\n        ← {', '.join(наши_)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
