#!/usr/bin/env python3
"""PreToolUse-гард: Таусик не пишет код.

Таусик — сессия приёма и раскладки задач. Его ценность в том, что владельцу
есть куда деть мысль, не отвлекая работающего агента. Стоит ему начать
реализовывать — он перестаёт быть таким местом: занимает себя надолго,
набирает контекст кодовой базы и отвечает не сразу.

Роль записана в его output style, но стиль — просьба. Здесь гарантия.

Признак роли — переменная окружения `TAUSIK_ROLE`, которую ставит скрипт
запуска. Хуки наследуют окружение сессии (проверено 15.08.2026), а имени
сессии в payload нет — иначе опознавали бы по нему.

Разрешено писать только markdown внутри `docs/`: планы, заметки, очередь.
Это ровно то, ради чего Таусик существует.

Exit 2 = блокировка. Exit 0 = пропустить.
"""

import json
import os
import re
import shlex
import sys

ROLE_ENV = "TAUSIK_ROLE"

# Инструменты записи. Символьные редакторы Serena — такой же путь к файлу,
# как Write: гард, знающий только про встроенные, обходится одним вызовом
# `replace_symbol_body`.
WRITE_TOOLS = frozenset(
    {
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "mcp__serena__replace_symbol_body",
        "mcp__serena__replace_content",
        "mcp__serena__insert_after_symbol",
        "mcp__serena__insert_before_symbol",
        "mcp__serena__rename_symbol",
        "mcp__serena__safe_delete_symbol",
    }
)

SHELL_TOOLS = frozenset({"Bash", "PowerShell"})

# Каждое поле, в котором инструмент может нести цель записи. `destination`
# важен отдельно: у перемещения цель — он, а не `path`, и гард, смотрящий
# только на источник, пропустил бы запись.
PATH_FIELDS = ("file_path", "notebook_path", "path", "relative_path", "destination")

# Перенаправление ищем ТОЛЬКО вне кавычек — сам оператор и отдельно имя
# файла за ним. Прежде это был один регэксп по всей строке, и он не различал
# команду и данные; чем это кончилось, написано у `redirect_targets`.
REDIRECT_RX = re.compile(r">>?")
TARGET_RX = re.compile(r"[\w./~-]+")

# Куда «пишут», чтобы выбросить. Это не запись, а глушение вывода: `2>/dev/null`
# стоит в каждой второй читающей команде, и запрещать её значит запрещать
# `ls docs/ 2>/dev/null` — то есть чтение.
#
# Поймано живьём: Таусику заблокировали `ls docs/ && ls docs/notes 2>/dev/null`
# с объяснением «Таусик не пишет код». Гард, срабатывающий на чтении, учит
# обходить себя — и это хуже, чем его отсутствие.
DISCARDS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/zero"}

# Операторы, разделяющие простые команды. По ним строку и режем перед разбором.
SPLIT_RX = re.compile(r"&&|\|\||[;|\n]")

# Команды, которые пишут в файл-аргумент. Значение — сколько первых
# позиционных аргументов НЕ являются целью: у `sed -i 's/a/b/' f` первый
# позиционный это выражение, у `tee f` целями являются все.
WRITERS = {"tee": 0, "sed": 1, "cp": 0, "mv": 0, "dd": 0}

# Команды, которые пишут ТОЛЬКО с ключом правки на месте. `sed` без `-i` —
# это чтение: `sed -n '1,80p' файл` печатает кусок и ничего не меняет.
#
# Поймано живьём 19.08: надзиратель хотел прочитать хук — `sed -n '1,80p'
# guard-tausik-write.py` — и получил «не пишет код». Гард, запрещающий
# ЧТЕНИЕ, вреден вдвойне: он мешает работе и учит не верить его отказам, а
# среди них есть настоящие.
INPLACE_ONLY = {"sed": ("-i", "--in-place")}


# Указатель чекпоинта: `.claude/.checkpoint-<хост>[-<8 знаков сессии>]`.
#
# Единственное исключение из «только markdown в docs/», и заведено оно по
# факту: сессия не могла записать свой чекпоинт (файл лежит в `.claude/`), и
# после сжатия контекста хук возвращал ВЧЕРАШНИЙ указатель — то есть работа
# продолжалась с чужого места. Молчаливая потеря состояния хуже любого файла,
# который здесь можно испортить.
#
# Имя проверяется целиком, а не по каталогу: `.claude/` — это ещё и настройки,
# и хуки, и права, трогать которые сессии по-прежнему нечего.
CHECKPOINT_RX = re.compile(r"^\.checkpoint(?:-pending)?-[A-Za-z0-9_.-]+$")


