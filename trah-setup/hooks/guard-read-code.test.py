#!/usr/bin/env python3
"""Проверки гарда на чтение крупного кода целиком.

Ложный отказ здесь дороже пропуска: Read — базовый инструмент, и гард, который
мешает читать md, маленький файл или точный диапазон, отключат целиком. Поэтому
на каждый путь пропуска есть свой случай, а у отказа обязателен выход повтором.
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


def загрузить():
    путь = Path(__file__).resolve().parent / "guard-read-code.py"
    спец = importlib.util.spec_from_file_location("guard_read_code", str(путь))
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


гард = загрузить()


def прогнать(вход, tool="Read", session="s1"):
    сырьё = вход if isinstance(вход, str) else json.dumps(
        {"tool_name": tool, "tool_input": вход, "session_id": session})
    прежний, ошибки = sys.stdin, io.StringIO()
    sys.stdin = io.StringIO(сырьё)
    прежний_err, sys.stderr = sys.stderr, ошибки
    try:
        код = гард.main()
    finally:
        sys.stdin, sys.stderr = прежний, прежний_err
    return код, ошибки.getvalue()


def файл(каталог: Path, имя: str, строк: int) -> str:
    п = каталог / имя
    п.write_text("".join(f"line {i}\n" for i in range(строк)))
    return str(п)


with tempfile.TemporaryDirectory() as корень, tempfile.TemporaryDirectory() as чужой, \
        tempfile.TemporaryDirectory() as состояние:
    os.environ["NUDGE_SERENA_ROOTS"] = корень
    os.environ["TMPDIR"] = состояние
    к = Path(корень)
    большой = файл(к, "big.go", 300)
    маленький = файл(к, "small.go", 150)
    доку = файл(к, "notes.md", 900)
    снаружи = файл(Path(чужой), "other.go", 900)

    код, текст = прогнать({"file_path": большой})
    check("крупный код целиком — отказ", код == 2, f"={код}")
    check("отказ называет Serena и выход повтором",
          "find_symbol" in текст and "repeat" in текст, текст[:120])
    код, _ = прогнать({"file_path": большой})
    check("повтор того же Read — проходит", код == 0, f"={код}")
    код, _ = прогнать({"file_path": большой})
    check("после выхода счёт начинается заново", код == 2, f"={код}")
    код, _ = прогнать({"file_path": большой}, session="s2")
    check("чужая сессия не пользуется чужим выходом", код == 2, f"={код}")

    check("диапазон до потолка — проходит",
          прогнать({"file_path": большой, "offset": 10, "limit": 120})[0] == 0)
    check("limit больше потолка — отказ",
          прогнать({"file_path": большой, "limit": 250}, session="s3")[0] == 2)
    check("хвост файла короче потолка — проходит",
          прогнать({"file_path": большой, "offset": 250}, session="s4")[0] == 0)
    check("маленький файл целиком — проходит",
          прогнать({"file_path": маленький}, session="s5")[0] == 0)
    check("не код — проходит", прогнать({"file_path": доку}, session="s6")[0] == 0)
    check("код вне нашего дерева — проходит",
          прогнать({"file_path": снаружи}, session="s7")[0] == 0)
    check("файла нет — проходит",
          прогнать({"file_path": str(к / "нет.go")}, session="s8")[0] == 0)
    check("не Read — проходит",
          прогнать({"file_path": большой}, tool="Edit", session="s9")[0] == 0)
    check("мусор на входе — проходит", прогнать("не json")[0] == 0)
    check("вход не словарь — проходит", прогнать('{"tool_name": "Read", "tool_input": 5}')[0] == 0)

print(f"  {всего - провалов}/{всего} проверок прошло")
sys.exit(1 if провалов else 0)
