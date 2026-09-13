#!/usr/bin/env python3
"""Stop-хук: ход кончился обещанием вернуться, а будить сессию нечему.

Владелец 13.09.2026: сессия «кучу раз» писала, что ждёт события, и отдавала ход,
вместо того чтобы поставить Monitor. Замер по Э3 (08–13.09): 14 ходов кончились
словами «жду его», «доложу», «вернусь» без единого вызова в последнем сообщении,
и около девяти из них ждали события живого бота — тика, подтверждения листинга,
истечения срока. Проснуться сама сессия не может, и пинать её приходилось
владельцу. Monitor она при этом знала (34 вызова), фоновый Bash тоже (14).

Гард на sleep этот случай не видит: там ожидание внутри команды, а здесь ход
просто закончился.

Stop приносит `last_assistant_message`, `background_tasks` и `session_crons`.
Есть фоновая работа или будильник — разбудить есть кому, молчим. Иначе в тексте
ищется обещание вернуться самой. Ожидание ответа владельца обещанием не
считается, и ход, кончившийся вопросом, тоже: там ход честно отдан человеку.
Нашли — отказ в остановке с указанием, что делать. Второй раз за ход хук не
срабатывает (`stop_hook_active`), так что цена ложного срабатывания — один ход.
"""

import json
import os
import re
import sys

ОБЕЩАНИЕ = re.compile(
    r"\b(?:жду|ждём|ждем|дождусь|дожидаюсь|подожду)\s+(?:"
    r"его|её|ее|их|в\s+фоне|подтвержд\w*|истечени\w*|тик\w*|событи\w*|срабатыв\w*|"
    r"следующ\w*\s+(?:тик|событ|круг|прогон|попытк|такт)\w*|"
    r"результат\w*|окончани\w*|завершени\w*)"
    r"|\bдоложу\b|\bвернусь\s+с\b|\bотпишусь\b|\bсмотрю\s+за\s+этим\b"
    r"|\bI(?:'ll|\s+will)\s+(?:report\s+back|check\s+back|come\s+back)\b"
    r"|\bwaiting\s+for\s+(?:it|the\s+next)\b",
    re.IGNORECASE,
)

ПРИЧИНА = (
    "You ended the turn promising to come back when something happens, but nothing "
    "is registered to wake you: no background task, no scheduled wake-up. The owner "
    "would have to nudge you. Start the Monitor tool with an until-loop on that "
    "condition, or run the wait with run_in_background, and end the turn after that. "
    "If it is the owner who has to come back, say so plainly instead."
)


# Цитата — не обещание. 13.09.2026 хук остановил отчёт, который ПЕРЕЧИСЛЯЛ
# пойманные в Э3 фразы: «Жду её», «Ждём истечения» стояли в кавычках как примеры.
ЦИТАТА = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"\n]*\"|`[^`\n]*`")


def обещание(текст: str) -> bool:
    строки = [с.strip() for с in текст.strip().splitlines() if с.strip()]
    if not строки or строки[-1].endswith("?"):
        return False
    return ОБЕЩАНИЕ.search(ЦИТАТА.sub("", текст)) is not None


def решение(payload: dict) -> str | None:
    """Причина отказа в остановке, или None — остановиться можно."""
    if payload.get("stop_hook_active"):
        return None
    if payload.get("background_tasks") or payload.get("session_crons"):
        return None
    текст = payload.get("last_assistant_message")
    if not isinstance(текст, str) or not обещание(текст):
        return None
    return ПРИЧИНА


def main() -> int:
    if os.environ.get("NUDGE_WAIT") == "off":
        return 0
    try:
        payload = json.load(sys.stdin)
        причина = решение(payload) if isinstance(payload, dict) else None
    except Exception:
        return 0
    if причина:
        json.dump({"decision": "block", "reason": причина}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
