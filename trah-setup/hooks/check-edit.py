#!/usr/bin/env python3
"""PostToolUse: внешняя проверка правки. Разбор, и только разбор.

ЗАЧЕМ ЭТО ХУК, А НЕ СТРОКА В ПРОМПТЕ. Anthropic называет проверяемость рычагом
номер один и одновременно велит НЕ приказывать Opus 5 перепроверять себя:
руководство по модели прямо говорит убрать из промпта указания вида «include a
final verification step» — модель и так проверяет, а указание даёт перепроверку
вхолостую. Противоречия здесь нет. Приказ модели стоит токенов на решение и
исполняется по настроению; хук стоит ноль модельных токенов и возвращает факт,
которого модель иначе не знает.

ТОЛЬКО РАЗБОР. Проверяется одно: разбирается ли файл вообще. Ни форматирование,
ни стиль, ни линтер — там живут ложные срабатывания, а ложное срабатывание в
хуке дороже пропущенной ошибки: оно приходит на КАЖДУЮ правку, и его начинают
не читать. Разбор же однозначен: файл либо синтаксически цел, либо нет.

Незнакомое расширение — молчание. Нет проверяльщика в системе — молчание.
Файла нет (удалён, переименован) — молчание.

`exit 2` не блокирует: для `PostToolUse` он означает «показать stderr модели».
Вызов уже состоялся, откатывать нечего — можно только сообщить.
"""

import json
import os
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

# Поля, из которых бывает путь: у встроенных инструментов одно имя, у Serena
# другое. `relative_path` считается от корня проекта, а не от текущего каталога.
ПОЛЯ_ПУТИ = ("file_path", "notebook_path", "relative_path")

ТАЙМАУТ = 5

# Потолок размера. Исходники столько не весят, а разборщик, которому подсунули
# многогигабайтный файл, втягивает его в память одной строкой. Разбор 29.08.2026
# назвал этот путь и как отказ в обслуживании, и как способ подвесить сессию.
ПОТОЛОК_БАЙТ = 2 * 1024 * 1024


def _текст(путь: Path) -> str:
    """Содержимое файла для внутренних разборщиков.

    Кодировка `utf-8-sig`, а не `utf-8`: без неё метка порядка байтов остаётся
    в начале строки, и `compile` объявляет РАБОЧИЙ файл сломанным
    («invalid non-printable character U+FEFF»). Настоящий интерпретатор метку
    снимает сам. Проверено запуском 29.08.2026: питон файл выполнял, а хук на
    него ругался.
    """
    return путь.read_text(encoding="utf-8-sig", errors="replace")


def _разбор_питона(путь: Path) -> str | None:
    try:
        # Предупреждения глушим намеренно. `compile` печатает SyntaxWarning
        # (скажем, на `'\d+'`) прямо в stderr процесса, минуя всю логику
        # ниже, — и хук переставал молчать на целом файле. Проверено запуском.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            compile(_текст(путь), str(путь), "exec")
    except SyntaxError as e:
        строка = f":{e.lineno}" if e.lineno else ""
        return f"{путь.name}{строка}: {e.msg}"
    except Exception:
        return None
    return None


def _разбор_json(путь: Path) -> str | None:
    try:
        json.loads(_текст(путь))
    except json.JSONDecodeError as e:
        return f"{путь.name}:{e.lineno}: {e.msg}"
    except Exception:
        return None
    return None


def _разбор_yaml(путь: Path) -> str | None:
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return None
    try:
        yaml.safe_load(_текст(путь))
    except yaml.YAMLError as e:
        return f"{путь.name}: {str(e).splitlines()[0]}"
    except Exception:
        return None
    return None


def _разбор_toml(путь: Path) -> str | None:
    try:
        import tomllib  # noqa: PLC0415
    except ImportError:
        return None
    try:
        tomllib.loads(_текст(путь))
    except tomllib.TOMLDecodeError as e:
        return f"{путь.name}: {e}"
    except Exception:
        return None
    return None


