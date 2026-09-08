#!/usr/bin/env python3
"""Пересадить наши САМОСТОЯТЕЛЬНЫЕ функции дословно, без позиционной карты.

Переносчик выводит имена позиционно из совпавшего вендорного контекста. Для
правки ВНУТРИ вендорной функции это верно. Для нашей собственной функции — нет:
её локальные имена в карте не участвуют, и когда карта говорит `Y → Z`, а `Z` в
теле уже есть, две переменные становятся одной. Переобозначение безопасно только
когда отображение полное и взаимно однозначное на именах блока.

Здесь тело берётся из форка как есть и переименовывается ТОЛЬКО по модульной
карте — тем именам, которые объявлены вне функции и потому в ней свободны.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/home/kaltsit/vsc-port-260/tools")
from graft import КАРТА, переименовать  # noqa: E402

ФОРК = Path(
    "/home/kaltsit/Ledevia/Projects/claude-code-vsc/ext/extension/webview/index.js")
НАЧАЛО = re.compile(r"^(?:function|var|class) (fork[A-Za-z0-9_]*)\b")


def границы(строки: list[str]) -> dict[str, tuple[int, int]]:
    """Имя нашей функции → полуинтервал строк [начало, конец)."""
    итог, имя, нач = {}, None, 0
    for i, с in enumerate(строки):
        м = НАЧАЛО.match(с)
        if м and имя is None:
            имя, нач = м.group(1), i
            continue
        if имя is not None and (с in ("}", "};") or с.startswith("}")) and \
                not с[:1].isspace():
            итог[имя] = (нач, i + 1)
            имя = None
    return итог


ЦЕЛЬ = Path(sys.argv[1])
ИМЕНА = sys.argv[2].split(",")

исходные = ФОРК.read_text(encoding="utf-8").split("\n")
целевые = ЦЕЛЬ.read_text(encoding="utf-8").split("\n")
ги, гц = границы(исходные), границы(целевые)

задания = []
for имя in ИМЕНА:
    if имя not in ги or имя not in гц:
        print(f"  ✗ {имя}: не найдена ({'в форке' if имя not in ги else 'в цели'})")
        continue
    a, b = ги[имя]
    тело = [переименовать(с) for с in исходные[a:b]]
    задания.append((гц[имя], тело, имя))

for (a, b), тело, имя in sorted(задания, key=lambda z: -z[0][0]):
    целевые[a:b] = тело
    print(f"  ✓ {имя}: заменено {b - a} строк на {len(тело)}")

ЦЕЛЬ.write_text("\n".join(целевые), encoding="utf-8")
print(f"записано: {ЦЕЛЬ}  (модульных имён в карте: {len(КАРТА)})")