def allowed(path: str) -> bool:
    """Markdown внутри docs/, корневой CLAUDE.md и указатель чекпоинта.

    Каталог, а не расширение: README и CLAUDE.md проектов меняют поведение
    других агентов, и правит их владелец.

    КОРНЕВОЙ CLAUDE.md — исключение, и оно осмысленное. Это карта экосистемы:
    инварианты данных, атлас проектов, что не трогать. Держит её в порядке как
    раз надзиратель — он видит всё хозяйство целиком, и запирать его от того
    документа, которым он же и руководит, значило заставлять владельца
    переносить правки руками.

    Правило узкое: файл CLAUDE.md, лежащий ПРЯМО в корне проекта. Такой же
    файл внутри бота (`DmTrading/CLAUDE.md`) описывает конкретный сервис —
    там уклад бота, и решает его владелец.
    """
    norm = path.replace(os.sep, "/")
    parts = norm.rsplit("/", 2)
    if len(parts) >= 2 and parts[-2] == ".claude" and CHECKPOINT_RX.match(parts[-1]):
        return True
    if in_session_memory(norm):
        return True
    if norm == root_claude_md():
        return True
    if in_temp(norm):
        return True
    if not norm.endswith(".md"):
        return False
    return "/docs/" in norm or norm.startswith("docs/")


# Собственная память сессии: `~/.claude/projects/<проект>/memory/*.md`.
#
# Второе исключение из «только markdown в docs/», и заведено оно по той же
# причине, что и первое, — потерянное состояние.
#
# Туда харнесс сам велит складывать уроки: чем закончилась правка, какое
# допущение оказалось неверным, о чём владелец просил не забывать. Это
# ЕДИНСТВЕННЫЙ канал, которым знание переживает сжатие контекста и конец
# сессии; всё остальное сворачивается в пересказ или пропадает. Надзиратель
# писать туда не мог — то есть каждый выученный урок терялся молча.
#
# Правило узкое намеренно. В `~/.claude/projects/` лежат ТРАНСКРИПТЫ
# разговоров, и запись туда испортила бы историю, из которой восстанавливают
# ленту после перезапуска службы. Разрешаем только каталог `memory` и только
# markdown.
def in_session_memory(norm: str) -> bool:
    if not norm.endswith(".md"):
        return False
    base = os.path.expanduser("~/.claude/projects/").replace(os.sep, "/")
    if not norm.startswith(base):
        return False
    rest = norm[len(base):].split("/")
    # <проект>/memory/<что угодно>.md — минимум три части.
    return len(rest) >= 3 and rest[1] == "memory"


# Временные каталоги: черновик — не работа.
#
# Поймано живьём 19.08: надзиратель сверял корневой CLAUDE.md с прежней
# версией — `git show <коммит>^:CLAUDE.md > /tmp/claude_before.md && diff …` —
# и получил «не пишет код». Между тем в проекте не менялось ничего: файл во
# временном каталоге живёт до перезагрузки и ни на что не влияет.
#
# Запрет тут не защищал, а мешал разбираться: сравнить две версии, выгрузить
# ответ ручки, сложить список — обычная работа с фактами, ради которой
# надзиратель и существует.
#
# Оговорка, которую надо знать: скрипт, положенный во временный каталог, можно
# потом запустить, и его записи гард уже не увидит. Это дисциплина, а не
# охрана от злого умысла: уклад держит своего же агента в рамках роли.
TEMP_DIRS = ("/tmp/", "/var/tmp/", "/dev/shm/")


def in_temp(norm: str) -> bool:
    if norm.startswith(TEMP_DIRS):
        return True
    tmp = (os.environ.get("TMPDIR") or "").rstrip("/")
    return bool(tmp) and norm.startswith(tmp + "/")


def root_claude_md() -> str:
    """Путь к карте экосистемы — корневому CLAUDE.md проекта."""
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(root, "CLAUDE.md").replace(os.sep, "/")


