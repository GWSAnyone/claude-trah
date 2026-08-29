#!/usr/bin/env python3
"""Тесты проверяльщика правок.

Два требования, и второе важнее первого.

1. Сломанный файл замечен: выход 2 и внятное сообщение.
2. МОЛЧАНИЕ ВЕЗДЕ ОСТАЛЬНОМ. Ложное срабатывание здесь дороже пропуска: хук
   приходит на КАЖДУЮ правку, и стоит ему пару раз соврать, как его перестают
   читать. Поэтому незнакомое расширение, отсутствующий файл, отсутствующий
   проверяльщик и мусор во входе обязаны давать ровно 0 и пустой stderr.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ХУК = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-edit.py")

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


def запустить(payload) -> tuple[int, str]:
    сырое = payload if isinstance(payload, str) else json.dumps(payload)
    г = subprocess.run([sys.executable, ХУК], input=сырое, text=True, capture_output=True)
    return г.returncode, г.stderr


def правка(путь, поле: str = "file_path", cwd: str | None = None) -> dict:
    вход = {поле: str(путь)}
    п = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": вход}
    if cwd:
        п["cwd"] = cwd
    return п


def файл(каталог: str, имя: str, текст: str) -> Path:
    п = Path(каталог) / имя
    п.write_text(текст, encoding="utf-8")
    return п


print("check-edit.py")

# --- ловит сломанное --------------------------------------------------------
ЛОМАНОЕ = [
    ("py", "a.py", "def f(:\n    pass\n"),
    ("json", "a.json", '{"a": 1,,}'),
]
for имя, файлик, текст in ЛОМАНОЕ:
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, файлик, текст)))
        check(f"ломаный {имя}: выход 2", код == 2, f"={код}")
        check(f"ломаный {имя}: сказано что", "НЕ РАЗБИРАЕТСЯ" in err, f"={err[:120]!r}")

# --- пропускает целое -------------------------------------------------------
ЦЕЛОЕ = [
    ("py", "a.py", "def f():\n    return 1\n"),
    ("json", "a.json", '{"a": [1, 2], "b": null}'),
    ("py пустой", "b.py", ""),
    ("json число", "b.json", "42"),
]
for имя, файлик, текст in ЦЕЛОЕ:
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, файлик, текст)))
        check(f"целый {имя}: выход 0", код == 0, f"={код}")
        check(f"целый {имя}: молчит", err == "", f"={err[:120]!r}")

# --- ЧУЖОЕ РАСШИРЕНИЕ: молчание (критерий закрытия итерации) ----------------
ЧУЖИЕ = ["a.md", "a.txt", "a.rs", "a.zig", "a.kt", "a.csv", "a.lock", "a", "a.PY.bak"]
for файлик in ЧУЖИЕ:
    with tempfile.TemporaryDirectory() as d:
        # Содержимое заведомо невалидно КАК КОД — и всё равно должно молчать.
        код, err = запустить(правка(файл(d, файлик, "def f(:\n{{{ ,,, ]]]")))
        check(f"чужое «{файлик}»: выход 0", код == 0, f"={код}")
        check(f"чужое «{файлик}»: молчит", err == "", f"={err[:80]!r}")

# --- файла нет --------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    код, err = запустить(правка(Path(d) / "нет-такого.py"))
    check("файла нет: выход 0", код == 0, f"={код}")
    check("файла нет: молчит", err == "", f"={err[:80]!r}")

# --- каталог вместо файла ---------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    код, _ = запустить(правка(d))
    check("каталог: выход 0", код == 0, f"={код}")

# --- путь Serena: relative_path от cwd --------------------------------------
with tempfile.TemporaryDirectory() as d:
    файл(d, "внутри.py", "def f(:\n")
    код, err = запустить(правка("внутри.py", поле="relative_path", cwd=d))
    check("relative_path разрешён от cwd", код == 2, f"={код}")
with tempfile.TemporaryDirectory() as d:
    файл(d, "внутри.py", "def f():\n    pass\n")
    код, _ = запустить(правка("внутри.py", поле="relative_path", cwd=d))
    check("relative_path целый: выход 0", код == 0, f"={код}")

# --- внешние проверяльщики, если они есть в системе -------------------------
if shutil.which("bash"):
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, "a.sh", "if [ 1 ; then\n")))
        check("ломаный sh: выход 2", код == 2, f"={код} {err[:100]!r}")
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, "a.sh", "echo привет\n")))
        check("целый sh: выход 0", код == 0, f"={код} {err[:100]!r}")

if shutil.which("gofmt"):
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, "a.go", "package main\nfunc main( {\n")))
        check("ломаный go: выход 2", код == 2, f"={код} {err[:100]!r}")
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, "a.go", "package main\n\nfunc main() {}\n")))
        check("целый go: выход 0", код == 0, f"={код} {err[:100]!r}")

if shutil.which("node"):
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, "a.js", "function f( {\n")))
        check("ломаный js: выход 2", код == 2, f"={код} {err[:100]!r}")
    with tempfile.TemporaryDirectory() as d:
        код, err = запустить(правка(файл(d, "a.js", "function f() { return 1; }\n")))
        check("целый js: выход 0", код == 0, f"={код} {err[:100]!r}")

# --- ЛОЖНЫЕ СРАБАТЫВАНИЯ, найденные разбором 29.08.2026 ---------------------
# Все три проверены запуском ДО правки: хук объявлял сломанным целый файл.

# Метка порядка байтов: питон такой файл выполняет, хук ругался.
with tempfile.TemporaryDirectory() as d:
    п = Path(d) / "bom.py"
    п.write_bytes(b"\xef\xbb\xbfx = 1\n")
    рабочий = subprocess.run([sys.executable, str(п)], capture_output=True).returncode
    check("BOM: питон такой файл выполняет", рабочий == 0, f"код питона={рабочий}")
    код, err = запустить(правка(п))
    check("BOM в .py: выход 0", код == 0, f"={код}")
    check("BOM в .py: молчит", err == "", f"={err[:90]!r}")

# Нет прав на чтение — это не синтаксическая ошибка.
with tempfile.TemporaryDirectory() as d:
    п = файл(d, "a.sh", "echo ok\n")
    os.chmod(п, 0o000)
    try:
        код, err = запустить(правка(п))
        check("нечитаемый файл: выход 0", код == 0, f"={код}")
        check("нечитаемый файл: молчит", err == "", f"={err[:90]!r}")
    finally:
        os.chmod(п, 0o644)

# SyntaxWarning от compile печатался в stderr мимо всей логики.
with tempfile.TemporaryDirectory() as d:
    код, err = запустить(правка(файл(d, "w.py", "p = '\\d+'\n")))
    check("SyntaxWarning: выход 0", код == 0, f"={код}")
    check("SyntaxWarning: stderr пуст", err == "", f"={err[:90]!r}")

# `relative_path` за пределами рабочего каталога: чужой файл не наше дело.
with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as чужой:
    файл(чужой, "outside.json", "{,,,}")
    отн = os.path.relpath(os.path.join(чужой, "outside.json"), d)
    код, err = запустить(правка(отн, поле="relative_path", cwd=d))
    check("путь наружу через ..: выход 0", код == 0, f"={код}")
    check("путь наружу: молчит", err == "", f"={err[:90]!r}")

# Огромный файл разборщику не отдаём: он втянет его в память одной строкой.
with tempfile.TemporaryDirectory() as d:
    п = Path(d) / "huge.json"
    with п.open("wb") as ф:
        ф.truncate(3 * 1024 * 1024)
    код, err = запустить(правка(п))
    check("файл больше потолка: выход 0", код == 0, f"={код}")

# --- мусор во входе: всегда 0 -----------------------------------------------
МУСОР = [
    ("не JSON", "не json"),
    ("пусто", ""),
    ("пустой объект", {}),
    ("tool_input не объект", {"tool_input": "строка"}),
    ("пути нет", {"tool_input": {"content": "x"}}),
    ("путь пуст", {"tool_input": {"file_path": "   "}}),
    ("путь не строка", {"tool_input": {"file_path": 5}}),
]
for имя, вход in МУСОР:
    код, err = запустить(вход)
    check(f"мусор «{имя}»: выход 0", код == 0, f"={код}")
    check(f"мусор «{имя}»: молчит", err == "", f"={err[:80]!r}")

print(f"  {всего - провалов}/{всего} проверок прошло")
sys.exit(1 if провалов else 0)
