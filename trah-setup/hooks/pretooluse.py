#!/usr/bin/env python3
"""Один вход на PreToolUse вместо шести: диспетчер сторожей и подсказчиков.

ЗАЧЕМ
=====

До этого на событии PreToolUse стояло шесть отдельных команд, и на КАЖДЫЙ вызов
Bash поднималось шесть процессов python. Замер 29.08 (десять прогонов на хук,
медиана):

    пустой запуск python              9 мс   ← пол любого хука
    guard-tausik-write               18 мс
    guard-destructive                19 мс
    guard-session-launch             16 мс
    nudge-serena                     16 мс
    serena-remind-shim               79 мс   ← внутри чужой процесс
    ────────────────────────────────────
    подряд                          162 мс,  разом ≈ 79 мс

Из 162 мс полезной работы — сорок с небольшим; остальное шесть раз оплаченный
старт интерпретатора. Диспетчер поднимает питон один раз и зовёт те же модули
как функции: их код и их проверки остаются нетронутыми.

УСТРОЙСТВО
==========

Модули объявлены не здесь, а РЕЕСТРОМ рядом: `modules.json` — свой, комплектный;
`modules.local.json` — чужой, для модулей соседних продуктов. У записи имя файла
и образец имён инструментов, на которых модуль что-то делает; образцы списаны с
прежней проводки в `settings.json` один в один. В режиме `claude trah`
(`TRAH_MODE=1`) чужой реестр не читается вовсе.

Модуль зовётся как `main()` с подменённым stdin и перехваченным выводом. Он не
знает, что работает не один: читает тот же JSON, пишет тот же JSON, возвращает
тот же код.

СЛИЯНИЕ ОТВЕТОВ
===============

  * код 2 от любого модуля — запрет. Его stderr уходит наружу дословно, а
    остальные модули не зовутся: вызова всё равно не будет;
  * JSON с `permissionDecision: deny` — тот же запрет, только выраженный иначе
    (так делает апстрим Serena через прокладку). Отдаём дословно и тоже
    останавливаемся;
  * всё прочее — необязательные сообщения. Они склеиваются в один JSON, чтобы
    подсказка второго модуля не затирала подсказку первого.

Порядок в реестре — это порядок важности: сторож, который запрещает, идёт раньше
подсказчика, который советует. Свои модули идут раньше чужих.

ОДНА ТОЧКА ОТКАЗА
=================

Плата за общий процесс названа честно: раньше сломанный хук выключал себя
одного, теперь мог бы унести всех. Поэтому каждый модуль обёрнут в свой
`try/except`, и его падение превращается в ЗАМЕТНОЕ сообщение с именем виновника,
а не в тишину. Упавший модуль не запрещает вызов — ровно как и раньше, когда его
traceback уходил в stderr с кодом 1.

Выключатели:
    PRETOOLUSE=off        — пропустить всё;
    PRETOOLUSE_DIR=путь   — брать модули из другого каталога (для проверок);
    PRETOOLUSE_ONLY=a,b   — звать только эти модули (для проверок).
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
from pathlib import Path

# Реестр модулей лежит файлом рядом с диспетчером, а не списком в коде.
#
# ПОЧЕМУ. До 07.09.2026 список был зашит здесь, и в нём стояли два гарда чужого
# продукта. Комплект из-за этого нельзя было снять отдельно: набор проверок
# требовал, чтобы каждый файл из зашитого списка лежал на диске, — а чужие файлы
# приезжают из чужого репозитория.
#
# Своё и чужое разведены двумя файлами. `modules.json` комплект ставит сам;
# `modules.local.json` того же формата заводит владелец машины для модулей
# соседних продуктов, и комплект его не пишет и не трогает.
#
# ЧУЖИЕ МОДУЛИ НЕ ЗОВУТСЯ В РЕЖИМЕ `trah`. Сессия режима не подчиняется правилам
# продукта, с которым она не работает: обёртка ставит TRAH_MODE=1, и при нём
# читается только свой реестр. Обычный `claude` читает оба.
РЕЕСТР = "modules.json"
РЕЕСТР_ЧУЖИХ = "modules.local.json"

_загруженные: dict = {}


def каталог() -> Path:
    return Path(os.environ.get("PRETOOLUSE_DIR")
                or Path(__file__).resolve().parent)


def _записи(путь: Path) -> list:
    """Записи одного реестра. Нет файла или он битый — пусто, а не падение:
    диспетчер стоит перед КАЖДЫМ вызовом, и его поломка дороже потерянного
    модуля."""
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    записи = данные.get("модули") if isinstance(данные, dict) else данные
    if not isinstance(записи, list):
        return []
    return [з for з in записи if isinstance(з, dict) and з.get("файл")]


def _годится(запись: dict) -> bool:
    """Модуль зовётся, если его файл на месте и утилиты, которые он требует, в
    PATH. Гард, запрещающий работу мимо утилиты, без самой утилиты запер бы
    машину."""
    if not (каталог() / str(запись["файл"])).exists():
        return False
    требует = запись.get("требует") or []
    return all(shutil.which(str(у)) for у in требует)


def модули() -> tuple:
    """(файл, образец) в порядке реестров: сначала свои, потом чужие."""
    записи = _записи(каталог() / РЕЕСТР)
    if os.environ.get("TRAH_MODE") != "1":
        записи += _записи(каталог() / РЕЕСТР_ЧУЖИХ)
    return tuple((str(з["файл"]), str(з.get("образец") or ".*"))
                 for з in записи if _годится(з))


def подходит(образец: str, инструмент: str) -> bool:
    """Так же, как сопоставляет сам Claude Code: полное совпадение по образцу."""
    try:
        return re.fullmatch(образец, инструмент) is not None
    except re.error:
        return False


def загрузить(имя: str):
    """Модуль по имени файла; None — файла нет, такое бывает и это не беда."""
    if имя in _загруженные:
        return _загруженные[имя]
    путь = каталог() / имя
    if not путь.exists():
        _загруженные[имя] = None
        return None
    спец = importlib.util.spec_from_file_location(
        "хук_" + имя.replace("-", "_").removesuffix(".py"), путь)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    _загруженные[имя] = модуль
    return модуль


def позвать(имя: str, raw: str) -> tuple:
    """Код возврата, stdout, stderr одного модуля. Падение — не запрет."""
    модуль = загрузить(имя)
    if модуль is None or not hasattr(модуль, "main"):
        return 0, "", ""
    вывод, ошибки = io.StringIO(), io.StringIO()
    прежний_stdin = sys.stdin
    sys.stdin = io.StringIO(raw)
    try:
        with contextlib.redirect_stdout(вывод), contextlib.redirect_stderr(ошибки):
            код = модуль.main()
    except SystemExit as e:
        код = e.code if isinstance(e.code, int) else 0
    except Exception as e:  # noqa: BLE001 — падение модуля не должно ронять вызов
        return 0, "", f"хук {имя} сломался: {type(e).__name__}: {e}"
    finally:
        sys.stdin = прежний_stdin
    return (код if isinstance(код, int) else 0), вывод.getvalue(), ошибки.getvalue()


def запрет_в_json(текст: str) -> bool:
    """Апстрим Serena выражает отказ JSON'ом, а не кодом возврата."""
    try:
        д = json.loads(текст)
    except (ValueError, TypeError):
        return False
    if not isinstance(д, dict):
        return False
    свои = д.get("hookSpecificOutput") or {}
    решение = свои.get("permissionDecision") or д.get("permissionDecision")
    return str(решение).lower() == "deny"


