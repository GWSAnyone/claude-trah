#!/usr/bin/env python3
"""Проверки `catalogue.py` на поддельном корпусе. Токенов не стоит.

Корпус подделывается целиком: тест не должен зависеть от того, стоит ли на
машине форк tweakcc и какая версия у него внутри.
"""
import importlib.util
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


def загрузить(корпус: Path):
    os.environ["TWEAKCC_PROMPTS"] = str(корпус)
    путь = Path(__file__).resolve().parent / "catalogue.py"
    спец = importlib.util.spec_from_file_location("catalogue", путь)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        корпус = Path(tmp)
        (корпус / "prompts-9.9.9.json").write_text(json.dumps({
            "version": "9.9.9",
            "prompts": [
                {"id": "system-prompt-alpha", "name": "Альфа",
                 "description": "первый", "pieces": ["Начало ", "${x}", " конец"]},
                {"id": "tool-description-beta", "name": "Бета",
                 "description": "второй",
                 "pieces": ["Это описание инструмента длиннее сорока знаков подряд."]},
                {"id": "system-reminder-gamma", "name": "Гамма",
                 "description": "третий", "pieces": []},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        м = загрузить(корпус)

        записи = м.корпус("9.9.9")
        check("записи прочитаны", len(записи) == 3, str(len(записи)))
        альфа = записи[0]
        check("подстановка помечена", "${…}" in альфа["текст"], альфа["текст"])
        check("куски сохранены целиком",
              "".join(альфа["куски"]) == "Начало ${x} конец")

        занято = м.занятость(записи, {"наш-кусок": ["Начало "]})
        check("якорь находит запись", занято == {"system-prompt-alpha": ["наш-кусок"]},
              str(занято))
        check("чужой якорь не находит ничего",
              м.занятость(записи, {"наш": ["такого текста нет"]}) == {})

        # Якорь, разорванный подстановкой, ловится: сверка идёт по СКЛЕЙКЕ кусков.
        сквозной = м.занятость(записи, {"сквозной": ["Начало ${x} конец"]})
        check("склейка кусков ищется целиком",
              сквозной == {"system-prompt-alpha": ["сквозной"]}, str(сквозной))

        снимок = "…Это описание инструмента длиннее сорока знаков подряд.…"
        доехало = м.доставка(записи, снимок)
        check("доставка узнаёт длинный кусок",
              [з["id"] for з in доехало] == ["tool-description-beta"],
              str([з["id"] for з in доехало]))
        check("короткий кусок в доставку не идёт",
              м.доставка(записи, "Начало") == [])
        check("пустые куски не падают", м.доставка([записи[2]], "что угодно") == [])

    print(f"всего: {всего}   провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
