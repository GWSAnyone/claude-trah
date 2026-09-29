#!/usr/bin/env python3
"""Проверки `nudge-wait.py`. Токенов не стоит.

Обещания взяты дословно из стенограммы Э3 (08–13.09.2026), молчание — из тех же
ходов, где сессия честно отдавала ход владельцу.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


путь = Path(__file__).resolve().parent / "nudge-wait.py"
спец = importlib.util.spec_from_file_location("nudge_wait", str(путь))
хук = importlib.util.module_from_spec(спец)
спец.loader.exec_module(хук)

ОБЕЩАНИЯ = [
    "Тик 13:51:25 прошёл раньше — команды уйдут следующим. Жду его в фоне и вернусь с проверкой.",
    "Следующий же тик отправил выставление за 3¢. Жду подтверждения листинга, дальше две минуты и истечение.",
    "Срок машина поставила на 14:32 UTC. Ждём истечения.",
    "Наблюдаю. Лот пока стоит — снятие уйдёт ближайшим тиком, доложу как отработает.",
    "Следующая попытка назначена на 18:54:03. Жду её.",
    "Пока ничего: круг монитора ещё не наступил. Жду следующего события.",
    "Картина должна выправиться к ~22:56. Смотрю за этим, доложу числами.",
    "Deployed. I'll report back once the health check turns green.",
]
МОЛЧАНИЕ = [
    "Витрина крутится с пересборки 20:50. Жду следующий пункт по модалке правила.",
    "Останавливаюсь на выборе предмета — жду твоего решения.",
    "Правило включено. Доложу, когда увижу срабатывание, или сразу перезапускать бота?",
    "**Итог** Бот пересобран и здоров. Вопросов нет.",
    "Вернусь к нему сам только когда включится правило слива.",
    "Хук остановил бы 6: «Жду подтверждения листинга», «Ждём истечения», «Жду её».",
    "Пример из стенограммы: `доложу числами` и \"жду его семь замеров\".",
    "",
]

for текст in ОБЕЩАНИЯ:
    check(f"обещание: {текст[:50]}", хук.решение({"last_assistant_message": текст}) is not None)
for текст in МОЛЧАНИЕ:
    check(f"молчит: {текст[:50]}", хук.решение({"last_assistant_message": текст}) is None)

обещание = ОБЕЩАНИЯ[0]
check("фоновая задача есть — молчит",
      хук.решение({"last_assistant_message": обещание, "background_tasks": [{"id": "m1"}]}) is None)
check("будильник есть — молчит",
      хук.решение({"last_assistant_message": обещание, "session_crons": [{"id": "c1"}]}) is None)
check("второй заход за ход — молчит",
      хук.решение({"last_assistant_message": обещание, "stop_hook_active": True}) is None)
check("пустые списки не спасают",
      хук.решение({"last_assistant_message": обещание, "background_tasks": [],
                   "session_crons": []}) is not None)
check("текста нет — молчит", хук.решение({}) is None)

спец_cp = importlib.util.spec_from_file_location("checkpoint_hook", str(путь.parent / "checkpoint.py"))
CP = importlib.util.module_from_spec(спец_cp)
спец_cp.loader.exec_module(CP)
with tempfile.TemporaryDirectory() as каталог:
    сессия = "87b3fb09-7ae3-4107-ac55-1e34157058e4"
    заказ = {"last_assistant_message": обещание, "cwd": каталог, "session_id": сессия}
    check("метки заказа нет — отказ", хук.решение(заказ) is not None)
    метка = Path(CP.compact_order_path(каталог, сессия))
    метка.parent.mkdir()
    метка.write_text("2026-09-29T15:18:36\n", encoding="utf-8")
    check("сжатие заказано — молчит", хук.решение(заказ) is None)
    check("метка чужой сессии не спасает",
          хук.решение({**заказ, "session_id": "e0063367-dd45"}) is not None)
    давно = time.time() - хук.СЖАТИЕ_СЕК - 60
    os.utime(метка, (давно, давно))
    check("протухшая метка не спасает", хук.решение(заказ) is not None)


def прогнать(сырьё: str) -> tuple[int, str]:
    прежний, вывод = sys.stdin, io.StringIO()
    sys.stdin = io.StringIO(сырьё)
    прежний_out, sys.stdout = sys.stdout, вывод
    try:
        return хук.main(), вывод.getvalue()
    finally:
        sys.stdin, sys.stdout = прежний, прежний_out


код, вывод = прогнать(json.dumps({"last_assistant_message": обещание}))
ответ = json.loads(вывод) if вывод else {}
check("отказ в остановке — JSON decision block",
      код == 0 and ответ.get("decision") == "block" and "Monitor" in ответ.get("reason", ""), вывод[:100])
check("молчание — пустой вывод", прогнать(json.dumps({"last_assistant_message": "Готово."})) == (0, ""))
check("мусор — выход 0 и тишина", прогнать("не json") == (0, ""))

print(f"  {всего - провалов}/{всего} проверок прошло")
sys.exit(1 if провалов else 0)
