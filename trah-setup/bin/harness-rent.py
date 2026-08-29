#!/usr/bin/env python3
"""Рента оснастки: сколько знаков занимает в системном промпте каждая способность.

В системный промпт попадает НЕ тело агента или навыка, а его карточка:
имя, описание, список инструментов. Тело грузится только при вызове.
Считаем карточки — это и есть плата за одно лишь наличие способности.

Токены оценены как знаки/3.5 для латиницы и знаки/2.5 для кириллицы —
это оценка, а не подсчёт токенизатором.
"""
import pathlib
import re
import sys

HOME = pathlib.Path.home()
FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)


def токенов(text: str) -> int:
    кир = sum(1 for c in text if "а" <= c.lower() <= "я" or c == "ё")
    лат = len(text) - кир
    return round(лат / 3.5 + кир / 2.5)


def карточка(path: pathlib.Path) -> tuple[str, int]:
    """Имя и размер карточки: то из шапки, что уезжает в системный промпт."""
    text = path.read_text(encoding="utf-8", errors="replace")
    имя = path.parent.name if path.name == "SKILL.md" else path.stem
    m = FRONT.match(text)
    if not m:
        return имя, 0
    шапка = m.group(1)
    нужное = []
    ключ = None
    for line in шапка.splitlines():
        if re.match(r"^[a-zA-Z_-]+:", line):
            ключ = line.split(":", 1)[0]
            if ключ in ("name", "description", "tools", "model"):
                нужное.append(line)
        elif ключ in ("name", "description", "tools", "model"):
            нужное.append(line)
    return имя, токенов("\n".join(нужное))


def раздел(title: str, пути: list) -> int:
    строки = []
    итого = 0
    for p in пути:
        имя, т = карточка(p)
        итого += т
        строки.append((т, имя, str(p)))
    print(f"\n=== {title}: ~{итого} токенов на сессию ===")
    for т, имя, _ in sorted(строки, reverse=True):
        print(f"  {т:5d}  {имя}")
    return итого


def main():
    всего = 0
    свои = sorted((HOME / ".claude" / "agents").glob("*.md"))
    всего += раздел("свои агенты", свои)

    навыки = sorted((HOME / ".claude" / "skills").glob("*/SKILL.md"))
    всего += раздел("свои навыки", навыки)

    import json
    настройки = json.load(open(HOME / ".claude" / "settings.json"))
    включены = {k.split("@")[0] for k, v in (настройки.get("enabledPlugins") or {}).items() if v}

    кэш = HOME / ".claude" / "plugins" / "cache"
    for плагин in sorted(кэш.glob("*/*/*/agents")):
        имя = плагин.parent.parent.name
        if имя not in включены:
            print(f"\n=== плагин {имя}: ВЫКЛЮЧЕН, ренты нет ===")
            continue
        всего += раздел(f"плагин {имя}: агенты", sorted(плагин.glob("*.md")))
    for плагин in sorted(кэш.glob("*/*/*/skills/*/SKILL.md")):
        имя = плагин.parents[3].name
        if имя not in включены:
            continue
        всего += раздел(f"плагин {имя}: навык", [плагин])

    print(f"\nИТОГО карточек: ~{всего} токенов в каждой сессии")
    print("Сверх этого: наставления MCP-серверов и имена отложенных инструментов —")
    print("их в файлах на диске нет, они приходят от самих серверов.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
