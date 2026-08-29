#!/usr/bin/env python3
"""Проверки крана строки состояния. Токенов не стоит.

Кран сидит на пути строки состояния — вещи владельца, — поэтому проверяется не
только то, что он считает, но и то, чего он НЕ делает: не глотает вход, не
печатает своего в stdout, не роняет строку, когда вход оказался мусором.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

КРАН = str(Path(__file__).resolve().parent / "cache-tap.py")
спец = importlib.util.spec_from_file_location("cache_tap", КРАН)
tap = importlib.util.module_from_spec(спец)
спец.loader.exec_module(tap)

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if условие:
        print(f"  ✓ {имя}")
    else:
        провалов += 1
        print(f"  ✗ {имя}  {подробность}")


def вход(запросов: int, чтение: int, **ещё) -> dict:
    д = {
        "session_id": "проба",
        "prompt_cache": {"requests": запросов, "hit_ratio": 0.9, "warm": True,
                         "ttl": "1h", "misses": 0},
        "context_window": {"used_percentage": 23,
                           "current_usage": {"cache_read_input_tokens": чтение}},
        "rate_limits": {"seven_day": {"used_percentage": 83},
                        "five_hour": {"used_percentage": 35}},
        "cost": {"total_cost_usd": 12.5},
        "model": {"id": "claude-opus-5[1m]"},
        "transcript_path": "/нет/такого.jsonl",
        "version": "2.1.251",
    }
    д.update(ещё)
    return д


print("счёт накопленного чтения")

пусто = tap.досчитать(вход(10, 200_000), {})
check("первый вход не начисляет ничего", пусто["всего_чтения"] == 0,
      str(пусто["всего_чтения"]))
check("счётчик запросов запомнен", пусто["запросов"] == 10)

шаг = tap.досчитать(вход(11, 200_000), пусто)
check("один запрос — одно чтение", шаг["всего_чтения"] == 200_000,
      str(шаг["всего_чтения"]))

# Строка состояния могла не рисоваться: окно не в фокусе, сессия в фоне. Тогда
# разница накопится, и умножить её надо на текущее чтение — оно за это время
# сдвинулось едва.
скачок = tap.досчитать(вход(15, 210_000), шаг)
check("пропущенные тики досчитываются разницей",
      скачок["всего_чтения"] == 200_000 + 4 * 210_000, str(скачок["всего_чтения"]))

назад = tap.досчитать(вход(2, 100_000), скачок)
check("счётчик пошёл назад — не начисляем задним числом",
      назад["всего_чтения"] == скачок["всего_чтения"], str(назад["всего_чтения"]))
check("новый счётчик запомнен", назад["запросов"] == 2)

# Числа кеша могут не приехать вовсе — вход соседней сессии, старая версия.
без_чисел = tap.досчитать({"session_id": "проба"}, шаг)
check("без чисел счёт не портится", без_чисел["всего_чтения"] == 200_000)
check("без чисел прежний счётчик сохраняется", без_чисел["запросов"] == 11)

print("\nчто снимается для хуков")
снимок = tap.досчитать(вход(11, 200_000), пусто)
check("предел недели снят", снимок["предел_недели"] == 83)
check("предел пяти часов снят", снимок["предел_пяти_часов"] == 35)
check("доля попаданий снята", снимок["доля_попаданий"] == 0.9)
check("окно в процентах снято", снимок["окно_процентов"] == 23)
check("стоимость снята", снимок["стоимость"] == 12.5)
check("время снятия проставлено", abs(снимок["снято"] - time.time()) < 5)

print("\nпередача вниз по течению")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    ниже = tmp / "ниже.sh"
    ниже.write_text("#!/bin/sh\ncat | tr -d '\\n' | wc -c\n", encoding="utf-8")
    ниже.chmod(0o755)
    среда = dict(os.environ, TMPDIR=str(tmp), CACHE_TAP_NEXT=str(ниже))
    полезное = json.dumps(вход(20, 300_000), ensure_ascii=False)

    р = subprocess.run([sys.executable, КРАН], input=полезное,
                       capture_output=True, text=True, env=среда)
    # Сравниваем БАЙТЫ, а не символы: `wc -c` считает байты, а в полезном
    # грузе кириллица. Первая редакция проверки сравнивала с длиной строки и
    # отбилась на ровном месте — 453 против 439.
    ждём = len(полезное.encode("utf-8"))
    check("вход доходит вниз целиком", р.stdout.strip() == str(ждём),
          f"{р.stdout.strip()!r} против {ждём}")
    check("кран своего в строку не печатает", "cache" not in р.stdout.lower(),
          р.stdout[:80])
    состояние = json.loads((tmp / "cache-tap" / "проба.json").read_text())
    check("состояние записано под id сессии", состояние["запросов"] == 20)

    # Мусор на входе не должен ни ронять кран, ни глушить строку состояния.
    р = subprocess.run([sys.executable, КРАН], input="это не json",
                       capture_output=True, text=True, env=среда)
    check("мусор на входе не роняет", р.returncode == 0, р.stderr[:80])
    check("мусор всё равно уходит вниз",
          р.stdout.strip() == str(len("это не json".encode("utf-8"))),
          р.stdout[:40])

    # Выключатель: чистая передача, состояние не трогается.
    было = (tmp / "cache-tap" / "проба.json").read_text()
    р = subprocess.run([sys.executable, КРАН], input=json.dumps(вход(99, 1)),
                       capture_output=True, text=True,
                       env=dict(среда, CACHE_TAP="off"))
    check("выключенный кран не пишет состояния",
          (tmp / "cache-tap" / "проба.json").read_text() == было)
    check("выключенный кран всё равно передаёт", р.stdout.strip() != "")

    # Сжатие обнулило контекст — значит и счёт. Без этого лесенка напоминаний
    # не сбросилась бы никогда: `requests` сжатие не трогает.
    р = subprocess.run([sys.executable, КРАН, "--reset"],
                       input=json.dumps({"session_id": "проба"}),
                       capture_output=True, text=True, env=среда)
    после = json.loads((tmp / "cache-tap" / "проба.json").read_text())
    check("сброс обнуляет счёт", после["всего_чтения"] == 0, str(после))
    check("сброс сохраняет счётчик запросов", после["запросов"] == 20)
    check("сброс помечен временем", isinstance(после.get("обнулено"), float))

    р = subprocess.run([sys.executable, КРАН, "--reset"],
                       input=json.dumps({"session_id": "которой-нет"}),
                       capture_output=True, text=True, env=среда)
    check("сброс неизвестной сессии не создаёт файла",
          not (tmp / "cache-tap" / "которой-нет.json").exists())

    # Сборщика строки может не быть вовсе — кран обязан промолчать, а не
    # свалиться с трассировкой в строку состояния.
    р = subprocess.run([sys.executable, КРАН], input=полезное,
                       capture_output=True, text=True,
                       env=dict(среда, CACHE_TAP_NEXT=str(tmp / "нет-такого")))
    check("без сборщика ниже — тихий ноль", р.returncode == 0 and not р.stdout,
          f"{р.returncode} {р.stdout[:40]}")

print(f"\nвсего: {всего}   провалов: {провалов}")
sys.exit(1 if провалов else 0)
