#!/usr/bin/env python3
"""PostCompact: после ЗАКАЗАННОГО сжатия вернуть сессию к работе.

Сжатие обрывает ход посередине дела. Дальше есть развилка, и она зависит от
того, КТО его заказал:

  * заказала сессия сама — значит она отложила незаконченный шаг и ждёт слова.
    Её надо вернуть к делу, иначе работа встанет до следующей реплики
    владельца, а он мог отойти;
  * нажал человек — он мог хотеть ровно обратного: перехватить и дать другую
    задачу. Подгонять работу здесь значит отнять у него эту возможность.

Различаются они меткой, которую `compact-order.py` кладёт рядом с чекпоинтом в
момент заказа. Метка есть и свежая — сжатие наше. Метки нет — молчим. Это
дословный перенос правила службы (`afterCompact` в `internal/httpapi/compact.go`,
поле `orderedBy`): там оно проверено работой, и переизобретать его незачем.

Метка съедается в любом случае, даже когда мы молчим: пролежав, она приписала
бы нам следующее сжатие, которого мы не заказывали.

Выключатель: COMPACT_CONTINUE=off.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ХУКИ = Path(os.environ.get("TRAH_HOOKS_DIR", str(Path(__file__).resolve().parent)))
sys.path.insert(0, str(ХУКИ))
import sockmsg  # noqa: E402

# Сколько метка считается нашей. Сжатие идёт минуты, но не часы: пролежавшая
# дольше метка — след заказа, который до сжатия так и не дошёл (например, его
# отбил сторож чекпоинта), и приписывать ей чужое сжатие нельзя.
СВЕЖЕСТЬ_СЕК = 15 * 60


def чекпоинт_модуль():
    путь = ХУКИ / "checkpoint.py"
    if not путь.exists():
        return None
    спец = importlib.util.spec_from_file_location("checkpoint_hook", путь)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def сообщение(данные: dict | None) -> str:
    строки = [
        "The context has been compacted: the conversation is folded into a "
        "summary. You ordered this yourself — the work is not lost.",
    ]
    if данные:
        строки += [
            "",
            f"Plan:        {данные.get('plan', '—')}",
            f"Next action: {данные.get('next', '—')}",
        ]
    строки += [
        "",
        "Carry on from that step: finish it and report. Do not start over and "
        "do not re-read files the summary already covers. This message needs "
        "no answer of its own.",
    ]
    return "\n".join(строки)


def main() -> int:
    if os.environ.get("COMPACT_CONTINUE") == "off":
        return 0
    try:
        полезное = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    cwd = полезное.get("cwd") or os.getcwd()
    session_id = полезное.get("session_id", "")

    cp = чекпоинт_модуль()
    if cp is None:
        return 0
    метка = Path(cwd) / ".claude" / f".compact-ordered-{cp.suffix_for(session_id)}"
    try:
        возраст = time.time() - метка.stat().st_mtime
    except OSError:
        return 0  # метки нет — сжатие не наше, работу не подгоняем
    try:
        метка.unlink()
    except OSError:
        pass
    if возраст > СВЕЖЕСТЬ_СЕК:
        return 0

    данные = cp.load(cp.resolve_checkpoint(cwd, session_id))
    беда = sockmsg.послать(сообщение(данные))
    if беда:
        sys.stderr.write(f"compact-continue: {беда}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
