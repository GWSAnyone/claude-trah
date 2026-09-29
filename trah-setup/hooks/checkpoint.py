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

Состояние: <cwd>/.claude/.checkpoint-<host>-<8 знаков сессии> (пишет скилл),
рядом .checkpoint-pending-* и .checkpoint-spec-* с тем же хвостом.

Хвост из ДВУХ частей, и обе обязательны. Хост — каталог синкается Syncthing
между машинами. Сессия — их бывает несколько разом в одном дереве, и без неё
они пишут в один файл поверх друг друга.

Имя считает `suffix_for`, и это единственное место, где оно считается.
Скиллу его выдаёт команда `checkpoint.py path` — вычислять имя второй раз
своими силами нельзя, две редакции одного правила разъезжаются молча.
"""

import glob
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import goal  # noqa: E402

STALE_SECONDS = 30 * 60
# Насколько метка времени может опережать часы, оставаясь правдоподобной.
FUTURE_TOLERANCE = 5 * 60

# Не чаще одного толчка в эти секунды на сессию. Толчок сам приходит репликой и
# сам вызывает ход — а ход может снова упереться в тот же протухший чекпоинт.
# Без ограничителя это цикл, и он крутится молча.
NUDGE_SECONDS = 5 * 60

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


def age_seconds(path: str, data: dict | None = None) -> float | None:
    """Возраст указателя в секундах. Время берётся из mtime файла.

    НЕ из поля `at`: его пишет модель, и пишет по памяти. 30.08.2026 в
    указателе оказалось время на 189 минут вперёд — сессия проставила его на
    глаз сразу после честной записи состояния, сторож увидел метку из будущего
    и отбил сжатие. Отказ был формально верен и при этом полностью ложен:
    состояние на диске было свежее некуда.

    Момент записи знает файловая система, и спрашивать о нём модель незачем.
    Поле `at` осталось запасным путём — на указатели прежнего формата и на
    случай, когда mtime не прочитался.
    """
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        pass
    stamp = (data or {}).get("at")
    if not stamp:
        return None
    try:
        parsed = time.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return time.time() - time.mktime(parsed)


def written_at(path: str, data: dict | None = None) -> str:
    """Когда указатель записан — по файлу, а не по слову модели."""
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S",
                             time.localtime(os.path.getmtime(path)))
    except OSError:
        return str((data or {}).get("at") or "—")


def stale_reason(path: str, data: dict | None = None) -> tuple[str, int] | None:
    """Почему чекпоинт нельзя считать свежим: («stale»|«future», минуты).

    None — можно.

    Отдельной функцией, а не сравнением на месте, ровно из-за второго случая:
    ВРЕМЯ ИЗ БУДУЩЕГО. 29.08.2026 в чекпоинте лежало `2026-08-30T22:20` при
    часах `2026-08-29` — сессии, которая его писала, система выдала неверную
    дату, и она записала её честно. Возраст выходил отрицательным, условие
    «старше получаса» не срабатывало НИКОГДА, и сторож пропускал любое сжатие,
    лишь бы файл существовал. Проверка была включена и при этом не работала —
    худший из отказов, потому что он не виден.

    С переходом на mtime (30.08.2026) этот случай почти исчез: время ставит
    файловая система. Проверка оставлена на съехавшие назад часы машины и на
    запасной путь по полю `at`, где всё прежнее в силе.

    Допуск в пять минут оставлен часам: они расходятся на минуты, но не на
    сутки.

    Причина возвращается признаком и числом, а не готовой фразой: сторож
    говорит с моделью по-английски, а помощник `compact-order.py` — с
    владельцем по-русски, и одна общая формулировка не подошла бы обоим.
    """
    age = age_seconds(path, data)
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


def facts(cwd: str, data: dict | None, path: str = "") -> str:
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
            at = f" ({written_at(path, data)})" if path or data.get("at") else ""
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


def nudge_stamp_path(cwd: str, session_id: str = "") -> str:
    """Когда сессию в последний раз толкали после отбитого сжатия."""
    return os.path.join(cwd, ".claude", f".compact-nudged-{suffix_for(session_id)}")


def compact_order_path(cwd: str, session_id: str = "") -> str:
    """Метка сжатия, которое сессия заказала себе сама (`compact-order.py`).

    Её читают трое: `compact-order` — от двойного заказа, `compact-continue` —
    чтобы разбудить сессию после сжатия и съесть метку, `nudge-wait` — чтобы не
    требовать будильника, когда будить уже есть кому.
    """
    return os.path.join(cwd, ".claude", f".compact-ordered-{suffix_for(session_id)}")


def nudge(cwd: str, session_id: str, reason: str) -> str:
    """Толкнуть сессию репликой после отказа в сжатии.

    Отказ печатается в stderr хука, а stderr — это указание МОДЕЛИ, которой
    может не достаться хода. Замер по стенограмме сессии 0d52af2f (01.09.2026):
    из 21 отбитого сжатия 13 раз сессия встала и ждала реплику человека. Ход
    даёт только кадр в сокет — тот же путь, которым `compact-order.py` заказывает
    сжатие, а `compact-continue.py` возвращает работу после удавшегося.

    Возвращает пустую строку при успехе, иначе — беду для stderr. Тихо: ради
    толчка отказ не отменяется и не превращается в ошибку.
    """
    if os.environ.get("CHECKPOINT_NUDGE") == "off":
        return "толчок выключен"

    штамп = nudge_stamp_path(cwd, session_id)
    try:
        if time.time() - os.path.getmtime(штамп) < NUDGE_SECONDS:
            return "толчок пропущен: предыдущий был только что"
    except OSError:
        pass

    свой = os.path.dirname(os.path.abspath(__file__))
    if свой not in sys.path:
        sys.path.insert(0, свой)
    try:
        import sockmsg
    except ImportError as e:
        return f"sockmsg не нашёлся: {e}"

    # Любая беда транспорта — строкой, не исключением. Упавший процесс на
    # PreCompact CLI читает как «не блок»: так на Windows (нет `os.getuid`,
    # нет `AF_UNIX`) сторож переставал сторожить, а сжатие шло без чекпоинта.
    try:
        беда = sockmsg.послать(
            f"Compaction was refused: {reason}. Update the record — the working "
            "state, what was measured, what was tried and abandoned — then order "
            "the compaction again. Continue the interrupted work afterwards; do "
            "not ask what to do."
        )
    except Exception as e:  # noqa: BLE001 — отказ в сжатии важнее толчка
        беда = f"кадр не ушёл: {e}"
    if беда:
        return беда
    try:
        os.makedirs(os.path.join(cwd, ".claude"), exist_ok=True)
        with open(штамп, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S"))
    except OSError:
        pass
    return ""


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
    cp_path = resolve_checkpoint(cwd, payload.get("session_id", ""))
    data = load(cp_path)

    if payload.get("trigger") == "manual":
        if data is None:
            sys.stderr.write(
                "Compaction stopped: there is no checkpoint.\n\n"
                "Everything worked out but not written to disk would be lost.\n\n"
                "Write the state down, then repeat the compaction. Do not stop "
                "here and do not ask what to do.\n\n"
                "Task finished and nothing to continue — offer `/clear` instead."
            )
            if беда := nudge(cwd, payload.get("session_id", ""),
                             "there is no checkpoint"):
                sys.stderr.write(f"\n\ncheckpoint.py: {беда}")
            return 2
        if beda := stale_reason(cp_path, data):
            kind, minutes = beda
            what = (f"the checkpoint is {minutes} min stale" if kind == "stale"
                    else f"the checkpoint file is dated {minutes} min in the "
                         "FUTURE — the machine clock has drifted, and staleness "
                         "cannot be judged")
            sys.stderr.write(
                f"Compaction stopped: {what}.\n\n"
                f"Written: {written_at(cp_path, data)}\n"
                f"Plan: {data.get('plan', '—')}\n\n"
                "Much has been done since that is not in the record.\n\n"
                "Bring it up to date, then repeat the compaction. Do not stop "
                "here and do not ask what to do."
            )
            if беда := nudge(cwd, payload.get("session_id", ""), what):
                sys.stderr.write(f"\n\ncheckpoint.py: {беда}")
            return 2

    # Указания диктует служба — и структуру, и факты (её список фактов шире
    # нашего: в нём есть ещё и файлы, которых сессия касалась). Печатать своё
    # поверх значило бы прислать модели два одинаковых «## Compact
    # Instructions» и два «## Facts at the moment of compaction».
    session_id = payload.get("session_id", "")
    # Активная цель `/goal`. Её оценщик читает ТОЛЬКО стенограмму, а сжатие
    # стенограмму заменяет выжимкой — значит условие и доказательства обязаны
    # уехать в выжимку, иначе цель станет недоказуемой и будет блокировать
    # остановку до ручной отмены. Разбор механизма — в `goal.py`.
    цель = goal.состояние(payload.get("transcript_path"))
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
        # А раздел про активную цель печатаем и здесь. Службе про `/goal`
        # ничего не известно, дублировать нечего, — и без этого раздела
        # оценщик цели после сжатия останется без доказательств.
        if цель:
            sys.stdout.write(goal.указание_к_выжимке(цель) + "\n")
        return 0

    note(cwd, session_id, "этот хук")
    out = SUMMARY_SPEC
    if extra := facts(cwd, data, cp_path):
        out += "\n\n" + extra
    if цель:
        out += "\n\n" + goal.указание_к_выжимке(цель)
    sys.stdout.write(out + "\n")
    return 0


def mark(payload: dict) -> int:
    """PostCompact: сохранить пересказ и поставить метку для восстановления."""
    cwd = payload.get("cwd", ".")
    session_id = payload.get("session_id", "")
    cp_path, pending, base = paths(cwd, session_id)
    os.makedirs(base, exist_ok=True)

    # Заметку снимаем ВСЕГДА, а не только когда есть что записать. Прежняя
    # редакция звала `take_note` внутри `if summary:` — и сжатие с пустым
    # пересказом оставляло заметку лежать навсегда. За неделю их натекло три.
    who = take_note(cwd, session_id) or "неизвестно"

    summary = payload.get("compact_summary") or ""
    if summary:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        log_dir = os.path.join(base, "compact-summaries")
        os.makedirs(log_dir, exist_ok=True)
        # Кто диктовал структуру — в заголовок. Без этой строки пересказ,
        # вышедший стандартным из-за того, что замолчали оба, ничем не
        # отличается от пересказа, которому просто не последовали.
        with open(os.path.join(log_dir, f"{stamp}.md"), "w", encoding="utf-8") as f:
            f.write(f"# Пересказ компакции {stamp}\n\n"
                    f"Триггер: {payload.get('trigger', '?')}\n"
                    f"Структуру диктовал: {who}\n\n{summary}\n")

    with open(pending, "w", encoding="utf-8") as f:
        f.write(payload.get("trigger", "manual"))

    # Уборка идёт здесь, а не на старте сессии: `PostCompact` случается редко,
    # а хук и так уже разбудил питон. Своя беда уборки не должна ронять метку,
    # ради которой хук и позван, — поэтому она последней и под глушителем.
    try:
        sweep(cwd, session_id)
    except Exception:                                          # noqa: BLE001
        pass
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

    cp_path = resolve_checkpoint(cwd, session_id)
    data = load(cp_path)
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
            f"Recorded at:     {written_at(cp_path, data)}",
            f"Next action:     {data.get('next', '—')}",
        ]
    else:
        lines += ["", "There is no pointer — the state will have to be restored from the plan and git."]

    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def where() -> int:
    """Напечатать путь к указателю ЭТОЙ сессии. Не событие — команда для скилла.

    Правило именования состояния должно жить в ОДНОМ месте. Раньше оно было
    записано дважды: здесь, в `suffix_for`, и словами в тексте скилла, который
    вычислял восьмизнак сам — `ls -t` по каталогу стенограмм и `head -1`. Под
    параллельными сессиями это гонка: самая свежая стенограмма в каталоге с
    равным успехом чужая. Замер 30.08.2026 по 257 стенограммам этого проекта —
    56 минут, в которые менялись сразу несколько.

    Расплата двусторонняя и обе стороны тихие: указатель уезжает под чужим
    именем (сосед теряет свой), а `guard` ищет строго своё имя, не находит и
    блокирует сжатие словами «чекпоинта нет» — сразу после того, как скилл его
    записал.

    Идентификатор при этом лежит в окружении: `CLAUDE_CODE_SESSION_ID` ставит
    сам CLI. Нет его — молчать нельзя, иначе имя тихо выродится в общее на все
    сессии; поэтому отказ с кодом 1, а запасной путь остаётся за вызывающим.
    """
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        sys.stderr.write(
            "checkpoint.py path: в окружении нет CLAUDE_CODE_SESSION_ID.\n"
            "Без него имя указателя выродится в общее на все сессии этой "
            "машины, и параллельные сессии затрут друг друга.\n")
        return 1
    scoped, _, _ = paths(session_cwd(session_id), session_id)
    sys.stdout.write(scoped + "\n")
    return 0


# Приставки имён состояния. Порядок важен: `.checkpoint-` — приставка и для
# двух других, и проверять её надо последней.
STATE_PREFIXES = (".checkpoint-pending-", ".checkpoint-spec-", ".checkpoint-")
RETIRED_DIR = "checkpoints-retired"


def transcripts_dir(cwd: str) -> str:
    """Каталог стенограмм этого проекта.

    CLI кодирует путь заменой на `-` ВСЕГО, что не латиница, цифра или дефис:
    `/home/u/x` → `-home-u-x`, `D:\\asynchronus` → `D--asynchronus`. Прежняя
    замена одной `/` под Windows не меняла ничего, а `os.path.join` с
    абсолютным `C:\\…` вторым аргументом отбрасывает первый — «каталогом
    стенограмм» становился сам проект, и `sweep` судил о живости сессий по его
    `*.jsonl`.
    """
    return os.path.join(os.path.expanduser("~"), ".claude", "projects",
                        re.sub(r"[^A-Za-z0-9-]", "-", os.path.abspath(cwd)))


def session_cwd(session_id: str) -> str:
    """cwd сессии — тот самый, что хуки получают в payload.

    Скрипт, который модель зовёт из Bash (`compact-order.py`, `checkpoint.py
    path`), видит cwd своего процесса, а тот уезжает за первым же `cd` в
    команде. Тогда указатель ложился в `<другой каталог>/.claude`, а `guard` и
    `compact-continue` искали его в cwd из payload: сжатие отбивалось словами
    «чекпоинта нет», заказ терял продолжение. В окружении cwd сессии нет, в
    стенограмме есть — поле `cwd` у записей. Нет стенограммы — cwd процесса.
    """
    if session_id:
        маска = os.path.join(os.path.expanduser("~"), ".claude", "projects",
                             "*", session_id + ".jsonl")
        for path in glob.glob(маска):
            try:
                with open(path, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    f.seek(max(0, f.tell() - 262144))
                    хвост = f.read().decode("utf-8", "replace")
            except OSError:
                continue
            for line in reversed(хвост.splitlines()):
                try:
                    cwd = json.loads(line).get("cwd")
                except (ValueError, AttributeError):
                    continue
                if cwd:
                    return cwd
    return os.getcwd()


def own_suffix(name: str, host: str) -> str:
    """Восьмизнак сессии из имени файла состояния ЭТОЙ машины, иначе пусто.

    Чужой хост не наш: каталог синкается Syncthing, и файл с другой машины
    трогать нельзя — там своя жизнь и свои стенограммы.
    """
    for prefix in STATE_PREFIXES:
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        return rest[len(host) + 1:] if rest.startswith(host + "-") else ""
    return ""


def sweep(cwd: str, session_id: str = "") -> int:
    """Убрать в архив состояние сессий, чьих стенограмм больше нет.

    Указатели копились без предела: 30.08.2026 в этом дереве их лежало десять
    на 17 625 байт, самому старому шесть суток. Читал их скилл склейкой по
    маске, то есть рисковал утащить `next` недельной давности из чужой сессии.

    Файлы ПЕРЕНОСЯТСЯ, а не удаляются: в указателе лежит слово владельца о том,
    с чего продолжать, и цена ошибочного суждения «эта сессия мертва»
    несопоставима с ценой лишнего файла на диске.

    Признак смерти один — пропала стенограмма. Пустой список живых означает,
    что каталог стенограмм не прочитался, и тогда мы не судим вовсе: иначе
    первая же ошибка чтения увезла бы в архив всё разом.
    """
    base = os.path.join(cwd, ".claude")
    try:
        live = {n[:8] for n in os.listdir(transcripts_dir(cwd))
                if n.endswith(".jsonl")}
        names = sorted(os.listdir(base))
    except OSError:
        return 0
    if not live:
        return 0

    host, mine, moved = socket.gethostname(), session_id[:8], 0
    for name in names:
        suffix = own_suffix(name, host)
        if not suffix or suffix == mine or suffix in live:
            continue
        try:
            os.makedirs(os.path.join(base, RETIRED_DIR), exist_ok=True)
            os.replace(os.path.join(base, name),
                       os.path.join(base, RETIRED_DIR, name))
            moved += 1
        except OSError:
            pass
    return moved


MODES = {"guard": guard, "mark": mark, "restore": restore}


def main() -> int:
    команды = (*MODES, "path")
    if len(sys.argv) < 2 or sys.argv[1] not in команды:
        sys.stderr.write(f"использование: checkpoint.py {{{'|'.join(команды)}}}\n")
        return 1
    # `path` — команда, а не событие: полезной нагрузки на входе нет, и ждать
    # её от stdin значило бы повиснуть на пустом терминале.
    if sys.argv[1] == "path":
        return where()
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    return MODES[sys.argv[1]](payload)


if __name__ == "__main__":
    sys.exit(main())
