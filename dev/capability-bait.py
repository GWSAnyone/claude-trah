#!/usr/bin/env python3
"""Калибровка оснастки: включается ли способность, когда она очевидно уместна.

Замер отвечает на вопрос, которого не видит ни одна мерка по стенограммам:
УМЕЕТ ли модель пользоваться тем, что ей поставили. Стенограммы показывают
только то, что случилось, и молчат о том, была ли задача поводом.

Устройство. Десять задач-приманок, по одной на способность. Каждая
сформулирована так, что нужная способность — прямое попадание, а дешёвый обход
рядом и соблазнителен. Меряем ровно одно: какие инструменты сработали. Две
приманки контрольные: там правильный ответ «сделай сам», и они ловят ложные
срабатывания — без них замер награждал бы за суету.

Что показал первый прогон 29.08 (2.1.247, сборка режима):

  сработало 5 из 10. Включились ровно те способности, без которых цели не
  достичь: браузер, context7, поиск в сети, символьный слой. Не включилась ни
  одна из тех, что лишь ОРГАНИЗУЮТ выполнимую руками работу — ни агент, ни
  навык `security`, ни sequential-thinking. Ложных срабатываний ноль: на
  пустяковый вопрос ушёл один вызов за девять секунд.

Оговорка, без которой числа врут: в двух сработавших приманках подсказка
подсунута словами задачи — «своими глазами», «не по памяти». Без таких слов
инструмент мог бы и не включиться.

Запуск:
    capability-bait.py                       # все десять
    capability-bait.py --only безопасность   # выбранные, через запятую
    capability-bait.py --project ~/другой    # в другом дереве
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

СБОРКИ = Path.home() / ".local/share/claude/trah"
УЛОВ = Path(os.environ.get("TMPDIR", "/tmp")) / "capability-bait"
ТАЙМАУТ = 480

СТРАНИЦА = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>карточка</title>
<style>
  body { font: 16px/1.5 system-ui; background: #f4f4f6; padding: 40px; }
  .card { width: 320px; background: #fff; border-radius: 12px; padding: 24px;
          box-shadow: 0 2px 8px rgba(0,0,0,.12); overflow: visible; }
  .card h2 { margin: 0 0 12px; font-size: 20px; }
  .btn { position: relative; left: 210px; width: 180px; padding: 12px 20px;
         background: #2b6cb0; color: #fff; border: 0; border-radius: 8px; }
</style></head>
<body>
  <div class="card">
    <h2>Подписка</h2>
    <p>Продлевается каждый месяц, отменить можно в любой момент.</p>
    <button class="btn">Оформить</button>
  </div>
</body></html>
"""


def приманки(страница: Path) -> list:
    """Имя, ожидаемое (подстроки в именах инструментов и типах агентов), задача."""
    return [
        (
            "поиск-веером",
            ["Explore", "Agent"],
            "Где в этом дереве проверяется согласие владельца на коммит? Нужен "
            "список файл:строка по всем каталогам сразу — cmd/, internal/, "
            "tools/, trah-setup/. Содержимое файлов мне не нужно, нужен "
            "перечень мест. Ничего не правь.",
        ),
        (
            "понять-устройство",
            ["senior-reviewer", "Agent"],
            "Объясни, как устроена сборка режима: что происходит от команды "
            "`trah.py build` до готового бинарника, какие куски куда кладутся и "
            "где стыки, на которых это ломается. Мне нужна картина целиком, а "
            "не пересказ кода. Ничего не правь.",
        ),
        (
            "безопасность",
            ["critical-reviewer", "security", "scan-", "Agent", "Skill"],
            "Перед выкаткой проверь на дыры хук "
            "trah-setup/hooks/guard-destructive.py — он решает, пускать ли "
            "разрушительную команду, и обойти его нельзя. Найди, чем его можно "
            "обмануть. Ничего не правь, доложи находки.",
        ),
        (
            "написать-тесты",
            ["test-writer", "Agent"],
            "Напиши тесты для trah-setup/bin/count-bullet.py в том стиле, в "
            "каком написаны соседние тесты в этом каталоге, и оставь их зелёными.",
        ),
        (
            "браузер",
            ["playwright", "browser", "Skill"],
            f"Открой {страница} — там кнопка вылезает за край карточки. "
            "Посмотри своими глазами, что именно съехало, и скажи, какое "
            "правило это чинит. Файл не правь, просто разберись.",
        ),
        (
            "документация",
            ["context7"],
            "В Pydantic v2 чем заменили декоратор @validator из первой версии, "
            "как теперь выглядит сигнатура и что стало с параметром `always`? "
            "Нужна точность по текущей версии, а не по памяти.",
        ),
        (
            "разбор-последствий",
            ["sequential-thinking"],
            "Мы думаем перенести хранение чекпоинтов из файла "
            ".claude/.checkpoint-* в sqlite. Разбери последствия: кто сейчас "
            "читает указатель, что сломается при переносе, в каком порядке "
            "мигрировать и где потеряем восстановление после сжатия. Ничего не "
            "правь.",
        ),
        (
            "символьный (контроль+)",
            ["mcp__serena__find_symbol", "mcp__serena__find_referencing_symbols"],
            "Что делает функция _owner_consented в "
            "trah-setup/hooks/guard-destructive.py и кто её вызывает? Ничего не правь.",
        ),
        (
            "мелочь (контроль−)",
            [],
            "Сколько строк в trah-setup/README.md и какого числа он менялся в "
            "последний раз по git?",
        ),
        (
            "наружу",
            ["WebSearch", "WebFetch"],
            "Вышла ли уже стабильная Go 1.26 и что в ней изменилось в сборщике "
            "мусора? Нужно текущее положение дел, а не память.",
        ),
    ]


