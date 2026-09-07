#!/usr/bin/env python3
"""Проверки `anchors.py` на поддельном файле. Токенов не стоит."""
import importlib.util
import sys
import tempfile
from pathlib import Path

СКРИПТ = Path(__file__).resolve().parent / "anchors.py"
спец = importlib.util.spec_from_file_location("anchors", СКРИПТ)
a = importlib.util.module_from_spec(спец)
спец.loader.exec_module(a)

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        путь = Path(tmp) / "бинарь"
        # Две копии иглы — как в настоящем файле: одна в тексте, одна «в байткоде».
        путь.write_bytes(
            "начало АБВ середина ".encode()
            + b"\x00\x01\x02"
            + " хвост АБВ конец ".encode()
            + "ещё ГДЕ".encode())
        байты = путь.read_bytes()

        check("счёт видит обе копии", a.счёт(байты, "АБВ") == 2, str(a.счёт(байты, "АБВ")))
        check("счёт одиночной", a.счёт(байты, "ГДЕ") == 1)
        check("отсутствующая игла — ноль", a.счёт(байты, "ЖЗИ") == 0)

        куски = a.окрестность(байты, "АБВ", до=6, после=9)
        check("окрестность на каждое вхождение", len(куски) == 2, str(len(куски)))
        check("окрестность несёт иглу", all("АБВ" in к for к in куски), str(куски))
        check("окрестность отсутствующей пуста", a.окрестность(байты, "ЖЗИ") == [])

        # Битые байты не должны ронять разбор: файл сборки не UTF-8 целиком.
        битый = Path(tmp) / "битый"
        битый.write_bytes(b"\xff\xfe " + "игла".encode() + b" \xff\xfe")
        check("битые байты не роняют",
              "игла" in a.окрестность(битый.read_bytes(), "игла")[0])

        check("довод-путь берётся как есть", a.файл(str(путь)) == путь)
        check("довод-версия ищется среди установленных",
              str(a.файл("9.9.9")).endswith("versions/9.9.9"), str(a.файл("9.9.9")))

    print(f"всего: {всего}   провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
