#!/usr/bin/env python3
"""SubagentStop: итоговый ответ каждого подагента — ещё и в файл.

Ответ подагента приходит главной сессии сообщением и живёт ровно до сжатия:
в сводке от карты на двадцать тысяч символов остаются две строки, и вернуться
к ней нечем. Файл пишут только те, кому это велено и дан Write (researcher,
critical-reviewer). Картограф `senior-reviewer` намеренно только читает — и по
транскриптам этой машины на 29.09.2026 ни одна из его 73 карт не легла на диск.
Давать ему Write ради архива значит отнять у него гарантию «ничего не правлю»,
поэтому пишет не он, а этот хук.

Куда: `<cwd сессии>/.claude/agent-reports/<дата>-<время>-<тип>-<задача>-<id>.md`.
Внутри шапка, бриф (первое сообщение подагенту) и ответ целиком. У тех, кто
сам пишет отчёт, сюда ляжет выжимка со ссылкой на него — дубль дешёвый, зато
в одной папке лежит каждый запуск.

Подагент, продолженный через SendMessage, останавливается снова с тем же id:
новый ответ дописывается в тот же файл, повтор того же текста — нет.

Хук ничего не блокирует и ничего не говорит: код выхода всегда 0. Отказ
записать — строка в stderr, работа подагента от этого не зависит.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ПАПКА = Path(".claude") / "agent-reports"


def текст(содержимое) -> str:
    if isinstance(содержимое, str):
        return содержимое
    return "\n".join(ч.get("text", "") for ч in содержимое or []
                     if isinstance(ч, dict) and ч.get("type") == "text")


def из_транскрипта(путь: str) -> tuple[str, str]:
    """Бриф и последний текст подагента — на случай, если события мало."""
    бриф, последний = "", ""
    try:
        строки = open(путь, encoding="utf-8").readlines()
    except OSError:
        return бриф, последний
    for строка in строки:
        try:
            з = json.loads(строка)
        except ValueError:
            continue
        сообщение = з.get("message") or {}
        if з.get("type") == "user" and not бриф:
            бриф = текст(сообщение.get("content")).strip()
        elif з.get("type") == "assistant":
            т = текст(сообщение.get("content")).strip()
            if т:
                последний = т
    return бриф, последний


def описание(путь: str) -> str:
    try:
        return json.load(open(re.sub(r"\.jsonl$", ".meta.json", путь))).get("description", "")
    except (OSError, ValueError, AttributeError):
        return ""


def слаг(с: str) -> str:
    return re.sub(r"[^\w]+", "-", с.lower()).strip("-")[:40].strip("-")


def main() -> int:
    if os.environ.get("AGENT_REPORT") == "off":
        return 0
    try:
        п = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    # Пустой тип — служебный подагент самого CLI, а не вызов Agent: 29.09.2026
    # такой пришёл без транскрипта и с угаданной следующей репликой владельца
    # вместо ответа.
    if п.get("hook_event_name") != "SubagentStop" or not п.get("agent_id") \
            or not п.get("agent_type"):
        return 0

    агент = п["agent_id"]
    тип = п["agent_type"]
    транскрипт = п.get("agent_transcript_path") or ""
    бриф, последний = из_транскрипта(транскрипт)
    ответ = (п.get("last_assistant_message") or "").strip() or последний
    if not ответ:
        return 0
    задача = описание(транскрипт)

    папка = Path(п.get("cwd") or os.getcwd()) / ПАПКА
    try:
        папка.mkdir(parents=True, exist_ok=True)
        # Архив машины, не проекта: в чужой репозиторий он не должен уехать,
        # а трогать чужой .gitignore комплект не вправе.
        игнор = папка / ".gitignore"
        if not игнор.exists():
            игнор.write_text("*\n", encoding="utf-8")

        прежние = sorted(папка.glob(f"*-{агент}.md"))
        сейчас = time.strftime("%Y-%m-%d %H:%M")
        if прежние:
            файл = прежние[0]
            if файл.read_text(encoding="utf-8").rstrip().endswith(ответ):
                return 0
            with файл.open("a", encoding="utf-8") as f:
                f.write(f"\n## Ответ — продолжение, {сейчас}\n\n{ответ}\n")
            return 0

        имя = "-".join(ч for ч in (time.strftime("%Y-%m-%d-%H%M"), слаг(тип),
                                    слаг(задача), агент) if ч)
        шапка = [f"# {тип}" + (f" — {задача}" if задача else ""), "",
                 f"- время: {сейчас}",
                 f"- агент: {агент}",
                 f"- сессия: {п.get('session_id', '')}",
                 f"- транскрипт: {транскрипт}", ""]
        тело = "\n".join(шапка) + f"\n## Бриф\n\n{бриф or '(не найден)'}\n\n## Ответ\n\n{ответ}\n"
        (папка / f"{имя}.md").write_text(тело, encoding="utf-8")
    except OSError as беда:
        sys.stderr.write(f"agent-report: {беда}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
