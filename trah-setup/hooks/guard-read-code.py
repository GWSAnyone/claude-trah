#!/usr/bin/env python3
"""PreToolUse-гард на чтение крупного кода целиком встроенным Read.

Замер по сессии Э3 (SyncedProjects, 08–13.09.2026): Read по коду проекта — 295
раз, из них 23 целиком и 160 диапазоном больше 40 строк, при правиле «Read — для
пары известных строк». Мягкое напоминание уже стояло: счётчик serena-hooks 38 раз
ответил на Read ошибкой, ход тратился, а Read шёл дальше. Совет поведение не
менял.

Полный запрет Read опасен: это базовый инструмент, и файл бывает нужен целиком
(владелец 13.09: «слишком опасно полностью блокировать»). Поэтому отказ узкий и
всегда с выходом:

  * только код (КОД) в нашем рабочем дереве;
  * только чтение больше ПОТОЛОК строк за раз — без limit Read отдаёт до 2000;
  * только файл длиннее ФАЙЛ строк;
  * тот же Read того же файла, повторённый в пределах ОКНО секунд после отказа,
    проходит: сессия настояла — значит нужно.

Что считать нашим деревом, решает `our_tree` из nudge-serena.py, а не своя
копия: две редакции одного ответа разошлись бы молча.

Exit 2 = отказ, stderr уходит модели. Exit 0 = пропустить.
"""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

КОД = (".go", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".py")
ПОТОЛОК = 120
ФАЙЛ = 200
ОКНО = 600
# Столько строк Read отдаёт, когда limit не задан.
READ_ПО_УМОЛЧАНИЮ = 2000

MSG = (
    "BLOCKED: Read of {n} lines of code at once. Serena: get_symbols_overview on the "
    "file, then find_symbol with include_body for the symbols you need. For a few "
    "known lines, Read with offset and a limit up to {cap}. If you truly need this "
    "much of the file, repeat the same Read: a repeat within ten minutes goes through."
)


def _nudge_serena():
    путь = Path(__file__).resolve().parent / "nudge-serena.py"
    спец = importlib.util.spec_from_file_location("nudge_serena", str(путь))
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def состояние(session_id: str) -> Path:
    корень = Path(os.environ.get("TMPDIR") or "/tmp") / "guard-read-code"
    return корень / f"{session_id or 'без-сессии'}.json"


def прочитать(файл: Path) -> dict:
    try:
        данные = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return данные if isinstance(данные, dict) else {}


def записать(файл: Path, данные: dict) -> None:
    try:
        файл.parent.mkdir(parents=True, exist_ok=True)
        файл.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def строк(путь: str) -> int:
    n = 0
    with open(путь, "rb") as ф:
        while кусок := ф.read(1 << 20):
            n += кусок.count(b"\n")
    return n


def сколько_прочтёт(вход: dict, всего: int) -> int:
    limit = вход.get("limit")
    offset = вход.get("offset")
    запрошено = limit if isinstance(limit, int) and limit > 0 else READ_ПО_УМОЛЧАНИЮ
    начало = max(offset - 1, 0) if isinstance(offset, int) else 0
    return max(min(запрошено, всего - начало), 0)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Read":
        return 0
    вход = payload.get("tool_input") or {}
    if not isinstance(вход, dict):
        return 0
    путь = str(вход.get("file_path") or "")
    if not путь.endswith(КОД) or not os.path.isfile(путь):
        return 0
    limit = вход.get("limit")
    if isinstance(limit, int) and 0 < limit <= ПОТОЛОК:
        return 0
    try:
        всего = строк(путь)
    except OSError:
        return 0
    if всего <= ФАЙЛ:
        return 0
    n = сколько_прочтёт(вход, всего)
    if n <= ПОТОЛОК:
        return 0
    if not _nudge_serena().our_tree(путь):
        return 0

    файл = состояние(str(payload.get("session_id") or ""))
    отказы = прочитать(файл)
    ключ = os.path.realpath(путь)
    сейчас = time.time()
    прошлый = отказы.get(ключ)
    if isinstance(прошлый, (int, float)) and сейчас - прошлый <= ОКНО:
        отказы.pop(ключ)
        записать(файл, отказы)
        return 0
    отказы = {к: т for к, т in отказы.items()
              if isinstance(т, (int, float)) and сейчас - т <= ОКНО}
    отказы[ключ] = сейчас
    записать(файл, отказы)
    sys.stderr.write(MSG.format(n=n, cap=ПОТОЛОК) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