def сборка() -> str:
    """Та же сборка, что запускает обёртка: `trah/current`, иначе новейшая."""
    cur = СБОРКИ / "current"
    if cur.exists():
        return str(cur.resolve())
    версии = sorted(d for d in СБОРКИ.iterdir() if not d.name.endswith(".json"))
    return str(версии[-1])


def прогон(бинарь: str, проект: str, имя: str, ожидание: list, задача: str) -> dict:
    файл = УЛОВ / f"{имя.replace(' ', '_')}.jsonl"
    начало = time.time()
    оборвано = False
    try:
        г = subprocess.run(
            [бинарь, "--print", "--output-format", "stream-json", "--verbose",
             "--model", "claude-opus-5", "--permission-mode", "bypassPermissions",
             задача],
            cwd=проект, capture_output=True, text=True, timeout=ТАЙМАУТ,
        )
        вывод = г.stdout
    except subprocess.TimeoutExpired as e:
        сырое = e.stdout or ""
        вывод = сырое.decode("utf-8", "replace") if isinstance(сырое, bytes) else сырое
        оборвано = True
    файл.write_text(вывод, encoding="utf-8")

    инструменты = collections.Counter()
    агенты = collections.Counter()
    навыки = collections.Counter()
    токенов = слов = 0
    for строка in вывод.splitlines():
        строка = строка.strip()
        if not строка:
            continue
        try:
            з = json.loads(строка)
        except json.JSONDecodeError:
            continue
        с = з.get("message") or {}
        if з.get("type") != "assistant" or not isinstance(с.get("content"), list):
            continue
        токенов += int((с.get("usage") or {}).get("output_tokens") or 0)
        for б in с["content"]:
            if not isinstance(б, dict):
                continue
            if б.get("type") == "tool_use":
                инструменты[б.get("name") or "?"] += 1
                вх = б.get("input") or {}
                if б.get("name") in ("Agent", "Task"):
                    агенты[вх.get("subagent_type") or "(без типа)"] += 1
                elif б.get("name") == "Skill":
                    навыки[вх.get("skill") or "(без имени)"] += 1
            elif б.get("type") == "text":
                слов += len((б.get("text") or "").split())

    поле = " ".join(list(инструменты) + list(агенты) + list(навыки))
    if ожидание:
        попал = any(о.lower() in поле.lower() for о in ожидание)
    else:
        # Контроль−: попаданием считается ОТСУТСТВИЕ тяжёлой машинерии.
        попал = not (агенты or навыки
                     or any(n.startswith("mcp__sequential") for n in инструменты))
    return {
        "имя": имя, "попал": попал, "оборвано": оборвано,
        "инструменты": dict(инструменты.most_common()),
        "агенты": dict(агенты), "навыки": dict(навыки),
        "вызовов": sum(инструменты.values()), "токенов": токенов, "слов": слов,
        "секунд": round(time.time() - начало),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="имена приманок через запятую")
    ap.add_argument("--jobs", type=int, default=3, help="сколько прогонов разом")
    ap.add_argument("--project", default=os.getcwd(), help="дерево, в котором работать")
    a = ap.parse_args()

    УЛОВ.mkdir(parents=True, exist_ok=True)
    страница = УЛОВ / "страница.html"
    страница.write_text(СТРАНИЦА, encoding="utf-8")

    бинарь = сборка()
    набор = приманки(страница)
    if a.only:
        нужные = {x.strip() for x in a.only.split(",")}
        набор = [п for п in набор if п[0] in нужные]
    print(f"сборка: {бинарь}\nдерево: {a.project}\n"
          f"приманок: {len(набор)}, по {a.jobs} разом\n", flush=True)

    итоги = []
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        фьючи = [pool.submit(прогон, бинарь, a.project, *п) for п in набор]
        for ф in фьючи:
            и = ф.result()
            итоги.append(и)
            print(f"  [{'ДА' if и['попал'] else 'нет':>3}] {и['имя']:22} "
                  f"вызовов {и['вызовов']:3d}  {и['секунд']:3d}с  "
                  f"агенты={и['агенты'] or '—'}  навыки={и['навыки'] or '—'}"
                  f"{'  ОБОРВАНО' if и['оборвано'] else ''}", flush=True)

    (УЛОВ / "итоги.json").write_text(
        json.dumps(итоги, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 78)
    print(f"{'приманка':24} {'сраб':>5} {'вызовов':>8} {'сек':>5}  чем работала")
    for и in итоги:
        топ = ", ".join(f"{n}:{k}" for n, k in list(и["инструменты"].items())[:5])
        print(f"{и['имя']:24} {'ДА' if и['попал'] else 'нет':>5} "
              f"{и['вызовов']:>8} {и['секунд']:>5}  {топ}")
    print(f"\nсработало {sum(1 for и in итоги if и['попал'])} из {len(итоги)}")
    print(f"улов: {УЛОВ}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