def разобрать(текст: str) -> tuple:
    """Сообщение и добавка к контексту из вывода модуля. Не JSON — просто текст."""
    текст = текст.strip()
    if not текст:
        return "", ""
    try:
        д = json.loads(текст)
    except ValueError:
        return текст, текст
    if not isinstance(д, dict):
        return текст, текст
    свои = д.get("hookSpecificOutput") or {}
    return (str(д.get("systemMessage") or ""),
            str(свои.get("additionalContext") or ""))


def main() -> int:
    if (os.environ.get("PRETOOLUSE") or "on").strip().lower() == "off":
        return 0
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw, strict=False)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    инструмент = str(payload.get("tool_name") or payload.get("toolName") or "")
    только = os.environ.get("PRETOOLUSE_ONLY")
    отобранные = {x.strip() for x in только.split(",")} if только else None

    сообщения, добавки, поломки = [], [], []
    for имя, образец in модули():
        if отобранные is not None and имя not in отобранные:
            continue
        if not подходит(образец, инструмент):
            continue
        код, вывод, ошибки = позвать(имя, raw)

        if код == 2:
            # Запрет. Дальше идти незачем: вызов не состоится.
            sys.stderr.write(ошибки or f"хук {имя} запретил вызов")
            return 2
        if вывод.strip() and запрет_в_json(вывод):
            sys.stdout.write(вывод)
            return 0
        if ошибки.strip().startswith(f"хук {имя} сломался"):
            поломки.append(ошибки.strip())
            continue
        с, д = разобрать(вывод)
        if с:
            сообщения.append(с)
        if д:
            добавки.append(д)

    if поломки:
        сообщения.extend(поломки)
        добавки.extend(поломки)
    if not сообщения and not добавки:
        return 0

    sys.stdout.write(json.dumps({
        "systemMessage": "\n\n".join(dict.fromkeys(с for с in сообщения if с)),
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n\n".join(dict.fromkeys(д for д in добавки if д)),
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
