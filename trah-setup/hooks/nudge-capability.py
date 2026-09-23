#!/usr/bin/env python3
"""UserPromptSubmit: напомнить о способности, когда задача ровно под неё.

Замер 29.08 (десять приманок, по одной на способность) показал границу.
Инструмент, без которого цели не достичь, включается сам: браузер, context7,
поиск в сети, символьный слой Serena — пять попаданий из пяти. Способность,
которая лишь ОРГАНИЗУЕТ работу, выполнимую руками, не включается почти никогда.

Из пяти несработавших три оказались защитимым суждением — одна цель, один файл,
делегировать нечего. Два были настоящим промахом:

  * навык `security`: в приманке стояло «перед выкаткой проверь на дыры», а в
    описании навыка — «посмотри дыры» и «можно это выкатывать». Не сработал, и
    разбор руками занял 249 секунд, вчетверо дороже прочих приманок;
  * sequential-thinking: приманка была ровно из списка в брифе — перенос
    хранилища, радиус поражения, порядок миграции. Не сработал.

Отсюда устройство хука. Он НЕ решает за модель и ничего не блокирует: он
называет способность и требует явного выбора — позвать или сказать вслух,
почему делаешь сам. Молчаливый пропуск и есть то, что мы лечим.

Правила, которыми куплена точность:

  * приманки узкие. Ложная подсказка дороже пропущенной: `nudge-serena` уже
    отменял законную работу десятью способами, и это чинилось дольше, чем
    писалось;
  * sequential-thinking требует ДВУХ признаков сразу — слова о перемене и слова
    о последствиях — плюс длины задачи от двадцати слов. «Перенеси функцию в
    соседний файл, проверь зависимости» подсказки не заслуживает;
  * один раз за сессию на способность. Повтор в каждом ходе — это шум, который
    перестают читать;
  * задача, где способность уже названа, подсказки не получает.

Выключатель: NUDGE_CAPABILITY=off.
"""
import json
import os
import tempfile
import re
import sys
from pathlib import Path

СОСТОЯНИЕ = Path(os.environ["TMPDIR"] if os.path.isdir(os.environ.get("TMPDIR") or "") else tempfile.gettempdir()) / "nudge-capability"

БЕЗОПАСНОСТЬ = (
    "This task is a security pass. There is a skill for it — `security` — which "
    "scopes the work, models the threat, delegates the reading and triages what "
    "comes back; and an agent, `critical-reviewer`, which reads a named area and "
    "reports every defect it finds. Call one of them, or say in your answer why "
    "you are doing it by hand."
)

РАЗБОР = (
    "This task turns on consequences across more than one place. That is what "
    "sequential-thinking is for: it holds the chain of steps and lets you revise "
    "one without losing the rest. Call it, or say in your answer why you are "
    "reasoning without it."
)

# Признаки безопасности: каждый сам по себе достаточен, поэтому каждый узок.
_БЕЗОПАСНОСТЬ = [
    re.compile(r"провер\w*[^.\n]{0,40}безопасн", re.I),
    re.compile(r"(посмотр|поищ|найд|провер)\w*[^.\n]{0,30}дыр", re.I),
    re.compile(r"\bна дыры\b", re.I),
    re.compile(r"уязвим", re.I),
    re.compile(r"(аудит|разбор)[^.\n]{0,25}безопасн", re.I),
    re.compile(r"безопасн\w*[^.\n]{0,25}(аудит|разбор|провер)", re.I),
    re.compile(r"security\s+(review|audit|pass|check|scan)", re.I),
    re.compile(r"\b(pentest|vulnerabilit|exploitable)", re.I),
    re.compile(r"(check|audit|review)[^.\n]{0,40}(for )?(security|vulnerabilit)", re.I),
]

# Разбор последствий: нужны ОБА признака, иначе подсказка полезет на каждый
# перенос функции между файлами.
_ПЕРЕМЕНА = re.compile(
    r"(мигрир|миграц|перенес|перенос|перевест|перепис|замен|переход|рефактор|"
    r"разнест|раздел|объедин|выкин|снест|migrat|refactor|rewrit|replace|move)",
    re.I)
_ПОСЛЕДСТВИЯ = re.compile(
    r"(последств|сломает|отвалит|развалит|радиус|в каком порядке|порядок "
    r"(миграц|перенос)|кто (сейчас )?(читает|зовёт|зовет|использует|зависит)|"
    r"что зависит|blast radius|implication|what breaks|knock-on)",
    re.I)
СЛОВ_ДЛЯ_РАЗБОРА = 20

# Способность уже названа — молчим.
_НАЗВАНЫ = {
    "security": re.compile(
        r"(/security\b|навык\W{0,3}security|critical-reviewer|скан\w* безопасн)", re.I),
    "sequential": re.compile(
        r"(sequential[- ]?thinking|последовательн\w* мышлен)", re.I),
}


def режим() -> str:
    return (os.environ.get("NUDGE_CAPABILITY") or "on").strip().lower()


def подсказки(prompt: str) -> list:
    """Какие способности уместны здесь. Пустой список — молчание."""
    если_есть = []
    if any(p.search(prompt) for p in _БЕЗОПАСНОСТЬ):
        если_есть.append(("security", БЕЗОПАСНОСТЬ))
    if (len(prompt.split()) >= СЛОВ_ДЛЯ_РАЗБОРА
            and _ПЕРЕМЕНА.search(prompt) and _ПОСЛЕДСТВИЯ.search(prompt)):
        если_есть.append(("sequential", РАЗБОР))
    return [(имя, текст) for имя, текст in если_есть
            if not _НАЗВАНЫ[имя].search(prompt)]


def уже_сказано(session_id: str) -> set:
    файл = СОСТОЯНИЕ / f"{session_id or 'без-сессии'}.json"
    try:
        return set(json.loads(файл.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def запомнить(session_id: str, имена: set) -> None:
    файл = СОСТОЯНИЕ / f"{session_id or 'без-сессии'}.json"
    try:
        СОСТОЯНИЕ.mkdir(parents=True, exist_ok=True)
        файл.write_text(json.dumps(sorted(имена), ensure_ascii=False),
                        encoding="utf-8")
    except OSError:
        # Не смогли запомнить — подскажем ещё раз. Это дешевле, чем упасть.
        pass


def main() -> int:
    if режим() == "off":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    prompt = (payload.get("prompt") or "").strip()
    if not prompt or prompt.startswith("/"):
        return 0

    session_id = payload.get("session_id") or ""
    было = уже_сказано(session_id)
    новые = [(имя, текст) for имя, текст in подсказки(prompt) if имя not in было]
    if not новые:
        return 0

    запомнить(session_id, было | {имя for имя, _ in новые})
    sys.stdout.write("\n\n".join(текст for _, текст in новые) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
