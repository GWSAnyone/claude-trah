#!/usr/bin/env python3
"""Прогон проба-мода: что из меток мода доехало до модели.

    run.py [ВЕРСИЯ] [--debug]           в ловушку sink.py, ноль токенов
    run.py [ВЕРСИЯ] --relay [--debug]   через relay.py, НАСТОЯЩИЕ токены

Ловушка отвечает отказом, поэтому видно только первый запрос главного цикла.
Подагент и сжатие случаются после ответа модели — для них `--relay`: два шага в
одной сессии, «запусти подагента» и затем `/compact`, и разбор каждого запроса.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ЗДЕСЬ = Path(__file__).resolve().parent
КОРЕНЬ = ЗДЕСЬ.parent.parent
версия = next((a for н, a in enumerate(sys.argv[1:], 1)
               if not a.startswith("-") and sys.argv[н - 1] not in ("--model", "--plugin")), "2.1.287")
бинарь = Path.home() / ".local/share/claude/versions" / версия
ЖИВОЙ = "--relay" in sys.argv
ПОРТ = 8780 if ЖИВОЙ else 8779
МЕТКИ = ["MARK-COMPOSE", "MARK-SECTION", "MARK-TOOL-BASH", "MARK-ATT-", "MARK-ATTR-",
         "MARK-CONTEXT", "MARK-SPAWN", "MARK-COMPACT"]
ЗАДАЧА_ПОДАГЕНТУ = ("Вызови инструмент Agent с subagent_type general-purpose и заданием "
                    "«ответь одним словом: сколько будет 2+2». Сам больше ничего не делай.")

блокнот = Path(tempfile.mkdtemp(prefix="trah-probe-"))
улов, журнал = блокнот / "sink.jsonl", блокнот / "log.json"
посредник = КОРЕНЬ / ("dev/relay.py" if ЖИВОЙ else "trah-setup/bin/sink.py")
ловушка = subprocess.Popen([sys.executable, str(посредник), str(ПОРТ), str(улов)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
# `--plugin КАТАЛОГ` — вместо проба-мода собранный мод trah; его журнал — TRAH_MOD_LOG.
мод = Path(sys.argv[sys.argv.index("--plugin") + 1]).expanduser() if "--plugin" in sys.argv else ЗДЕСЬ
# Свой каталог конфига с включённым флагом модов — см. `trah.py` › тестовое_окружение.
_спец = importlib.util.spec_from_file_location("trah", КОРЕНЬ / "trah-setup/bin/trah.py")
trah = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(trah)
окружение = {**trah.тестовое_окружение(), "ENABLE_TOOL_SEARCH": "1", "TRAH_PROBE_LOG": str(журнал),
             "TRAH_MOD_LOG": str(журнал),
             "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{ПОРТ}"}
сессия = str(uuid.uuid4())
# Модель: в ловушку — Opus 5 (токенов не стоит, а от модели зависит состав
# промпта: на нём lean). Живой прогон — Sonnet: владелец, 02.10, «старайся не
# гонять опус, только соннет или хайку, если только тест не подразумевает
# проверку конкретно опуса». `--model X` перебивает.
модель = (sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv
          else "sonnet" if ЖИВОЙ else "claude-opus-5")
# Без пользовательских настроек: иначе в пробе работают живые хуки комплекта.
# 02.10 сторож чекпоинта отбил `/compact` пробы — «контрольной точки нет».
основа = [str(бинарь), "--setting-sources", "project,local",
          "--plugin-dir", str(мод), "--model", модель,
          *(["--debug"] if "--debug" in sys.argv else [])]
if "--compact-file" in sys.argv:
    (блокнот / "CLAUDE.md").write_text("# Проба\nПравило пробы: отвечай коротко.\n")
    (блокнот / "notes.txt").write_text("заметка пробы\n" * 50)
шаги = ([[*основа, "--print", "/goal Ответь, сколько будет 2+2, и на этом всё."]]
        if "--goal" in sys.argv else
        [[*основа, "--session-id", сессия, "--print",
          "Прочитай инструментом Read файлы notes.txt и CLAUDE.md, больше ничего."],
         [*основа, "--resume", сессия, "--print", "/compact"],
         [*основа, "--resume", сессия, "--print", "Сколько будет 2+2?"]]
        if "--compact-file" in sys.argv else
        [[*основа, "--session-id", сессия, "--print", ЗАДАЧА_ПОДАГЕНТУ],
         [*основа, "--resume", сессия, "--print", "/compact"]] if ЖИВОЙ
        else [[*основа, "--print", "2+2"]])
вывод = []
try:
    time.sleep(1)
    for шаг in шаги:
        г = subprocess.run(шаг, env=окружение, capture_output=True, text=True,
                           timeout=600, cwd=блокнот)
        вывод.append(f"$ {' '.join(шаг[-2:])}\nкод {г.returncode}\n{г.stderr}\n--- stdout\n{г.stdout}")
finally:
    ловушка.terminate()
    ловушка.wait(timeout=10)
(блокнот / "stderr.txt").write_text("\n\n".join(вывод))

запросы = []
for строка in улов.read_text().splitlines() if улов.exists() else []:
    тело = json.loads(строка).get("body") or {}
    if "messages" in тело:
        запросы.append(тело)

print(f"версия {версия}, {'relay' if ЖИВОЙ else 'sink'}, запросов к модели {len(запросы)}, блокнот {блокнот}")
итого = {м: set() for м in МЕТКИ}
for н, тело in enumerate(запросы):
    система = json.dumps(тело.get("system"), ensure_ascii=False)
    сообщения = json.dumps(тело.get("messages"), ensure_ascii=False)
    имена = [t["name"] for t in тело.get("tools") or []]
    кто = ("сжатие" if "summar" in система.lower() and not имена else
           "главный" if "Agent" in имена else "подагент?")
    есть = []
    for м in МЕТКИ:
        где = [п for п, т in (("sys", система), ("msg", сообщения),
                               ("tools", json.dumps(тело.get("tools"), ensure_ascii=False))) if м in т]
        if где:
            есть.append(f"{м}[{','.join(где)}]")
            итого[м].add(кто)
    print(f"  #{н} {кто:<9} {тело.get('model')} tools={len(имена)} sys={len(система)} "
          f"msgs={len(тело.get('messages') or [])}: {' '.join(есть) or '—'}")
for м, кто in итого.items():
    print(f"  {'✓' if кто else '✗'} {м:<16} {', '.join(sorted(кто)) or 'не доехала'}")
события = json.loads(журнал.read_text()) if журнал.exists() else []
if isinstance(события, dict):  # журнал мода trah: {кусок: {пришло, легло}}
    print("журнал мода:", json.dumps(события, ensure_ascii=False))
    sys.exit(0)
счёт: dict[str, int] = {}
for с in события:
    счёт[с["событие"]] = счёт.get(с["событие"], 0) + 1
print("журнал мода:", json.dumps(счёт, ensure_ascii=False))
