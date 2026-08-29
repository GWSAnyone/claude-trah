#!/usr/bin/env python3
"""Проверки `batch-width.py` на синтетической стенограмме. Токенов не стоит.

Стенограмма подделывается в ЖИВОЙ форме: один ответ модели разложен по записям,
на каждый блок своя строка с общим `requestId`. Именно на этом первый замер
29.08.2026 и обманулся, показав ширину 1 у всего подряд.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

СКРИПТ = Path(__file__).resolve().parent / "batch-width.py"
спец = importlib.util.spec_from_file_location("batch_width", СКРИПТ)
bw = importlib.util.module_from_spec(спец)
спец.loader.exec_module(bw)

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


def пачка(время: str, инструменты: list[str], sidechain: bool = False,
          одной_записью: bool = False) -> list[str]:
    """Строки стенограммы для одного ответа модели."""
    общий = {"type": "assistant", "timestamp": время, "requestId": f"req-{время}"}
    if sidechain:
        общий["isSidechain"] = True
    блоки = [{"type": "tool_use", "name": и, "id": f"t{n}"}
             for n, и in enumerate(инструменты)]
    if одной_записью or not блоки:
        записи = [{**общий, "message": {"content": [{"type": "text", "text": "…"}] + блоки}}]
    else:
        записи = [{**общий, "message": {"content": [{"type": "text", "text": "…"}]}}]
        записи += [{**общий, "message": {"content": [б]}} for б in блоки]
    return [json.dumps(з, ensure_ascii=False) for з in записи]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        путь = Path(tmp) / "s.jsonl"
        строки: list[str] = []
        строки += пачка("2026-08-28T10:00:00Z", ["Bash"])
        строки += пачка("2026-08-28T11:00:00Z", ["Read", "Read", "Bash"])
        строки += [json.dumps({"type": "user", "timestamp": "2026-08-28T11:01:00Z"})]
        строки += пачка("2026-08-29T09:00:00Z", ["find_symbol"] * 8)
        строки += пачка("2026-08-29T09:30:00Z", [])                        # ответ без вызовов
        строки += пачка("2026-08-29T10:00:00Z", ["Grep"], sidechain=True)  # ветка подагента
        строки += ["", "{не json}"]
        путь.write_text("\n".join(строки) + "\n", encoding="utf-8")

        все = bw.ходы(путь, None, False)
        check("пачка собрана из разных записей", len(все) == 3, f"{len(все)}")
        check("ширины прочитаны", [ш for _, ш, _ in все] == [1, 3, 8],
              str([ш for _, ш, _ in все]))
        check("ответ без вызовов не считается",
              all(ш > 0 for _, ш, _ in все))
        check("ветка подагента исключена",
              all("Grep" not in и for _, _, и in все))

        с_веткой = bw.ходы(путь, None, True)
        check("с --subagents ветка возвращается", len(с_веткой) == 4, f"{len(с_веткой)}")

        поздние = bw.ходы(путь, "2026-08-29", False)
        check("--since отсекает по дате", len(поздние) == 1, f"{len(поздние)}")

        # Та же пачка, но записанная одной записью: обе формы должны читаться.
        путь2 = Path(tmp) / "s2.jsonl"
        путь2.write_text("\n".join(пачка("2026-08-28T12:00:00Z", ["a", "b", "c"],
                                         одной_записью=True)) + "\n", encoding="utf-8")
        одной = bw.ходы(путь2, None, False)
        check("слитная запись читается тоже",
              len(одной) == 1 and одной[0][1] == 3, str(одной))

        с = bw.свод(все)
        check("вызовов всего", с["вызовов"] == 12, str(с["вызовов"]))
        check("медиана", с["медиана"] == 3.0, str(с["медиана"]))
        check("среднее", с["среднее"] == 4.0, str(с["среднее"]))
        check("максимум", с["максимум"] == 8, str(с["максимум"]))
        check("доля одиночных", с["доля_одиночных"] == 33, str(с["доля_одиночных"]))
        check("одиночный виновник назван", с["одиночные"]["Bash"] == 1,
              str(dict(с["одиночные"])))
        check("гистограмма складывает 5+", с["гистограмма"]["5+"] == 1,
              str(dict(с["гистограмма"])))

        пусто = bw.свод([])
        check("пустой свод не падает", пусто["ходов"] == 0)
        check("медиана пустого — ноль", bw.медиана([]) == 0.0)
        check("медиана чётного — среднее середины", bw.медиана([1, 3]) == 2.0)

        check("выбор файлов берёт явный путь",
              bw.стенограммы([str(путь)], None) == [путь])
        check("--sessions режет хвост",
              bw.стенограммы([str(путь)], 1) == [путь])

    print(f"всего: {всего}   провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
