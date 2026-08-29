#!/usr/bin/env python3
"""Чекпоинт вокруг компакции контекста: три режима, по одному на событие.

Компакция сворачивает разговор в пересказ. Переживают её только корневой
CLAUDE.md, безусловные правила, auto memory и системный промпт. Ответ Serena
с `mem:core`, вложенные CLAUDE.md и правила с `paths:` — нет.

Разделение по событиям продиктовано тем, что каждое из них умеет:

    guard    PreCompact (manual)  — единственное событие вокруг компакции,
                                    которое может заблокировать (exit 2)
    mark     PostCompact          — decision control отсутствует, доступны
                                    только побочные эффекты: пишем метку
    restore  UserPromptSubmit     — одно из трёх событий, чей stdout попадает
                                    в контекст; отдаёт указатель и снимает метку

Состояние: <cwd>/.claude/.checkpoint-<host> (пишет скилл) и .checkpoint-pending-<host>.
Имена с хостом — каталог синкается Syncthing между машинами.
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

STALE_SECONDS = 30 * 60
# Насколько метка времени может опережать часы, оставаясь правдоподобной.
FUTURE_TOLERANCE = 5 * 60

# Структура пересказа — дословная копия `chat.DefaultCompactSummary` службы
# Таусозавра (сверено побайтно 26.08: 1765 знаков с обеих сторон).
#
# Копия, а не запрос к службе: сессия в терминале поднимается без неё, и
# спрашивать было бы не у кого — а восстанавливаться она должна так же, как
# сессия под службой, иначе качество продолжения зависит от того, где её
# подняли. Источник правды — Go-константа: правится она, этот текст следом.
# Расходятся копии молча, потому это и написано здесь прямо.
#
# Печатает текст ОДИН из двоих. Под службой её собственный хук `PreCompact`
# знает больше — уклад сессии и его `compact_summary`, — и тогда молчит
# этот; решение принимается в `guard`.
#
# Весь успешный stdout хука `PreCompact` уходит в слот `Additional
# Instructions` зашитого промпта сжатия — другой точки вставки в нём нет.
#
# Текст подрезан 27.08 по обмеру 55 настоящих пересказов, сделанных по прежней
# редакции (`~/.claude/projects/**/*.jsonl`). Что показал обмер:
#
#   * CONSTRAINTS уходил на копию системного промпта. Самые частые пункты —
#     «no destructive git commands» (24 пересказа из 55), «never add
#     Co-Authored-By» (17), «commit only with permission» (14), «многострочное
#     сообщение в файл» (6). Все они и так приезжают кэшированной приставкой
#     каждым ходом. Виновата была строка «Never drop one for being obvious»:
#     она прямо велела копировать очевидное. Убрана.
#   * NEXT просил ОДНО действие, а получал в среднем 7.6 строки, максимум 18 —
#     пятая часть пересказа. Открытые вопросы теперь с потолком.
#   * Пересказ рос от сжатия к сжатию: 23 перехода внутри сессий, средний
#     коэффициент 1.26, выросло 11 против сжавшихся 6. Прежняя редакция нигде
#     не говорила, что законченное надо ВЫНОСИТЬ. Теперь говорит.
#   * VERIFIED/ASSUMED работают (51 и 40 из 55) — оставлены как есть.
#   * STATE и FILES пересекаются по путям всего на 8 % — сливать нечего.
#
# Фраз «пишешь для агента», «экономь на токен» и «содержимое файлов не
# переносится» здесь намеренно НЕТ: их говорит патч бинаря
# (`agent-conversation-summarization`) выше по промпту, в фазе анализа, куда
# этот слот не дотягивается.
SUMMARY_SPEC = """## Compact Instructions

Keep the required <analysis> and <summary> wrappers. Inside <summary> use
exactly these six sections, in this order, and no others — they replace the
nine standard ones.

## TASK
The goal in force now. Not the history of how it changed.

