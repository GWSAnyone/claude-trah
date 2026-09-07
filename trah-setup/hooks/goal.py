"""Активная цель `/goal`, вычитанная из стенограммы.

Не хук — общий модуль. Им пользуются:

* `checkpoint.py` — чтобы указания к выжимке несли условие и доказательства;
* `nudge-compact.py` — чтобы цель не читалась как повод отложить сжатие и чтобы
  застрявшая цель не разоряла молча.

ЗАЧЕМ ЭТО ВООБЩЕ. Оценщик цели читает ТОЛЬКО стенограмму: инструментов у него
нет, файлы он не открывает, план прочитать не может (разобрано по бинарнику
2.1.259, 03.09.2026). Сжатие стенограмму заменяет выжимкой, и доказательства,
добытые до сжатия, для оценщика исчезают. Хуже: при обрезке транскрипта под
окно оценщика им же дописывается прямая инструкция вернуть «insufficient
evidence in transcript». Значит цель, доказательство которой осталось до
сжатия, становится недоказуемой и цикл не кончается никогда. Условие и
доказательства обязаны попасть в выжимку — а выжимку пишем мы.

КАК ОПРЕДЕЛЯЕТСЯ АКТИВНОСТЬ. Правило списано с их собственного восстановления
цели при `--resume` (функция `Rhr`): идти по стенограмме с конца, взять первое
вложение `goal_status`; если у него `met` или `failed` — цели нет, иначе цель
активна с этим условием.

ВИДЫ ВЛОЖЕНИЙ `goal_status`, все четыре из их кода:

    {met: false, sentinel: true,  condition}          — цель поставлена
    {met: true,  sentinel: true,  condition}          — снята вручную
    {met: false, condition, reason}                   — оценщик отказал
    {met: true,  condition, reason, iterations, …}    — достигнута
    {met: false, failed: true, condition, reason, …}  — признана невыполнимой
"""
import json
import os

# Сколько отказов оценщика подряд считать застреванием. Предела итераций в их
# коде НЕТ вовсе (искал `maxIterations` — не существует), а каждая попытка
# остановиться стоит вызова модели по всей стенограмме. Десять — не жёсткий
# стоп, а порог, после которого требуем назвать вслух, достижима ли цель.
ПОТОЛОК_ОТКАЗОВ = 10

# Предфильтр по сырой строке: разбирать JSON у каждой записи стенограммы дорого,
# а нужных записей единицы. Тот же приём, что в `nudge-compact.py`.
_МЕТКА = b'"goal_status"'


def _вложения(стенограмма: str) -> list[dict]:
    """Все `goal_status` в порядке файла. Ошибки чтения — пустой список."""
    найдено: list[dict] = []
    try:
        файл = open(стенограмма, "rb")
    except OSError:
        return найдено
    with файл:
        for сырая in файл:
            if _МЕТКА not in сырая:
                continue
            try:
                запись = json.loads(сырая.decode("utf-8", "replace"))
            except ValueError:
                continue
            if запись.get("type") != "attachment":
                continue
            вложение = запись.get("attachment") or {}
            if вложение.get("type") != "goal_status":
                continue
            вложение = dict(вложение)
            вложение["_время"] = запись.get("timestamp")
            найдено.append(вложение)
    return найдено


def состояние(стенограмма: str | None) -> dict | None:
    """Активная цель или None.

    Возвращает `{"условие", "отказов", "поставлена", "причина"}`:

    * `условие` — текст, дословно как его ввёл владелец;
    * `отказов` — сколько раз оценщик ответил «не выполнено» с постановки;
    * `поставлена` — отметка времени записи о постановке, если нашлась;
    * `причина` — что оценщик сказал в последний отказ, если отказ был.
    """
    if not стенограмма or not os.path.exists(стенограмма):
        return None
    все = _вложения(стенограмма)
    if not все:
        return None

    последнее = все[-1]
    if последнее.get("met") or последнее.get("failed"):
        return None
    условие = последнее.get("condition")
    if not isinstance(условие, str) or not условие:
        return None

    # Считаем с последней ПОСТАНОВКИ, а не с начала файла: цель могли ставить
    # несколько раз подряд, и отказы прежней к нынешней отношения не имеют.
    начало = 0
    for i in range(len(все) - 1, -1, -1):
        if все[i].get("sentinel") and not все[i].get("met"):
            начало = i
            break
    хвост = все[начало:]
    отказов = sum(1 for в in хвост
                  if not в.get("sentinel") and not в.get("met")
                  and not в.get("failed"))
    причина = next((в.get("reason") for в in reversed(хвост)
                    if not в.get("sentinel") and not в.get("met")), None)
    return {
        "условие": условие,
        "отказов": отказов,
        "поставлена": хвост[0].get("_время") if хвост else None,
        "причина": причина if isinstance(причина, str) else None,
    }


def застряла(цель: dict | None) -> bool:
    """Отказов накопилось столько, что пора назвать вещи своими именами."""
    return bool(цель) and цель.get("отказов", 0) >= ПОТОЛОК_ОТКАЗОВ


def указание_к_выжимке(цель: dict) -> str:
    """Раздел, который добавляется к указаниям PreCompact при активной цели."""
    условие = цель["условие"].strip()
    return (
        "\n## Active goal — this section is MANDATORY in the summary\n"
        "\n"
        "A `/goal` is running. Its evaluator reads ONLY the transcript: it has "
        "no tools, cannot open the plan, cannot run anything. After this "
        "compaction the summary IS the transcript for it. Whatever evidence "
        "you leave out stops existing, and the goal becomes impossible to "
        "satisfy — it will keep blocking every stop until someone clears it "
        "by hand.\n"
        "\n"
        "So the summary must carry a section headed `## Active goal` with:\n"
        "\n"
        f"1. **The condition, verbatim:** «{условие}»\n"
        "2. **What is already proven toward it** — one line per item, each "
        "with what proved it: the command and its output in numbers, the "
        "file:line, the measurement. Not «tests were run» but «`go test "
        "./... -count=1` → ok, 27 sets, 0 failed».\n"
        "3. **What is still missing** for the condition to hold.\n"
        "4. **Decisions taken under uncertainty** that the owner has not yet "
        "reviewed, and where they are recorded in the plan.\n"
        "\n"
        "Carry items 1 and 2 forward on every later compaction too: evidence "
        "dropped once never comes back.\n"
    )
