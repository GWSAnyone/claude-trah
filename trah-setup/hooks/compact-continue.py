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

# Stop: дать заказу исполниться

Заказ стоит в очереди и разбирается, когда ход кончился. При активном `/goal`
ход не кончается: цель — это Stop-хук с оценщиком, его «не выполнено» —
блокирующая ошибка, и CLI продолжает ход с ней вместо того, чтобы разобрать
очередь. Сжатие ждало, пока цель не будет достигнута, то есть не наступало
именно тогда, когда контекст рос дольше всего.

Лечится `continue:false` из Stop-хука. В CLI 2.1.284 остановка хуком
проверяется РАНЬШЕ блокирующих ошибок (`if(A)return …preventContinuation:!0`
стоит перед `if(ve.length>0)return{blockingErrors:ve…}`), поэтому она
побеждает отказ оценщика. Цель при этом не снимается: `activeGoal` меняют
только «достигнута», «невыполнима» и ручная отмена. После сжатия этот же хук на
PostCompact возвращает сессию к работе, и следующий конец хода снова идёт к
оценщику.

Держим ход один раз на заказ: в метку дописывается `held`, а время изменения
возвращается прежним, потому что по нему PostCompact судит о свежести. Без
этого заказ, который сторож чекпоинта отбил, обрывал бы каждый ход цели, пока
метка не протухнет.

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
#
# Час, а не пятнадцать минут: между заказом и удавшимся сжатием умещается целый
# круг отказа — сторож отбил, сессия пошла обновлять запись, обновление заняло
# несколько ходов. При пятнадцати минутах метка успевала протухнуть, и работа
# после успешного сжатия всё равно не возобновлялась — ровно та поломка, ради
# которой метка и заводилась.
СВЕЖЕСТЬ_СЕК = 60 * 60


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


def придержать_ход(метка: Path) -> int:
    """Stop: свежий, ещё не придержанный заказ — кончить ход, чтобы он исполнился."""
    try:
        сведения = метка.stat()
        текст = метка.read_text(encoding="utf-8")
    except OSError:
        return 0
    if time.time() - сведения.st_mtime > СВЕЖЕСТЬ_СЕК or "held" in текст.split():
        return 0
    try:
        with метка.open("a", encoding="utf-8") as ф:
            ф.write("held\n")
        os.utime(метка, ns=(сведения.st_atime_ns, сведения.st_mtime_ns))
    except OSError:
        return 0
    json.dump({"continue": False,
               "stopReason": "заказано сжатие: ход завершён, чтобы оно "
                             "исполнилось, работа продолжится после него"},
              sys.stdout, ensure_ascii=False)
    return 0


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
    if полезное.get("hook_event_name") == "Stop":
        return придержать_ход(метка)
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
