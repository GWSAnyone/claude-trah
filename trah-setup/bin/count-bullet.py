#!/usr/bin/env python3
"""Сколько копий пункта «prefer dedicated tools» в бинарнике и одинаковы ли они.

Корпусный патч tweakcc правит ОДНО вхождение, а `grep -c` показал строки, а не
вхождения. Прежде чем писать свою замену, надо знать точное число и убедиться,
что все копии совпадают дословно — иначе одна строка поиска накроет не всё.

Использование: count-bullet.py <бинарник> [ещё бинарники…]
"""
import sys
from pathlib import Path

ЯКОРЬ = b"IMPORTANT: Avoid using this tool to run "


def main() -> int:
    for путь in sys.argv[1:]:
        данные = Path(путь).read_bytes()
        места = []
        i = данные.find(ЯКОРЬ)
        while i >= 0:
            места.append(i)
            i = данные.find(ЯКОРЬ, i + 1)
        print(f"═══ {путь}: вхождений {len(места)}")
        хвосты = {}
        for м in места:
            хвост = данные[м : м + 330]
            хвосты.setdefault(хвост, []).append(м)
        for n, (хвост, где) in enumerate(хвостов_по_порядку(хвосты), 1):
            print(f"  вариант {n}: {len(где)} шт., смещения {где}")
            print("   ", хвост.decode("utf-8", "replace").replace("\n", " | ")[:320])
    return 0


def хвостов_по_порядку(хвосты):
    return sorted(хвосты.items(), key=lambda kv: min(kv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
