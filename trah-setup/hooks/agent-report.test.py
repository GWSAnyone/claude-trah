#!/usr/bin/env python3
"""Проверки `agent-report.py`. Токенов не стоит.

Хук — единственное место, где карта картографа переживает сжатие. Промолчав,
он теряет её без следа; ошибившись с файлом, пишет второй отчёт на каждое
продолжение агента. Поэтому проверяется запись, дописывание, повтор и то, что
хук никогда не мешает остановке подагента.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "agent-report.py")

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


def транскрипт(каталог: str, агент: str, бриф: str, ответы: list, описание: str = "") -> str:
    путь = Path(каталог) / "subagents" / f"agent-{агент}.jsonl"
    путь.parent.mkdir(parents=True, exist_ok=True)
    строки = [{"type": "user", "message": {"role": "user", "content": бриф}}]
    for о in ответы:
        строки.append({"type": "assistant", "message": {"content": о}})
    путь.write_text("\n".join(json.dumps(с, ensure_ascii=False) for с in строки) + "\n",
                    encoding="utf-8")
    if описание:
        путь.with_suffix(".meta.json").write_text(
            json.dumps({"agentType": "senior-reviewer", "description": описание},
                       ensure_ascii=False), encoding="utf-8")
    return str(путь)


def run(cwd: str, агент: str, путь: str, последнее, режим: str | None = None,
        событие: str = "SubagentStop", сырьё: str | None = None,
        тип: str = "senior-reviewer"):
    env = dict(os.environ)
    if режим is None:
        env.pop("AGENT_REPORT", None)
    else:
        env["AGENT_REPORT"] = режим
    вход = сырьё if сырьё is not None else json.dumps({
        "cwd": cwd, "session_id": "сессия-1", "hook_event_name": событие,
        "agent_id": агент, "agent_type": тип,
        "agent_transcript_path": путь, "last_assistant_message": последнее},
        ensure_ascii=False)
    р = subprocess.run([sys.executable, HOOK], input=вход,
                       capture_output=True, text=True, env=env)
    return р.returncode, р.stdout, р.stderr


def отчёты(cwd: str) -> list[Path]:
    return sorted((Path(cwd) / ".claude" / "agent-reports").glob("*.md"))


def main() -> int:
    print("запись карты")
    with tempfile.TemporaryDirectory() as tmp:
        путь = транскрипт(tmp, "a1", "Составь карту модуля X", ["смотрю", "# Карта\nвсё"],
                          описание="Map module X")
        код, вых, ош = run(tmp, "a1", путь, "# Карта\nвсё")
        файлы = отчёты(tmp)
        check("код 0 и тишина", код == 0 and not вых.strip(), f"{код} {вых!r} {ош!r}")
        check("один файл", len(файлы) == 1, str(файлы))
        if файлы:
            т = файлы[0].read_text(encoding="utf-8")
            имя = файлы[0].name
            check("в имени тип, задача и id",
                  "senior-reviewer" in имя and "map-module-x" in имя and имя.endswith("-a1.md"), имя)
            check("бриф на месте", "Составь карту модуля X" in т, т)
            check("ответ целиком", "# Карта\nвсё" in т, т)
            check("в шапке путь к транскрипту", путь in т, т)
        игнор = Path(tmp) / ".claude" / "agent-reports" / ".gitignore"
        check("папка закрыта от git", игнор.exists() and игнор.read_text() == "*\n")

        код, вых, ош = run(tmp, "a1", путь, "# Карта\nвсё")
        check("повтор того же ответа не дописывается",
              файлы and файлы[0].read_text(encoding="utf-8").count("# Карта") == 1)

        код, вых, ош = run(tmp, "a1", путь, "Уточнение по Y")
        т = файлы[0].read_text(encoding="utf-8") if файлы else ""
        check("продолжение дописано в тот же файл",
              len(отчёты(tmp)) == 1 and "## Ответ — продолжение" in т and "Уточнение по Y" in т, т)

    print("ответа в событии нет")
    with tempfile.TemporaryDirectory() as tmp:
        путь = транскрипт(tmp, "b2", "бриф",
                          [[{"type": "text", "text": "последний текст"},
                            {"type": "tool_use", "name": "Read", "input": {}}],
                           [{"type": "tool_use", "name": "Read", "input": {}}]])
        run(tmp, "b2", путь, None)
        файлы = отчёты(tmp)
        check("ответ взят из транскрипта",
              len(файлы) == 1 and "последний текст" in файлы[0].read_text(encoding="utf-8"),
              str(файлы))

        путь = транскрипт(tmp, "c3", "бриф", [])
        run(tmp, "c3", путь, "")
        check("пустой ответ файла не даёт", len(отчёты(tmp)) == 1)

    print("чужие события и поломки")
    with tempfile.TemporaryDirectory() as tmp:
        путь = транскрипт(tmp, "d4", "бриф", ["ответ"])
        код, *_ = run(tmp, "d4", путь, "ответ", событие="Stop")
        check("Stop главной сессии не пишется", код == 0 and not отчёты(tmp))
        код, *_ = run(tmp, "d4", "/нет.jsonl", "угаданная реплика", тип="")
        check("служебный подагент без типа не пишется", код == 0 and not отчёты(tmp))
        код, *_ = run(tmp, "d4", путь, "ответ", режим="off")
        check("выключатель действует", код == 0 and not отчёты(tmp))
        код, вых, ош = run(tmp, "d4", путь, "ответ", сырьё="не json")
        check("мусор на входе — код 0", код == 0, ош)
        код, *_ = run(tmp, "d4", "/нет/такого.jsonl", "ответ")
        т = отчёты(tmp)[0].read_text(encoding="utf-8") if отчёты(tmp) else ""
        check("без транскрипта ответ всё равно сохранён", "ответ" in т and "(не найден)" in т, т)

    with tempfile.TemporaryDirectory() as tmp:
        занято = Path(tmp) / ".claude"
        занято.write_text("файл вместо каталога", encoding="utf-8")
        код, вых, ош = run(tmp, "e5", "/нет.jsonl", "ответ")
        check("не смог записать — код 0 и строка в stderr",
              код == 0 and "agent-report:" in ош, f"{код} {ош!r}")

    print(f"\nвсего: {всего}, провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    raise SystemExit(main())