def найти_программу(программа: str) -> str | None:
    """Полный путь к программе — тот самый, что потом и запустится.

    Под Windows `subprocess.run(["bash", …])` ищет по правилам CreateProcess:
    `System32` раньше `PATH`. Там лежит `bash.exe` от WSL, и проверка
    `shutil.which` (нашла Git Bash) и запуск (взял WSL) смотрели на РАЗНЫЕ
    программы. Итог 23.09.2026: каждая правка `.sh` объявлялась «не
    разбирается» с «WSL … execvpe(/bin/bash) failed» — ложная тревога на
    каждой правке. Поэтому запускаем найденный путь, а WSL-заглушку не берём.
    """
    путь = shutil.which(программа)
    if os.name != "nt" or программа != "bash":
        return путь
    годные = [путь] if путь else []
    for корень in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if корень:
            годные.append(os.path.join(корень, "Git", "bin", "bash.exe"))
    for п in годные:
        низ = (п or "").lower()
        if п and os.path.isfile(п) and "system32" not in низ and "windowsapps" not in низ:
            return п
    return None


def _внешним(программа: str, доводы: list[str]):
    """Проверяльщик-подпроцесс. Нет программы в системе — молчание, не ошибка."""

    def проверить(путь: Path) -> str | None:
        исполнимое = найти_программу(программа)
        if исполнимое is None:
            return None
        try:
            г = subprocess.run([исполнимое, *доводы, str(путь)],
                               capture_output=True, text=True, timeout=ТАЙМАУТ)
        except (subprocess.TimeoutExpired, OSError):
            return None
        if г.returncode == 0:
            return None
        весть = (г.stderr or г.stdout or "").strip()
        return весть.splitlines()[0][:300] if весть else None

    return проверить


# Расширение -> проверяльщик. Всё, чего здесь нет, не проверяется вовсе.
ПРОВЕРЯЛЬЩИКИ = {
    ".py": _разбор_питона,
    ".json": _разбор_json,
    ".yaml": _разбор_yaml,
    ".yml": _разбор_yaml,
    ".toml": _разбор_toml,
    ".go": _внешним("gofmt", ["-e", "-l"]),
    ".js": _внешним("node", ["--check"]),
    ".mjs": _внешним("node", ["--check"]),
    ".cjs": _внешним("node", ["--check"]),
    ".sh": _внешним("bash", ["-n"]),
    ".bash": _внешним("bash", ["-n"]),
}


def путь_правки(payload: dict) -> Path | None:
    вход = payload.get("tool_input")
    if not isinstance(вход, dict):
        return None
    поле = next((п for п in ПОЛЯ_ПУТИ
                 if isinstance(вход.get(п), str) and вход[п].strip()), None)
    if поле is None:
        return None
    п = Path(вход[поле])
    if п.is_absolute():
        return п

    # `relative_path` Serena считается от КОРНЯ ПРОЕКТА, а мы знаем только
    # рабочий каталог. Обычно они совпадают, но когда нет — склейка укажет на
    # ЧУЖОЙ файл, и хук либо промолчит о сломанной правке, либо обругает
    # правку, которой не было. Оба исхода проверены запуском 29.08.2026.
    #
    # Поэтому: склеили, разрешили `..`, и если получившийся путь вышел за
    # пределы рабочего каталога — молчим. Мы не знаем, что это за файл, а
    # догадка тут стоит дороже пропуска.
    основа = Path(payload.get("cwd") or os.getcwd())
    целиком = (основа / п).resolve()
    try:
        целиком.relative_to(основа.resolve())
    except ValueError:
        return None
    return целиком


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    try:
        путь = путь_правки(payload)
        if путь is None or not путь.is_file():
            return 0
        # Читать нечем — не наше дело. Без этой проверки `bash -n` возвращал
        # 126 на файле без прав, а `_внешним` считает ненулевой код ошибкой
        # разбора: хук говорил «файл сломан» про целый файл. Проверено
        # запуском 29.08.2026.
        if not os.access(путь, os.R_OK):
            return 0
        if путь.stat().st_size > ПОТОЛОК_БАЙТ:
            return 0
        проверить = ПРОВЕРЯЛЬЩИКИ.get(путь.suffix.lower())
        if проверить is None:
            return 0
        беда = проверить(путь)
        if not беда:
            return 0
        sys.stderr.write(
            f"ПРАВКА НЕ РАЗБИРАЕТСЯ: {беда}\n\n"
            f"Файл после правки синтаксически сломан. Починить сейчас, пока "
            f"известно, какая правка его сломала.\n"
        )
        return 2
    except Exception:
        # Проверяльщик не имеет права ронять сессию. Молчание безопаснее.
        return 0


if __name__ == "__main__":
    sys.exit(main())