# Heredoc: `<<EOF`, `<<-'PY'`, `<< "X"`. Тело такого блока — ДАННЫЕ, а не
# команда, и разбирать его как оболочку нельзя.
HEREDOC_RX = re.compile(r"<<-?\s*([\'\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

# Запись из скрипта, поданного в heredoc. Ловим то, чем пишут на деле:
# `open(path, "w")`, `Path(path).write_text(...)`, `shutil.copy(src, dst)`.
PY_OPEN_RX = re.compile(r"open\(\s*([^,)]+?)\s*,\s*[\'\"][waxr]?[bt+]*[wax][bt+]*[\'\"]")
PY_WRITE_RX = re.compile(r"(?:Path\(\s*([^)]+?)\s*\)\s*\.write_(?:text|bytes)|([\w.]+)\.write_(?:text|bytes)\()")
PY_ASSIGN_RX = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*[\'\"]([^\'\"\n]+)[\'\"]", re.M)

# Тройные кавычки — данные скрипта, а не его код: там лежит текст, который
# скрипт записывает. Искать в нём пути значит принимать за цель то, что
# упомянуто в прозе.
PY_TRIPLE_RX = re.compile(r"\'\'\'.*?\'\'\'|\"\"\".*?\"\"\"", re.S)
PY_LITERAL_RX = re.compile(r"\'([^\'\n]*)\'|\"([^\"\n]*)\"")

# Путь-подобная строка: косая черта МЕЖДУ значащими знаками. Не «содержит
# слэш»: под это подходят и `/`, и `s/a/b/`, и первое из них разворачивается
# в корень проекта, то есть в запрет на ровном месте.
PATHISH_RX = re.compile(r"[\w.~-]/[\w.-]")


# Присваивания оболочки и обращения к ним. Цель, названная переменной, —
# такая же цель: гард, который её не разворачивает, судит по строке `$f`.
SH_ASSIGN_RX = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.S)
VAR_RX = re.compile(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)")

QUOTES_RX = re.compile(r"'[^']*'|\"[^\"]*\"")


def mask_quoted(command: str) -> str:
    """Заглушить содержимое кавычек, сохранив длину строки."""
    return QUOTES_RX.sub(lambda m: m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[0], command)


def split_heredocs(command: str) -> tuple[str, list[str]]:
    """Отделить тела heredoc от самой команды.

    Пока этого не было, гард разбирал СОДЕРЖИМОЕ файла как оболочку. Строка
    плана `> База: BuyOrderBot …` читалась как перенаправление вывода в файл
    `База`, и надзирателю запрещали писать собственный план — то есть ровно
    то, ради чего он существует. Поймано живьём 18.08.2026.
    """
    lines = command.split("\n")
    body_lines: list[str] = []
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        marks = HEREDOC_RX.findall(line)
        i += 1
        for _, word in marks:
            while i < len(lines) and lines[i].strip() != word:
                body_lines.append(lines[i])
                i += 1
            i += 1  # сама закрывающая метка
    return "\n".join(kept), body_lines


def script_targets(body_lines: list[str]) -> list[str]:
    """Куда пишет скрипт, поданный в heredoc.

    Разбирать чужой язык целиком мы не беремся и не будем. Но записи `open(p,
    "w")` хватает, чтобы отличить «надзиратель правит свой план» от
    «надзиратель правит код через питон». Без этого heredoc был дырой:
    оболочка не пишет ничего, а файл на диске меняется.
    """
    body = "\n".join(body_lines)
    names = dict(PY_ASSIGN_RX.findall(body))
    # Запасной ответ на «имя, которого мы не знаем» — см. `pathish_literals`.
    guessed = pathish_literals(body)

    out: list[str] = []
    for m in PY_OPEN_RX.finditer(body):
        arg = m.group(1).strip()
        if arg[:1] in "'\"":
            out.append(arg.strip("'\""))
        elif arg in names:
            out.append(names[arg])
        elif guessed:
            out.extend(guessed)
        else:
            out.append("<путь из переменной %s>" % arg)
    for m in PY_WRITE_RX.finditer(body):
        arg = (m.group(1) or m.group(2) or "").strip()
        if arg[:1] in "'\"":
            out.append(arg.strip("'\""))
        elif arg in names:
            out.append(names[arg])
        elif guessed:
            out.extend(guessed)
    return out


def pathish_literals(body: str) -> list[str]:
    """Пути, названные в скрипте строками, — когда цель записи не разобрать.

    # Зачем

    Присваивание `p = 'docs/plans/x.md'` гард разворачивает. Но пути живут и
    там, где присваивания нет: ключами словаря, элементами списка, аргументами
    вызова. Простейший случай — закрыть две записи очереди разом:

        items = {"docs/queue/a.md": "…", "docs/queue/b.md": "…"}
        for path, tail in items.items():
            open(path, "w").write(...)

    Имени `path` в присваиваниях нет, и гард отвечал `Цель: <путь из
    переменной path>` — то есть блокировал работу, ради которой надзиратель и
    существует, отказом, который невозможно исполнить: переписывать нечего,
    цель разрешена, просто её не разглядели.

    # Как

    Берём строки-литералы скрипта, оставляем похожие на путь и судим по ним.
    Тройные кавычки выбрасываем: там лежит ТЕКСТ, который скрипт записывает, и
    упомянутый в прозе `docs/00-workspace.md` — не цель записи.

    # Чем это оплачено

    Разбор остаётся неполным, и это выбор, а не недосмотр. Скрипт, собирающий
    путь по частям, гард не разглядит — как не разглядит и скрипт, положенный
    в `/tmp` и запущенный оттуда. Уклад держит своего агента в рамках роли;
    он не охраняет от умысла. Зато отказ теперь наступает там, где в скрипте
    ДЕЙСТВИТЕЛЬНО назван путь к коду, и его видно в тексте отказа.
    """
    code = PY_TRIPLE_RX.sub(" ", body)
    out: list[str] = []
    for m in PY_LITERAL_RX.finditer(code):
        s = (m.group(1) or m.group(2) or "").strip()
        # Пробел внутри — это фраза, а не путь. Записываемый текст не всегда
        # в тройных кавычках, и предложение «починено в CSMoneyBot/main.go»
        # иначе становится целью записи: отказ на ровном месте, причём
        # ссылающийся на файл, которого команда не касается.
        if not s or any(c.isspace() for c in s):
            continue
        if PATHISH_RX.search(s) and s not in out:
            out.append(s)
    return out


def shell_targets(command: str) -> list[str]:
    """Файлы, в которые команда оболочки может писать.

    Разбор намеренно неполный: задача — не пропустить очевидное, а не поймать
    всё. Полный разбор командной строки со спуском в `bash -c` живёт в
    guard-destructive.py; дублировать его здесь значило бы завести вторую
    копию, которая разойдётся с первой.
    """
    command, bodies = split_heredocs(command)
    found = redirect_targets(command)
    found.extend(script_targets(bodies))

    # Составную команду разбираем ПО ЧАСТЯМ.
    #
    # Раньше разбор шёл по всей строке разом, и `mv a b && mv c d && ls` давал
    # целями `b`, `&&`, `mv`, `c`, `d`, `&&`, `ls` — всё, что стояло после
    # первого `mv`. Поймано живьём: Таусику запретили перенос двух планов из
    # `docs/` в `docs/` с объяснением «Цель: …/&&». Разделитель командой не
    # является, и приписывать ему запись — это не строгость, а поломка.
    for part in split_parts(command):
        found.extend(part_targets(part))
    # Переменные разворачиваем В КОНЦЕ, над готовым списком целей: они
    # встречаются и в редиректе, и в аргументе `sed -i`, и заводить разбор
    # дважды значило бы завести два места, которые разойдутся.
    return expand_vars(found, shell_vars(command))


def shell_vars(command: str) -> dict:
    """Присваивания, сделанные В ЭТОЙ ЖЕ команде.

    `f=docs/queue/x.md; sed -i 's/a/b/' "$f"; cat >> "$f" <<'EOF'` — обычный
    способ не повторять длинное имя трижды. Гард видел целью строку `$f`,
    сравнивал её с разрешённой зоной и отказывал: `Цель: …/$f`.

    Отказ был неисполним. Переписывать нечего — файл разрешён, команда верна;
    единственный выход, который он оставлял, — угадать, что дело в разборе.
    А отказ, который выглядит правилом, но им не является, учит не верить
    всем отказам подряд, включая настоящие.

    Читаем только присваивания в начале простой команды: `NAME=значение` и
    `NAME=значение команда …`. Того, что оболочка подставит из окружения или
    из подстановки команды, здесь нет намеренно — угадывать чужое значение
    хуже, чем честно оставить имя неразвёрнутым и отказать.
    """
    known: dict[str, str] = {}
    for part in split_parts(command):
        try:
            tokens = shlex.split(part)
        except ValueError:
            continue
        for tok in tokens:
            m = SH_ASSIGN_RX.match(tok)
            if not m:
                break  # присваивания идут только в начале команды
            name, value = m.group(1), m.group(2)
            known[name] = VAR_RX.sub(
                lambda x: known.get(x.group(1) or x.group(2), x.group(0)), value
            )
    return known


def expand_vars(found: list[str], known: dict) -> list[str]:
    """Подставить известные значения; неизвестное имя оставить как есть.

    Неизвестное не выбрасываем: цель, которую не удалось разобрать, — повод
    отказать, а не повод пропустить. Но в тексте отказа она останется видна
    именем, и понятно будет, что разбор споткнулся, а не правило сработало.
    """
    if not known:
        return found
    return [
        VAR_RX.sub(lambda m: known.get(m.group(1) or m.group(2), m.group(0)), t)
        for t in found
    ]


def redirect_targets(command: str) -> list[str]:
    """Файлы, названные перенаправлением вывода.

    Кавычки — данные, а не команда, и искать в них оболочку нельзя. Оператор
    ищется по строке с ЗАГЛУШЕННЫМ содержимым кавычек, а имя файла читается
    из исходной по тому же смещению: длина при заглушении сохраняется.

    # Чем это оплачено

    Прежде цель редиректа в кавычках искалась отдельным регэкспом ПО ВСЕЙ
    строке, до заглушения. 19.08.2026 надзиратель отдавал работнику задачу:

        tz start . frontswitch --effort high -- "… импортируют из
        '.../lib/<файл>' в BuyOrderBot/web и сверь списки имён; …"

    Внутри текста задачи есть `>` (закрывающая скобка `<файл>`), а сразу за
    ним — закрывающая кавычка. Регэксп прочёл это как «перенаправить в файл»
    и взял целью весь текст до следующей кавычки — три абзаца задачи. Гард
    ответил «надзиратель не пишет код» на команду, которой он же и советует
    отдавать работу: `tz` не пишет ничего, он поднимает рабочую сессию.

    Хуже отказа тут его вид: он выглядит как срабатывание правила, а не как
    ошибка разбора, и первым делом переписывают задачу, а не хук.
    """
    bare = mask_quoted(command)
    out: list[str] = []
    for m in REDIRECT_RX.finditer(bare):
        i = m.end()
        while i < len(command) and command[i] in " \t":
            i += 1
        if i >= len(command):
            continue
        ch = command[i]
        if ch in "'\"":
            # `> "имя с пробелом"`: имя целиком до парной кавычки.
            j = command.find(ch, i + 1)
            if j > i:
                out.append(command[i + 1:j])
            continue
        if ch == "&":
            continue  # `2>&1`, `>&2` — это дескриптор, а не файл
        hit = TARGET_RX.match(command, i)
        if hit:
            out.append(hit.group(0))
    return [t for t in out if t not in DISCARDS]


def split_parts(command: str) -> list[str]:
    """Разрезать составную команду по операторам ВНЕ кавычек.

    Резать по сырой строке нельзя по той же причине, что и искать редиректы:
    в тексте задачи, отдаваемой работнику, полно и `;`, и `|`. Разрез по ним
    рвёт строку посреди кавычек, и дальше разбор идёт по обломкам — то есть
    гадает.
    """
    bare = mask_quoted(command)
    parts: list[str] = []
    last = 0
    for m in SPLIT_RX.finditer(bare):
        parts.append(command[last:m.start()])
        last = m.end()
    parts.append(command[last:])
    return parts


def part_targets(part: str) -> list[str]:
    """Цели одной простой команды — без операторов."""
    try:
        tokens = shlex.split(part)
    except ValueError:
        return []  # незакрытая кавычка: что смог — то смог

    if not tokens:
        return []
    base = os.path.basename(tokens[0])
    spec = WRITERS.get(base)
    if spec is None:
        return []

    # Правка на месте — по ключу, а не по имени команды. Ключ бывает слитным
    # со значением (`-i.bak`) и собранным с другими (`-ni`), поэтому смотрим
    # начало короткого ключа, а не равенство.
    flags = INPLACE_ONLY.get(base)
    if flags:
        inplace = any(
            t.startswith(flags[1]) or (t.startswith("-") and not t.startswith("--") and "i" in t)
            for t in tokens[1:]
        )
        if not inplace:
            return []

    positional = [t for t in tokens[1:] if not t.startswith("-")][spec:]
    if not positional:
        return []
    # У перемещения и копирования цель одна — последняя: `mv a b c dir/`
    # пишет только в `dir/`. Считать целями все аргументы значило бы запрещать
    # перенос разрешённого файла в разрешённое же место.
    if base in ("mv", "cp"):
        return positional[-1:]
    return positional


def targets(tool_name: str, tool_input: dict) -> list[str]:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    out: list[str] = []

    if tool_name in SHELL_TOOLS:
        out.extend(shell_targets(tool_input.get("command") or ""))
    else:
        for field in PATH_FIELDS:
            value = tool_input.get(field)
            if isinstance(value, str) and value:
                out.append(value)

    resolved = []
    for raw in out:
        if not a_path(raw):
            continue
        p = os.path.expanduser(raw)
        if not os.path.isabs(p):
            p = os.path.join(project_dir, p)
        # normpath схлопывает `..`, без него относительный путь уходит из
        # разрешённой зоны и сравнение с ней перестаёт что-либо значить.
        resolved.append(os.path.normpath(p))
    return resolved


# a_path — похоже ли это вообще на путь к файлу.
#
# Двоеточие ДО первой косой черты означает, что это не путь: так выглядят
# ревизии git (`HEAD:docs/plans/x.md`, `abc123:CLAUDE.md`) и адреса
# (`https://…`). Ни туда, ни туда никто не пишет.
#
# # Чем это оплачено
#
# 20.08.2026 надзиратель восстанавливал срезанный хвост плана. Скрипт брал
# прежнюю версию через `git show "HEAD:docs/plans/2026-08-19-context-diet.md"`
# и писал её обратно в тот же файл — работа разрешённая от начала до конца.
# Гард ответил отказом с целью
# `…/SyncedProjects/HEAD:docs/plans/2026-08-19-context-diet.md`: пути такого
# нет и не будет, а склеился он из корня репозитория и РЕВИЗИИ.
#
# Споткнулся разбор не на `git` — этой команды гард не знает вовсе и знать не
# должен. Цель записи стояла за переменной цикла, и сработал запасной путь:
# «не разобрал имя — суди по путь-подобным строкам скрипта». Ревизия выглядит
# путём ровно настолько, чтобы в этот отбор попасть.
#
# Проверка одна и дешёвая. Разбирать аргументы git не стали намеренно: гард
# про дисциплину, а не про защиту от намеренного обхода, и каждое новое
# правило разбора приносит свои ложные срабатывания — это уже третий такой
# случай подряд. Настоящий деструктив по рабочему дереву (откат файла к HEAD,
# восстановление, жёсткий сброс, чистка, прятанье) стережёт
# `guard-destructive.py` — проверено фактом, там он блокируется.
def a_path(raw: str) -> bool:
    head = raw.split("/", 1)[0]
    return ":" not in head


def main() -> int:
    if not os.environ.get(ROLE_ENV):
        return 0  # обычная сессия — гард не при делах

    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in WRITE_TOOLS and tool_name not in SHELL_TOOLS:
        return 0

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    blocked = [p for p in targets(tool_name, tool_input) if not allowed(p)]
    if not blocked:
        return 0

    # Отказ говорит, ЧТО не пустили и ЧТО делать вместо этого.
    #
    # Прежний текст советовал `ghostty -e claude -n …` — способ, которого
    # больше нет: рабочие сессии заводит Таусозавр, и надзиратель умеет это
    # сам одной командой. Совет, отсылающий к несуществующему пути, хуже
    # молчания: по нему пробуют, не выходит, и доверие теряет весь отказ.
    sys.stderr.write(
        "BLOCKED: a supervisor does not write code.\n\n"
        f"Target: {blocked[0]}\n\n"
        "Your work ends where the task is formulated and written down.\n"
        "You may write markdown inside `docs/` — plans, notes, the queue — and\n"
        "the root `CLAUDE.md`, the map of the ecosystem. Drafts go to a temporary\n"
        "directory (`/tmp/…`), they affect nothing.\n"
        "Plus your own checkpoint pointer: `.claude/.checkpoint-<host>-<session>`.\n\n"
        "An edit in the code is needed — start a working session and give it the task:\n"
        "  tz start <directory> <name>\n"
        "  tz say <name> \"<what to do>\"\n"
        "It comes up with your scenario and becomes your subordinate."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
