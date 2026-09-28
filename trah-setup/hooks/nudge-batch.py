#!/usr/bin/env python3
"""Напомнить о пачках, когда одиночные вызовы пошли цепочкой.

Замер по сессии Э3 (SyncedProjects, 08–13.09.2026): одиночных пачек 63%, самая
длинная цепочка одиночек подряд — 70. В 15 отрезках из 19 первые 30 пачек после
сжатия шире остальных. Правило о пачках живёт в системном промпте, но к концу
отрезка сессия сползает в ритм «вызов — ответ». Сильнее формулировкой это не
лечится: правило надо вернуть в тот момент, когда оно ослабло.

Хук считает одиночные пачки подряд и на ПОРОГ-й шлёт одно напоминание в сокет
сессии — тем же транспортом, что лесенка сжатия (в VS Code он работает: заказы
сжатия через него исполнялись). Пачка шире одного вызова сбрасывает счёт, так что
следующее напоминание придёт только после новой цепочки. Порог 8 — стартовое
значение, а не замер; меняется `TRAH_BATCH_STREAK`.

Пачки подагента не считаются: сокет один на сессию, и напоминание ушло бы не
тому, кто сползает.

ХУК ОБЯЗАН БЫТЬ БЕЗВРЕДНЫМ, как и batch-meter: он стоит на горячем пути, выход
всегда 0, любое исключение гасится.
"""

import importlib.util
import json
import os
import re
import tempfile
import sys
from collections import Counter
from pathlib import Path

import sockmsg

ПОРОГ_ПО_УМОЛЧАНИЮ = 8

ТЕКСТ = (
    "{n} tool batches in a row carried a single call each. A lone call is a defect "
    "unless its argument came from the previous answer. Before the next call, name "
    "every independent question this step still has and send them in one turn."
)

# Подсказка по тому, из чего цепочка. Разбор одиночек 14.09.2026 (12 крупнейших
# стенограмм): честно склеиваемые кучи — Bash за Bash без эффекта и ошибки 3 342,
# чтение за чтением 1 984, правка того же файла 950, правка другого файла 641.
# Общий текст про слои ни одну из них не называет.
ЧТЕНИЕ = {"Read", "Grep", "Glob", "mcp__serena__find_symbol", "mcp__serena__search_for_pattern",
          "mcp__serena__get_symbols_overview", "mcp__serena__find_referencing_symbols",
          "mcp__serena__find_file", "mcp__serena__list_dir", "mcp__serena__find_declaration",
          "mcp__serena__find_implementations"}
ПРАВКА = {"Edit", "Write", "MultiEdit", "mcp__serena__replace_symbol_body",
          "mcp__serena__replace_content", "mcp__serena__replace_in_files",
          "mcp__serena__insert_after_symbol", "mcp__serena__insert_before_symbol"}
ПОДСКАЗКИ = {
    "Bash": " Most of them were Bash: commands that do not read each other's output and "
            "do not wait for a rebuild or restart go as one call joined with &&.",
    "чтение": " Most of them were reads: every file and symbol this step needs goes out "
              "in one turn, the probably-needed ones included.",
    "правка": " Most of them were edits: all edits of the step go in one turn, several "
              "edits of the same file included, and the check after them goes last in that "
              "same turn — calls of one turn run in order.",
}


def подсказка(имена: list[str]) -> str:
    имена = [re.sub(r"^mcp__serena-[A-Za-z0-9-]+__", "mcp__serena__", и) for и in имена]
    виды = Counter("Bash" if и == "Bash" else "чтение" if и in ЧТЕНИЕ
                   else "правка" if и in ПРАВКА else "прочее" for и in имена)
    if not виды:
        return ""
    вид, сколько = виды.most_common(1)[0]
    return ПОДСКАЗКИ.get(вид, "") if сколько * 2 >= len(имена) else ""


def порог() -> int:
    try:
        значение = int(os.environ.get("TRAH_BATCH_STREAK") or ПОРОГ_ПО_УМОЛЧАНИЮ)
    except ValueError:
        return ПОРОГ_ПО_УМОЛЧАНИЮ
    return значение if значение >= 2 else ПОРОГ_ПО_УМОЛЧАНИЮ


def _batch_meter():
    путь = Path(__file__).resolve().parent / "batch-meter.py"
    спец = importlib.util.spec_from_file_location("batch_meter", str(путь))
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def состояние(session_id: str) -> Path:
    корень = Path(os.environ["TMPDIR"] if os.path.isdir(os.environ.get("TMPDIR") or "") else tempfile.gettempdir()) / "nudge-batch"
    return корень / f"{session_id or 'без-сессии'}.json"


def шаг(подряд: int, ширина: int, предел: int) -> tuple[int, bool]:
    """Новый счёт одиночек подряд и надо ли напомнить на этой пачке."""
    if ширина != 1:
        return 0, False
    подряд += 1
    return подряд, подряд == предел


def main() -> int:
    if os.environ.get("NUDGE_BATCH") == "off":
        return 0
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("agent_id"):
            return 0
        строка = _batch_meter().запись(payload)
        if строка is None:
            return 0
        файл = состояние(str(payload.get("session_id") or ""))
        try:
            прежнее = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            прежнее = {}
        предел = порог()
        подряд, напомнить = шаг(int(прежнее.get("подряд") or 0), строка["width"], предел)
        имена = (list(прежнее.get("имена") or []) + строка["tools"])[-предел:] if подряд else []
        файл.parent.mkdir(parents=True, exist_ok=True)
        файл.write_text(json.dumps({"подряд": подряд, "имена": имена}), encoding="utf-8")
        if напомнить:
            sockmsg.послать(ТЕКСТ.format(n=предел) + подсказка(имена))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