## CONSTRAINTS
Only what this conversation established: rulings the owner gave here, scope
they ruled out, approvals granted or withheld. The standing rules arrive with
the system prompt on their own — a copy here buys nothing and is re-sent by
every later turn.

## STATE
What is done, what is in progress. Mark every claim VERIFIED, naming the
evidence that proved it, or ASSUMED. Never promote an assumption to a fact.

## FILES
One line per path still in play: what it is, what changed, why it matters
next. The list of uncommitted paths arrives below as a fact — do not retell it.

## REJECTED
What was tried and abandoned, each with the reason it failed — the most
expensive knowledge to rediscover.

## NEXT
One action, startable without reading anything else. Then the questions
waiting on the owner: at most three, one line each.

Carry the working set, not the log: a finished step, a closed question, a
fixed bug leave the summary as soon as nothing depends on them.

Be specific — exact names, numbers, paths, error text; vagueness costs another
turn of rediscovery. Then cut every sentence that carries no fact, and never a
fact to make it shorter."""


def suffix_for(session_id: str = "") -> str:
    """Хвост имён состояния: хост И сессия.

    Хост — потому что каталог синкается Syncthing, и метка с одной машины
    подхватилась бы на другой.

    Сессия — потому что терминалов у владельца несколько. С одним файлом на
    хост второй `/checkpoint` затирал состояние первого, а `PreCompact` затем
    сторожил чужое: разрешал сжать сессию, чей чекпоинт никто не делал.

    Короткий идентификатор (8 знаков) — тот же, что показывает `claude agents`.
    """
    host = socket.gethostname()
    return f"{host}-{session_id[:8]}" if session_id else host


def paths(cwd: str, session_id: str = "") -> tuple[str, str, str]:
    """Чекпоинт, метка восстановления и каталог состояния."""
    base = os.path.join(cwd, ".claude")
    suffix = suffix_for(session_id)
    return (
        os.path.join(base, f".checkpoint-{suffix}"),
        os.path.join(base, f".checkpoint-pending-{suffix}"),
        base,
    )


def spec_note_path(cwd: str, session_id: str = "") -> str:
    """Куда `guard` записывает, кто продиктовал структуру пересказа.

    Читает её `mark` и вписывает в заголовок сохранённого пересказа. Смысл
    один: решение замолчать должно быть заметно ПОСЛЕ, из архива, а не
    вычисляться заново по тому, что пересказ выглядит стандартным.
    """
    return os.path.join(cwd, ".claude", f".checkpoint-spec-{suffix_for(session_id)}")


def resolve_checkpoint(cwd: str, session_id: str) -> str:
    """Путь к чекпоинту этой сессии, с оглядкой на файлы прежнего формата.

    Старое имя (только хост) читаем, но не пишем: иначе переход сломал бы
    работу тем, у кого чекпоинт уже лежит, а смысла в поломке нет.
    """
    scoped, _, _ = paths(cwd, session_id)
    if os.path.exists(scoped) or not session_id:
        return scoped
    legacy, _, _ = paths(cwd)
    return legacy if os.path.exists(legacy) else scoped


def load(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def age_seconds(data: dict) -> float | None:
    stamp = data.get("at")
    if not stamp:
        return None
    try:
        parsed = time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return time.time() - time.mktime(parsed)


def stale_reason(data: dict) -> tuple[str, int] | None:
    """Почему чекпоинт нельзя считать свежим: («stale»|«future», минуты).

    None — можно.

    Отдельной функцией, а не сравнением на месте, ровно из-за второго случая:
    МЕТКА ИЗ БУДУЩЕГО. 29.08.2026 в чекпоинте лежало `2026-08-30T22:20` при
    часах `2026-08-29` — сессии, которая его писала, система выдала неверную
    дату, и она записала её честно. Возраст выходил отрицательным, условие
    «старше получаса» не срабатывало НИКОГДА, и сторож пропускал любое сжатие,
    лишь бы файл существовал. Проверка была включена и при этом не работала —
    худший из отказов, потому что он не виден.

    Допуск в пять минут оставлен часам: они расходятся на минуты, но не на
    сутки.

    Причина возвращается признаком и числом, а не готовой фразой: сторож
    говорит с моделью по-английски, а помощник `compact-order.py` — с
    владельцем по-русски, и одна общая формулировка не подошла бы обоим.
    """
    age = age_seconds(data)
    if age is None:
        return None
    if age < -FUTURE_TOLERANCE:
        return ("future", int(-age // 60))
    if age > STALE_SECONDS:
        return ("stale", int(age // 60))
    return None


def dirty_paths(cwd: str) -> str:
    """Короткий список незакоммиченного.

    Предел в двадцать имён — не бережливость: после сборки грязных путей
    бывают сотни, и такой список вытеснит из пересказа то, ради чего он
    пишется.
    """
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=cwd, capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    names, rest = [], 0
    for row in out.splitlines():
        parts = row.strip().split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            continue
        if len(names) == 20:
            rest += 1
            continue
        names.append(parts[1].strip())
    if not names:
        return ""
    line = ", ".join(names)
    return f"{line} и ещё {rest}" if rest else line


def facts(cwd: str, data: dict | None) -> str:
    """Что верно прямо сейчас и из разговора не восстановится.

    Путь плана и `next` — потому что содержимое файлов сжатие не переносит
    (возвращаются пять последних прочитанных, и у длинных только начало), а по
    пути продолжающий откроет их сам. Незакоммиченное — единственный список,
    по которому видно, какая работа сделана, но ещё не закреплена.
    """
    lines = []
    if data:
        if data.get("plan"):
            lines.append(f"- Active plan: `{data['plan']}` — open it and read "
                         "the section «Где я сейчас».")
        if data.get("next"):
            at = f" ({data['at']})" if data.get("at") else ""
            lines.append(f"- Last checkpoint{at} says next: {data['next']}")
    if dirty := dirty_paths(cwd):
        lines.append(f"- Uncommitted right now: {dirty}")
    if not lines:
        return ""
    return ("## Facts at the moment of compaction\n\n"
            "True right now, and not recoverable from the conversation. Fold "
            "them into the sections above — do not add a section for them.\n\n"
            + "\n".join(lines))


def service_speaks(payload: dict) -> bool:
    """Продиктует ли структуру пересказа кто-то, кроме этого хука.

    # Почему спрашиваем службу, а не окружение

    Сначала здесь стоял `TZ_SELF` — переменная, которой служба помечает свои
    сессии. Признак верный, но НАСЛЕДУЕМЫЙ, и `cleanEnv` его не вычищает:
    всякий `claude`, поднятый изнутри сессии (`cmd/launch`, терминал, вызов
    из инструмента), получал чужой номер. Хуков службы у такой сессии нет, а
    хук считал её нашей и замолкал — диктовать оказывалось некому, и пересказ
    молча выходил стандартным. Ровно та потеря, ради предотвращения которой
    всё и затевалось.

    Вычистить переменную там, где сессии поднимаем мы, мало: `claude` из-под
    сессии запускают и руками. Поэтому признак взят не текущий по дереву
    процессов вовсе — `session_id` из полезной нагрузки, его выдаёт CLI.

    # Направление отказа

    Нет ответа, незнакомый номер, оборванная связь, мусор вместо JSON — все
    пути ведут в `False`, и хук говорит. Ошибиться в эту сторону значит
    напечатать структуру дважды: видно в пересказе, чинится. Ошибиться в
    другую — потерять её совсем, и не узнать об этом.

    Ловим `Exception` целиком намеренно: urllib отдаёт `URLError`,
    `HTTPError`, таймаут сокета и `ValueError` из разбора — перечислять их
    поимённо значит однажды пропустить новый и уронить хук, а упавший хук
    здесь равен потерянной структуре.
    """
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return False
    addr = os.environ.get("TZ_ADDR", "").strip() or "http://127.0.0.1:8181"
    if not addr.startswith("http"):
        addr = "http://" + addr
    req = urllib.request.Request(
        addr + "/api/compact-speaks",
        data=json.dumps({"session_id": session_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return bool(json.load(resp).get("speaks"))
    except Exception:
        return False


def note(cwd: str, session_id: str, who: str) -> None:
    """Записать, кто диктовал структуру этому сжатию.

    Тихо: не записалось — не беда, ради заметки сжатие останавливать нельзя.
    """
    try:
        os.makedirs(os.path.join(cwd, ".claude"), exist_ok=True)
        with open(spec_note_path(cwd, session_id), "w", encoding="utf-8") as f:
            f.write(who)
    except OSError:
        pass


def take_note(cwd: str, session_id: str) -> str:
    """Прочитать заметку и убрать её: она про одно конкретное сжатие."""
    path = spec_note_path(cwd, session_id)
    try:
        with open(path, encoding="utf-8") as f:
            who = f.read().strip()
    except OSError:
        return ""
    try:
        os.remove(path)
    except OSError:
        pass
    return who


def guard(payload: dict) -> int:
    """PreCompact: сторож чекпоинта И указания к пересказу.

    Весь успешный stdout этого хука становится содержимым слота `Additional
    Instructions` в промпте сжатия. Раньше здесь печаталось пусто, и сессия из
    терминала сворачивалась девятью стандартными разделами, тогда как сессия
    под службой получала структуру и факты. Разницы в качестве восстановления
    это не оправдывало — с тех пор текст печатается и здесь.

    Но под службой этот хук не один: её собственный `PreCompact` ставится в
    настройки сессии, а хостовые хуки с сессионными СКЛАДЫВАЮТСЯ, не
    замещаются. Обе стороны печатали одну и ту же структуру, и в промпт она
    уходила дважды. Молчит здесь тот, чей текст беднее: служба знает уклад
    сессии и его `compact_summary`, этот процесс — нет.

    Сторож чекпоинта при этом остаётся за нами и под службой тоже: свой она
    намеренно не включает там, где стоит хостовый (`compactBlocked` смотрит
    на `hostGuards`). Уберёшь блокировку отсюда заодно с текстом — её не
    останется вовсе ни у кого.

    Блокировка — только для ручного сжатия: автоматическое случается на
    потолке окна, и отказ означал бы сессию, которая не может ни сжаться, ни
    продолжать.
    """
    cwd = payload.get("cwd", ".")
    data = load(resolve_checkpoint(cwd, payload.get("session_id", "")))

    if payload.get("trigger") == "manual":
        if data is None:
            sys.stderr.write(
                "Compaction stopped: there is no checkpoint.\n\n"
                "The conversation is about to fold into a summary, and everything "
                "worked out but not written to disk will be lost. First `/checkpoint` "
                "— it updates the plan and writes down what to continue from. Then "
                "compaction is safe.\n\n"
                "If the task is finished and there is nothing to continue — say so to "
                "the owner and offer `/clear` instead of `/compact`: it is cheaper."
            )
            return 2
        if beda := stale_reason(data):
            kind, minutes = beda
            what = (f"the checkpoint is {minutes} min stale" if kind == "stale"
                    else f"the checkpoint is timestamped {minutes} min in the "
                         "FUTURE — the machine clock or the date handed to a "
                         "session has drifted, and staleness cannot be judged")
            sys.stderr.write(
                f"Compaction stopped: {what}.\n\n"
                f"Last recorded: {data.get('at')}\n"
                f"Plan: {data.get('plan', '—')}\n\n"
                "Much has been done since that is not in the plan. Run `/checkpoint` "
                "again, then compact."
            )
            return 2

    # Указания диктует служба — и структуру, и факты (её список фактов шире
    # нашего: в нём есть ещё и файлы, которых сессия касалась). Печатать своё
    # поверх значило бы прислать модели два одинаковых «## Compact
    # Instructions» и два «## Facts at the moment of compaction».
    session_id = payload.get("session_id", "")
    if service_speaks(payload):
        # Молчание — опасная сторона развилки, поэтому оно не бесшумно.
        # Строка уходит в stderr (хук вышел нулём, и она видна в событии
        # `hook_response`), а метка ложится рядом с чекпоинтом: `mark`
        # впишет её в заголовок сохранённого пересказа. Потерянная
        # структура должна обнаруживаться по архиву, а не по догадке
        # «что-то пересказ выглядит стандартным».
        note(cwd, session_id, "служба (её хук PreCompact)")
        sys.stderr.write("checkpoint.py: структуру пересказа диктует служба — "
                         "своих указаний не печатаю\n")
        return 0

    note(cwd, session_id, "этот хук")
    out = SUMMARY_SPEC
    if extra := facts(cwd, data):
        out += "\n\n" + extra
    sys.stdout.write(out + "\n")
    return 0


def mark(payload: dict) -> int:
    """PostCompact: сохранить пересказ и поставить метку для восстановления."""
    cwd = payload.get("cwd", ".")
    cp_path, pending, base = paths(cwd, payload.get("session_id", ""))
    os.makedirs(base, exist_ok=True)

    summary = payload.get("compact_summary") or ""
    if summary:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        log_dir = os.path.join(base, "compact-summaries")
        os.makedirs(log_dir, exist_ok=True)
        # Кто диктовал структуру — в заголовок. Без этой строки пересказ,
        # вышедший стандартным из-за того, что замолчали оба, ничем не
        # отличается от пересказа, которому просто не последовали.
        who = take_note(cwd, payload.get("session_id", "")) or "неизвестно"
        with open(os.path.join(log_dir, f"{stamp}.md"), "w", encoding="utf-8") as f:
            f.write(f"# Пересказ компакции {stamp}\n\n"
                    f"Триггер: {payload.get('trigger', '?')}\n"
                    f"Структуру диктовал: {who}\n\n{summary}\n")

    with open(pending, "w", encoding="utf-8") as f:
        f.write(payload.get("trigger", "manual"))
    return 0


def restore(payload: dict) -> int:
    """UserPromptSubmit: если только что была компакция — вернуть указатель."""
    cwd = payload.get("cwd", ".")
    session_id = payload.get("session_id", "")
    cp_path, pending, _ = paths(cwd, session_id)
    if not os.path.exists(pending):
        return 0
    try:
        os.remove(pending)
    except OSError:
        pass

    data = load(resolve_checkpoint(cwd, session_id))
    lines = [
        "The context has just been compacted. Below is what compaction does not carry over.",
        "",
        "Restore your working state before answering:",
        "1. Serena — if it is not bound to a project, bind it to THIS directory, never your home:",
        "   a home directory makes it crawl caches, package stores and kernel sources for minutes.",
        "2. Open the plan POINTWISE, not whole: `find_symbol` on «Где я сейчас» with",
        "   `include_body=true`; the map, if needed — `get_symbols_overview` with `depth=2`.",
    ]
    if data:
        lines += [
            "",
            f"Plan:            {data.get('plan', '—')}",
            f"Serena project:  {data.get('project', '—')}",
            f"Recorded at:     {data.get('at', '—')}",
            f"Next action:     {data.get('next', '—')}",
        ]
    else:
        lines += ["", "There is no pointer — the state will have to be restored from the plan and git."]

    sys.stdout.write("\n".join(lines) + "\n")
    return 0


MODES = {"guard": guard, "mark": mark, "restore": restore}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        sys.stderr.write(f"использование: checkpoint.py {{{'|'.join(MODES)}}}\n")
        return 1
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    return MODES[sys.argv[1]](payload)


if __name__ == "__main__":
    sys.exit(main())
