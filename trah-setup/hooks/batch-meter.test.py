#!/usr/bin/env python3
"""Тесты счётчика ширины пачки.

Главное, что здесь проверяется, — БЕЗВРЕДНОСТЬ. Хук стоит на горячем пути
между пачкой и следующим обращением к модели: любой ненулевой выход оборвал бы
агентский цикл. Поэтому на каждый мыслимый мусор во входе ожидается ровно 0.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ХУК = os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch-meter.py")

_спец = importlib.util.spec_from_file_location("batch_meter", ХУК)
модуль_хука = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(модуль_хука)

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


def запустить(payload, каталог: Path) -> tuple[int, list[dict]]:
    сырое = payload if isinstance(payload, str) else json.dumps(payload)
    г = subprocess.run([sys.executable, ХУК], input=сырое, text=True,
                       capture_output=True,
                       env={**os.environ, "TRAH_METRICS_DIR": str(каталог)})
    журнал = каталог / "batches.jsonl"
    строки = []
    if журнал.exists():
        строки = [json.loads(с) for с in журнал.read_text(encoding="utf-8").splitlines() if с.strip()]
    return г.returncode, строки


def пачка(имена: list[str], **прочее) -> dict:
    return {"hook_event_name": "PostToolBatch", "session_id": "s1", "cwd": "/tmp",
            "tool_calls": [{"tool_name": и, "tool_input": {}} for и in имена], **прочее}


print("batch-meter.py")

# --- ширина -----------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    код, строки = запустить(пачка(["Read", "Grep", "Bash"]), Path(d))
    check("выход 0", код == 0, f"={код}")
    check("одна строка журнала", len(строки) == 1, f"={len(строки)}")
    check("ширина 3", строки and строки[0]["width"] == 3, f"={строки}")
    check("имена записаны", строки and строки[0]["tools"] == ["Read", "Grep", "Bash"])
    check("сессия записана", строки and строки[0]["session"] == "s1")
    check("неуспешных 0", строки and строки[0]["failed"] == 0)

# --- накопление -------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    запустить(пачка(["Read"]), Path(d))
    запустить(пачка(["Bash", "Bash"]), Path(d))
    _, строки = запустить(пачка(["Edit"]), Path(d))
    check("журнал дописывается", len(строки) == 3, f"={len(строки)}")
    check("ширины по порядку", [с["width"] for с in строки] == [1, 2, 1],
          f"={[с['width'] for с in строки]}")

# --- неуспешные вызовы ------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    p = пачка([])
    p["tool_calls"] = [
        {"tool_name": "Bash", "tool_input": {}, "succeeded": True},
        {"tool_name": "Bash", "tool_input": {}, "succeeded": False},
        {"tool_name": "Read", "tool_input": {}, "tool_response": {"is_error": True}},
        {"tool_name": "Read", "tool_input": {}, "tool_response": {"ok": 1}},
    ]
    _, строки = запустить(p, Path(d))
    check("неуспешных 2", строки and строки[0]["failed"] == 2, f"={строки}")
    check("ширина 4 при неуспехах", строки and строки[0]["width"] == 4)

# --- мусор на входе: ВСЕГДА 0 и никогда не падать ---------------------------
МУСОР = [
    ("не JSON", "это не json вовсе"),
    ("пустая строка", ""),
    ("пустой объект", {}),
    ("tool_calls не список", {"tool_calls": "Read"}),
    ("tool_calls пуст", {"tool_calls": []}),
    ("элементы не объекты", {"tool_calls": ["Read", 5, None]}),
    ("без tool_name", {"tool_calls": [{"tool_input": {}}]}),
    ("null внутри", {"tool_calls": [None]}),
    ("вложенный мусор", {"tool_calls": [{"tool_name": {"a": 1}}]}),
]
for имя, вход in МУСОР:
    with tempfile.TemporaryDirectory() as d:
        код, строки = запустить(вход, Path(d))
        check(f"мусор «{имя}»: выход 0", код == 0, f"={код}")

# Пустая пачка не должна оставлять следа: строка с нулевой шириной испортила бы
# среднее, а мерить нечего.
with tempfile.TemporaryDirectory() as d:
    _, строки = запустить({"tool_calls": []}, Path(d))
    check("пустая пачка не пишется", строки == [], f"={строки}")

# Элемент без имени пропускается, но пачка с одним годным всё равно считается.
with tempfile.TemporaryDirectory() as d:
    _, строки = запустить({"tool_calls": [{"tool_name": "Read"}, {"нет": "имени"}]}, Path(d))
    check("годный элемент считается", строки and строки[0]["width"] == 1, f"={строки}")

# --- ПУСТАЯ переменная не должна ронять журнал в рабочий каталог ------------
# Найдено разбором 29.08.2026 и проверено запуском: `os.environ.get(k, умолч)`
# возвращает пустую строку, если переменная выставлена в пустую, и умолчание
# не подхватывается. Журнал уезжал в текущий каталог, то есть в репозиторий.
with tempfile.TemporaryDirectory() as d:
    г = subprocess.run(
        [sys.executable, ХУК], input=json.dumps(пачка(["Read"])), text=True,
        capture_output=True, cwd=d, env={**os.environ, "TRAH_METRICS_DIR": ""})
    check("пустая переменная: выход 0", г.returncode == 0, f"={г.returncode}")
    check("пустая переменная: журнал НЕ в рабочем каталоге",
          not (Path(d) / "batches.jsonl").exists(),
          "журнал упал в текущий каталог")

# --- журнал вычисляется в функции, а не на импорте --------------------------
# `Path.home()` бросает там, где домашний каталог не определяется. На уровне
# модуля это исключение не поймать, и хук выходит с кодом 1, нарушая свой же
# договор «выход всегда 0».
check("путь журнала считается функцией, а не на импорте",
      callable(getattr(модуль_хука, "журнал", None)),
      "если это снова константа уровня модуля — договор о выходе 0 нарушен")

print(f"  {всего - провалов}/{всего} проверок прошло")
sys.exit(1 if провалов else 0)
