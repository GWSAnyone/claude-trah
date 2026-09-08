#!/usr/bin/env python3
"""Пересадить цельный блок нашего кода из форка в новую вендорную версию.

Для ханков, которые переносчик не уложил: блок берётся строками из файла форка,
переименовывается по карте и вставляется перед указанной строкой-якорем цели.
Руками при этом не перепечатывается ни строки — перепечатка ста пятидесяти строк
это способ внести опечатку, которую потом искать полдня.
"""
import argparse
import re
import sys
from pathlib import Path

ФОРК = Path("/home/kaltsit/Ledevia/Projects/claude-code-vsc/ext/extension")
ИМЯ = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

# 2.1.247 → 2.1.260. Первые девять — из port.py, дальше добавленные при разборе
# конкретных мест, каждое со свидетелем.
КАРТА = {
    "j": "D", "z0": "K0", "W20": "K30", "B20": "W30", "Z1": "X1",
    "uX": "ZX", "gX": "JX", "l9": "m2", "Q0": "e1",
    "E1": "L1",    # фрагмент: E(L1,{children:[…]}) в fileToolHeader
    "nZ": "BG",    # реестр инструментов: BG(Z.name, J).hidden
    "ny0": "em0",  # заголовок инструмента: BG($.name,J).header(J,$.input)
    "oy0": "$c0",  # тело инструмента: BG(J.name,Z).body(…)
    "dy0": "im0",  # общий разбор входа MCP
    "Y1": "$1",    # useState: let [q, z] = $1(!1)
    "Y2": "n5",    # хук в начале компонента инструмента
}


def переименовать(строка: str) -> str:
    return ИМЯ.sub(lambda м: КАРТА.get(м.group(), м.group()), строка)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--файл", required=True, help="например webview/index.js")
    ap.add_argument("--с", type=int, required=True, help="первая строка форка, 1-based")
    ap.add_argument("--по", type=int, required=True, help="последняя строка форка")
    ap.add_argument("--перед", required=True, help="строка-якорь в цели")
    ap.add_argument("--в", required=True, help="каталог площадки")
    а = ap.parse_args()

    блок = (ФОРК / а.файл).read_text(encoding="utf-8").split("\n")[а.с - 1:а.по]
    блок = [переименовать(с) for с in блок]

    цель = Path(а.в) / "ext/extension" / а.файл
    строки = цель.read_text(encoding="utf-8").split("\n")
    где = [i for i, с in enumerate(строки) if с == а.перед]
    if len(где) != 1:
        print(f"якорь найден {len(где)} раз — вставлять нельзя", file=sys.stderr)
        return 1
    i = где[0]
    строки[i:i] = блок
    цель.write_text("\n".join(строки), encoding="utf-8")
    print(f"вставлено {len(блок)} строк перед строкой {i + 1} файла {цель}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
