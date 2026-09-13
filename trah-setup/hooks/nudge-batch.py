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
import sys
from pathlib import Path

import sockmsg

ПОРОГ_ПО_УМОЛЧАНИЮ = 8

ТЕКСТ = (
    "{n} tool batches in a row carried a single call each. A lone call is a defect "
    "unless its argument came from the previous answer. Before the next call, name "
    "every independent question this step still has and send them in one turn."
)


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
    корень = Path(os.environ.get("TMPDIR") or "/tmp") / "nudge-batch"
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
        файл.parent.mkdir(parents=True, exist_ok=True)
        файл.write_text(json.dumps({"подряд": подряд}), encoding="utf-8")
        if напомнить:
            sockmsg.послать(ТЕКСТ.format(n=предел))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
