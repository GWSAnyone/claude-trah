#!/usr/bin/env python3
"""PreToolUse: работа с файлами проекта через Bash — вернуть сессию к Serena.

Два режима. `warn` (по умолчанию) — код возврата 0, команда выполняется, а в
контекст уходит короткая строгая строка. `block` — код возврата 2, вызов не
состоится, причина и замена уезжают модели как ошибка. Режим берётся из
`NUDGE_SERENA_MODE`, иначе из аргумента (`nudge-serena.py block` в настройках),
иначе `warn`.

Что режим `block` НЕ запрещает — и это главное, чтобы не выстрелить себе в ногу.
Python остаётся калькулятором: считать по журналам, разбирать JSON, мерить,
ходить по сети, запускать процессы — всё это Serena не умеет вовсе, и запрещать
это значит остаться без арифметики. Запрещается ровно то, для чего у Serena есть
прямой инструмент: читать файл проекта ради содержимого и править файл проекта
вслепую. Код, который открывает файл проекта на ЧТЕНИЕ и печатает числа, а не
тело файла, проходит в обоих режимах.

Зачем именно так. Инструменты Serena отложены: пока сессия не позвала
`ToolSearch`, их нет в списке доступных, а `grep` и `cat` — есть. Рука тянется
к тому, что под рукой, и это не разовая оплошность: 20.08.2026 сессия с живым
сервером Serena сделала семнадцать вызовов Bash и ни одного символьного. Одно
напоминание в стиле вывода привычку не перебивает: стиль приходит раньше
работы, а соблазн — во время неё.

Ловятся оба обхода одним хуком, потому что беда у них одна:

  чтение   `grep`, `rg`, `cat`, `head`, `tail`, `sed -n`, `awk`, `find`
  правка   `sed -i`, `perl -i`, `tee`, перенаправления `>` и `>>`,
           однострочники и heredoc'и `python`, `node`, `perl`, `ruby`

# Устройство разбора — по тому, как сессии зовут это НА САМОМ ДЕЛЕ

Формы взяты не из головы: 21.08.2026 разобраны 5782 команды Bash из 120
транскриптов. Оттуда три вывода, каждый стоил бы дыры в проверке.

**`cd` начинает 3599 команд из 5782.** Пути в них относительны каталогу
ПОСЛЕ `cd`, а не каталогу сессии: `cd ~/Ledevia/tausozavr && sed -n 1,60p
internal/x.go`. Проверка «путь внутри проекта» от каталога сессии промахнулась
бы на большинстве команд, и хук молчал бы ровно там, где нужен. Поэтому `cd`
отслеживается посегментно.

**Инструмент редко стоит первым.** После `&&` — 725 grep и 687 sed, после `;`
— 707 grep, внутри `$( )` — 136, есть `command grep` (119) и вызовы из
`find -exec` и `xargs`. Поэтому сегментами считаются и подстановки, а обёртки
(`command`, `env`, `sudo`, `xargs`) снимаются.

**`head` и `tail` в 4154 случаях — фильтры после трубы**, и это законно.
Поэтому решает не место в конвейере, а НАЛИЧИЕ ФАЙЛОВОГО ОПЕРАНДА внутри
проекта: `go test ./... | head -20` молчит, `echo x | grep foo internal/y.go`
— нет. Труба учитывается лишь для рекурсии без пути (`grep -r pat`), где
операнда нет вовсе.

Непробиваемым это не будет: команду можно собрать в переменной, закодировать,
спрятать в скрипт. Задача другая — ловить обычные формы, которыми обход и
происходит на деле.
"""

import json
import os
import re
import shlex
import sys

# Команды, печатающие содержимое файла. Список пополнен 02.09.2026 после
# замера: восемь форм проходили мимо гарда и вываливали в контекст от 4 до
# 92 КБ. Повод посмотреть — changelog Claude Code 2.1.259, где Anthropic
# чинили тот же класс дыр в своих `Read()`-правилах: файл как значение опции,
# операнды `git`, составные команды.
READERS = frozenset({
    "grep", "rg", "ag", "cat", "head", "tail", "sed", "awk", "find",
    # печатают тело файла целиком или почти целиком
    "nl", "tac", "bat", "od", "xxd", "hexdump", "strings", "base64",
    "pr", "fold", "expand", "unexpand", "rev", "cut", "column", "dd",
    "less", "more",
})

# PowerShell делает то же самое другими именами. Без них хук пропускал целую
# оболочку: `tool_name` он принимал, а `Get-Content D:\проект\файл.go` не
# узнавал — дисциплина обходилась не хитростью, а сменой оболочки. Регистр
# складываем: PowerShell его не различает. Алиасов `sc`/`ac` нет намеренно:
# `sc` — ещё и управление службами Windows. (Порт tausozavr, 23.08.2026.)
_PS_READERS = frozenset({"get-content", "gc", "type", "select-string", "sls"})
_PS_WRITERS = frozenset({"set-content", "add-content", "out-file"})

# Подкоманды `git`, печатающие СОДЕРЖИМОЕ файла, а не сводку о нём.
# `git diff HEAD -- файл`, `git log`, `git status` сюда не входят намеренно:
# они печатают разницу, историю и состояние — ровно то, ради чего Bash и
# нужен, и чего в Serena нет.
_GIT_ПЕЧАТАЮЩИЕ = frozenset({"grep", "show", "cat-file", "blame", "annotate"})
INTERPRETERS = frozenset({"python", "python3", "node", "bun", "perl", "ruby", "php"})
INLINE_FLAGS = frozenset({"-c", "-e", "--eval", "-"})

# Обёртки, за которыми стоит настоящая команда.
WRAPPERS = frozenset({
    "sudo", "env", "nohup", "command", "time", "stdbuf", "nice", "xargs",
    "timeout", "builtin", "exec", "setsid", "ionice",
})
# Обёртки из двух слов: `uv run python …`.
RUNNERS = frozenset({"uv", "poetry", "pipx", "pdm", "rye", "hatch"})
# Оболочки: `bash -c '<команда>'` прячет команду в строке.
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish"})

# `cp` и `mv` намеренно НЕ считаются правкой. Проверено по 5782 настоящим
# командам: это перенос и раскладка файлов, а не правка содержимого, и
# инструмента для них у Serena нет вовсе. Плюс `cp` — предписанный способ
# сделать бэкап перед опасной операцией; ругаться на него значит ругаться на
# осторожность.

# Разделители, после которых начинается НОВАЯ команда. Подстановки `$( )` и
# обратные кавычки — тоже: внутри них команда своя.
_SEP = re.compile(r"(\|\||&&|\||;|\n|\$\(|`|\))")
# Те же разделители списком, длинные первыми: нарезка ниже идёт по строке
# посимвольно, и `||` обязан рассматриваться раньше `|`.
_SEP_TOKENS = ("||", "&&", "$(", "|", ";", "\n", "`", ")")
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# Кандидаты в пути внутри чужого кода: с разделителем каталогов или с точкой.
_PATHISH = re.compile(r"[\w./~-]*[/.][\w./~-]+")
# Настоящее расширение файла — чтобы отличить `internal/new.go` от `./...`.
_WITH_EXT = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,5}$")

# Наши рабочие деревья задаются НАСТРОЙКОЙ, а не тем, что сейчас активировано в
# Serena. Комплект уехал в Таусозавр, репозиториев стало несколько, и метка
# `.serena/project.yml` перестала совпадать с ответом на вопрос «наше ли это».
# Дерево без метки (`asynchronus`) хук не видел вовсе.
# Модули, которые ПЕЧАТАЮТ содержимое файла, то есть работают как `cat`.
# Всё остальное, запущенное через `-m` над проектным путём, — исполнение:
# проверка синтаксиса, прогон тестов, установка зависимостей.
_МОДУЛИ_ПЕЧАТАЮЩИЕ = frozenset({"json.tool", "pprint", "tokenize", "dis"})

_ROOTS_ENV = "NUDGE_SERENA_ROOTS"
_ROOTS_DEFAULT = "~/Ledevia"

# По-настоящему чужое, где встроенные инструменты законны: системные каталоги,
# временные песочницы, чужие дома. Соседний НАШ репозиторий чужим не является —
# именно этой лазейкой символьный слой обходился целый день.
_FOREIGN_PREFIXES = (
    "/tmp", "/var", "/etc", "/usr", "/opt", "/srv", "/proc", "/sys",
    "/dev", "/run", "/boot", "/nix", "/snap", "/lost+found",
)
_HOME_BASES = ("/home", "/Users", "/root")
if os.name == "nt":
    # Системное и временное под Windows. Дома других пользователей — `C:\Users`.
    _FOREIGN_PREFIXES += tuple(p for p in (
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        os.environ.get("TEMP", ""),
    ) if p)
    _HOME_BASES += (os.path.dirname(os.path.expanduser("~")),)

# По-английски и коротко: это команда себе, а не объяснение владельцу.
# Длинное вежливое напоминание читается как совет, а совет можно и не взять.
READ_MSG = (
    "STOP — Bash is not a reading tool. Serena MCP is mandatory for project "
    "files: find_symbol · get_symbols_overview · find_referencing_symbols · "
    "search_for_pattern (scoped). Use it to its full extent."
)
WRITE_MSG = (
    "STOP — Bash is not an editing tool. sed/heredoc/one-liners edit blind: "
    "no result shown, a missed pattern is as silent as a hit. Serena MCP is "
    "mandatory: replace_symbol_body · replace_content · insert_after_symbol."
)

# В режиме `block` текст уходит как ошибка вызова, поэтому в нём есть замена:
# отказ без замены заставляет сессию искать обход, а не менять способ.
BLOCK_READ_MSG = (
    "BLOCKED: Bash is not a reading tool for project files. Serena: find_symbol · "
    "get_symbols_overview · find_referencing_symbols · search_for_pattern (scoped; "
    "several branches at once — braces in paths_include_glob). Outside the project "
    "tree the built-in Read/Grep are right."
)
BLOCK_WRITE_MSG = (
    "BLOCKED: Bash edits project files blind. Serena: replace_symbol_body · "
    "replace_content · insert_after_symbol; a brand-new file — Write. A program "
    "that must process files goes into a file (Write) and prints a report, not "
    "file bodies."
)
BULK_MSG = (
    "Inline program of {n} lines: put it in a file (Write) and run it by name. "
    "The argument text is re-sent with the whole context on every following turn; "
    "a file is paid for once and re-runs cost nothing. "
    "JSON from curl or an API: pipe it to jq with one filter instead of a program."
)

# Программа, набранная в аргументе, дороже своего вывода: 20.08.2026 она стоила
# 597 108 токенов за три дня. Десять строк И БОЛЬШЕ — уже файл: проверка ниже
# идёт по `>=`, и ровно десять строк она отклоняет. Формулировка важна, потому
# что бриф 29.08.2026 говорил «длиннее десяти», то есть разрешал ту самую
# программу, которую хук отвергал; расхождение стоило хода.
BULK_LINES = 10

# Код, который ПИШЕТ. Всё остальное, что открывает файл проекта, считается
# вычислением и проходит: python как калькулятор — это то, чего Serena не умеет.
# Размен осознанный: запись, не попавшая в эти образцы, пройдёт молча.
_CODE_WRITE = re.compile(
    r"""open\s*\([^)]*['"][wax]b?\+?['"]     # open(path, "w") и родня
      | \.write_text\s*\( | \.write_bytes\s*\(
      | \.writelines\s*\( | \bwritelines\s*\(
      | \bwriteFileSync\b | \bappendFileSync\b
      | \bshutil\.(?:copy|copy2|move|copytree)\b
      | \bos\.(?:remove|unlink|rename|replace|truncate)\b
      | \bunlink\s*\( | \bmkdir\s*\(
      | \bFile\.write\b
    """,
    re.X,
)
# Heredoc — не обязательно программа. `git commit -F- <<MSG`, `cat > файл <<EOF`,
# `mail <<EOF` кладут в него ТЕКСТ, и считать его кодом нельзя: проверено на
# собственном коммите 22.08, хук обругал сообщение на 31 строку, а в режиме
# `block` отменил бы сам коммит. Телом кода считается heredoc только у того, кто
# умеет его исполнять.
_INTERPRETER_CALL = re.compile(
    r"(?:^|[\s|;&(])(?:python3?|node|bun|perl|ruby|php|sh|bash|zsh|dash|ksh)(?:\s|$)"
)

# Строка кода после `-c`, `-e`, `--eval` — вместе с кавычками, в которых она
# приехала. Скобки внутри неё разбору командной строки не по зубам.
_INLINE_ARG = re.compile(r"""(?:^|\s)(?:-c|-e|--eval)\s+(?:'([^']*)'|"([^"]*)"|(\S+))""")

# Чтение как подмена `cat`: содержимое файла прямиком в вывод.
_CODE_DUMP = re.compile(
    # `[^\n]*`, а не `[^)]*`: между `print(` и `.read(` стоит `open('файл')`,
    # и на его закрывающей скобке разбор обрывался бы, не дойдя до чтения.
    r"(?:print|sys\.stdout\.write|console\.log)\s*\([^\n]*\.read(?:_text|lines)?\s*\("
)


def strip_heredocs(command: str) -> str:
    """Команда без тел heredoc: внутри `<<'PY' … PY` лежит текст, а не команды."""
    out: list[str] = []
    terminator: str | None = None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        out.append(line)
        if m := _HEREDOC_START.search(line):
            terminator = m.group(2)
    return "\n".join(out)


def our_roots() -> list[str]:
    """Корни наших рабочих деревьев — из настройки `NUDGE_SERENA_ROOTS`.

    Разделитель — как в `PATH`. Пустое значение означает «настройки нет»: тогда
    остаётся прежний способ, по метке `.serena/project.yml`, и получатель
    комплекта без `~/Ledevia` ничего не теряет.
    """
    raw = os.environ.get(_ROOTS_ENV)
    if raw is None:
        raw = _ROOTS_DEFAULT
    roots = []
    for item in raw.split(os.pathsep):
        item = item.strip()
        if item:
            roots.append(os.path.realpath(os.path.expanduser(item)))
    return roots


def under(path: str, parent: str) -> bool:
    """Лежит ли `path` внутри `parent` (или совпадает с ним).

    Разделителем ЭТОЙ ОС и со складыванием регистра. Проверка по одной `/`
    под Windows не совпадала ни разу: `realpath` отдаёт `D:\\проект`, и
    объявленные корни молча переставали быть нашими. (Порт tausozavr.)
    """
    path = os.path.normcase(path).rstrip(os.sep)
    parent = os.path.normcase(parent).rstrip(os.sep)
    if not parent:  # корень POSIX `/` после rstrip
        return True
    return path == parent or path.startswith(parent + os.sep)


def foreign(path: str) -> bool:
    """По-настоящему чужое: система, временная песочница, чужой дом.

    Свой дом чужим не считается, а вот `/home/кто-то-другой` — считается.
    Проверка идёт ПОСЛЕ настроенных корней: если корень объявлен явно, он наш,
    где бы ни лежал (так тесты и работают из `/tmp`).
    """
    if any(under(path, prefix) for prefix in _FOREIGN_PREFIXES):
        return True
    home = os.path.realpath(os.path.expanduser("~"))
    return any(under(path, base) and not under(path, home) for base in _HOME_BASES)


def our_tree(path: str) -> bool:
    """Наше ли это рабочее дерево — то, где дисциплина обязательна.

    Три источника ответа, по убыванию силы:

    1. настроенный корень — наш всегда. Список деревьев задаётся снаружи, а не
       выводится из того, какой проект сейчас активирован в Serena: активен
       ровно один, а репозиториев у нас несколько;
    2. заведомо чужое — не наше никогда, даже с меткой внутри. Клон в песочнице
       под `/tmp` метку `.serena/project.yml` носит, но чужим быть не перестаёт;
    3. всё остальное — по-старому, меткой вверх по дереву.
    """
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        path = os.path.dirname(path)
    if any(under(path, root) for root in our_roots()):
        return True
    if foreign(path):
        return False
    home = os.path.realpath(os.path.expanduser("~"))
    while True:
        # Сам домашний каталог проектом НЕ считается, даже с меткой внутри.
        #
        # `~/.serena/project.yml` существует — дом зарегистрирован в Serena как
        # проект «kaltsit». Без этой остановки обход вверх упирался в него, и
        # «нашим деревом» становился ВЕСЬ дом: любая разовая сессия в `~`,
        # `~/Downloads`, `~/tmp-что-нибудь` получала полную дисциплину, хотя
        # символьного слоя там нет и быть не должно (у домашнего проекта
        # `language_servers: []`). Дом — место, где живут, а не проект.
        #
        # Настоящие рабочие деревья это не ослабляет: `~/Ledevia` объявлен
        # корнем выше, а `~/lom-ru` и прочие несут собственную метку и
        # находятся обходом ДО того, как он дойдёт до дома.
        if path == home:
            return False
        if os.path.isfile(os.path.join(path, ".serena", "project.yml")):
            return True
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def resolve(token: str, cwd: str) -> str:
    return os.path.join(cwd, os.path.expanduser(token.strip("'\"")))


def project_path(token: str, cwd: str) -> bool:
    """Существующий путь внутри проекта Serena."""
    token = token.strip("'\"")
    if not token or token.startswith("-"):
        return False
    candidate = resolve(token, cwd)
    return os.path.exists(candidate) and our_tree(candidate)


def project_target(token: str, cwd: str) -> bool:
    """Путь, КУДА пишут: существовать он не обязан.

    Отдельно от `project_path`, потому что создание файла — самый частый вид
    правки вслепую (`cat > internal/new.go <<'EOF'`), а требование
    существования пропускало бы ровно его. Достаточно, чтобы каталог назначения
    был внутри проекта.
    """
    token = token.strip("'\"")
    if not token or token.startswith("-"):
        return False
    candidate = resolve(token, cwd)
    parent = os.path.dirname(candidate) or cwd
    return os.path.isdir(parent) and our_tree(parent)


def code_touches_project(text: str, cwd: str) -> bool:
    """Есть ли в тексте кода путь к файлу проекта — существующему или новому.

    Новый файл учитывается по расширению (`internal/new.go`), а не по одному
    лишь наличию каталога: иначе `go build ./...` внутри кода считалось бы
    обращением к проекту, потому что каталог у него — сам проект.
    """
    for m in _PATHISH.finditer(text):
        token = m.group(0)
        if project_path(token, cwd):
            return True
        # Файл, которого ещё нет. Требуем разделитель каталогов: без него
        # обращение к полю (`m.group`, `os.path`, `p.read_text`) неотличимо от
        # имени файла с расширением — проверено на себе, хук ругался на разбор
        # собственных транскриптов.
        if "/" not in token:
            continue
        if _WITH_EXT.search(os.path.basename(token.strip("'\""))) and project_target(token, cwd):
            return True
    return False


def heredoc_bodies(command: str) -> str:
    """Тела всех heredoc'ов команды — это и есть код, набранный на месте.

    Нужны отдельно: разбор команды их выбрасывает, а именно в них и лежит
    правка вроде `pathlib.Path('internal/x.go').write_text(...)`.
    """
    out: list[str] = []
    terminator: str | None = None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            else:
                out.append(line)
            continue
        if m := _HEREDOC_START.search(line):
            terminator = m.group(2)
    return "\n".join(out)


def inline_code(command: str) -> str:
    """Код, набранный ПРЯМО в аргументе: тела heredoc'ов и строки после `-c`.

    Разбирается регуляркой, а не `shlex`: в коде полно скобок и кавычек, на
    которых обычный разбор командной строки спотыкается — `python3 -c
    "print(open('x').read())"` для `shlex` просто незакрытая кавычка.
    """
    # Интерпретатор ищется в САМОЙ КОМАНДЕ, без тел heredoc. Раньше поиск шёл по
    # всей строке вместе с телом, и слово `bash` ВНУТРИ сообщения коммита
    # объявляло это сообщение кодом. Проверено запуском 29.08.2026: коммит с
    # сообщением на десять строк, где встречается «запуск через bash», в режиме
    # `block` отменялся целиком. В этом репозитории такое сообщение — норма.
    #
    # Это ровно тот случай, ради которого `_INTERPRETER_CALL` и писался 22.08:
    # телом кода heredoc считается только у того, кто умеет его исполнять. Но
    # проверка смотрела и в само тело, то есть отвечала на свой вопрос его же
    # содержимым.
    code = heredoc_bodies(command) if _INTERPRETER_CALL.search(
        strip_heredocs(command)) else ""
    for match in _INLINE_ARG.finditer(command):
        code += "\n" + next((g for g in match.groups() if g is not None), "")
    return code


def tokens_of(segment: str) -> list[str]:
    """Слова сегмента.

    Под Windows обратная косая — РАЗДЕЛИТЕЛЬ ПУТИ, а не экранирование: POSIX-
    режим `shlex` делал из `D:\\проект\\файл.go` `D:проектфайл.go`, путь
    переставал быть путём, и хук молча пропускал чтение файла проекта.
    (Порт tausozavr, найдено пробой 23.08.2026.)
    """
    if os.name == "nt":
        lexer = shlex.shlex(segment, posix=True)
        lexer.whitespace_split = True
        lexer.escape = ""
        try:
            return list(lexer)
        except ValueError:
            return segment.split()
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def chdir_target(tokens: list[str]) -> str | None:
    """`cd X` — куда. Иначе None."""
    i = 0
    while i < len(tokens) and _ENV_ASSIGN.match(tokens[i]):
        i += 1
    if i < len(tokens) and tokens[i] == "cd" and i + 1 < len(tokens):
        return tokens[i + 1]
    return None


def _правит_на_месте(флаг: str) -> bool:
    """Флаг `sed`/`perl`, означающий правку файла НА МЕСТЕ.

    Раньше признаком была любая буква `i` в любом флаге, и под это попадало
    всё подряд. Проверено запуском 29.08.2026 в режиме `block`: `sed --version`
    отменялся как «слепая правка проекта», а вместе с ним `perl --version`,
    `rg perl --ignore-case` и `rg sed --line-number` — потому что слово `sed`
    или `perl` стояло операндом поиска, а `i` находилась в `version`,
    `ignore-case`, `line-number`.

    Короткий флаг — связка букв, и `i` в ней настоящая (`-i`, `-i.bak`, `-pi`).
    Длинный флаг обязан быть именно `--in-place`.
    """
    if not флаг.startswith("-"):
        return False
    if флаг.startswith("--"):
        return флаг == "--in-place" or флаг.startswith("--in-place=")
    return "i" in флаг[1:]


# Флаги, при которых команда ничего не читает, а рассказывает о себе. Без них
# `rg --version` и `find --version` считались рекурсивным чтением проекта:
# операндов нет, имя в списке рекурсивных — значит «читает от текущего
# каталога». Проверено запуском 29.08.2026, оба отменялись.
_СПРАВОЧНЫЕ = frozenset({"--version", "--help", "--usage", "-V", "-h"})


def redirects_to_project(tokens: list[str], cwd: str) -> bool:
    for i, token in enumerate(tokens):
        target = ""
        if token in (">", ">>") and i + 1 < len(tokens):
            target = tokens[i + 1]
        elif token.startswith(">") and len(token) > 1:
            target = token.lstrip(">")
        if not target:
            continue
        # `>&2` — это дескриптор, а не файл. Снятие ведущих `>` оставляло `&2`,
        # и `project_target` признавал его файлом в каталоге проекта, потому
        # что каталог-родитель существует. Так `echo проверка >&2` отменялся
        # как правка проекта. Числовая цель — тот же случай: `2>` и `1>`
        # перенаправляют дескриптор, а `$((2 > 1))` вообще арифметика.
        if target.startswith("&") or target.isdigit():
            continue
        if project_target(target, cwd):
            return True
    return False


def redirect_inputs(tokens: list[str]) -> list[str]:
    """Файлы, отданные команде на ВХОД: `nl < internal/x.go`.

    Для печатающей команды это тот же вывод содержимого, что и с операндом,
    только запись другая. Для `wc -l < файл` — нет: наружу уезжает число, и
    такие команды в READERS не значатся, так что список им не повредит.
    """
    цели = []
    for i, token in enumerate(tokens):
        if token == "<" and i + 1 < len(tokens):
            цели.append(tokens[i + 1])
        elif token.startswith("<") and len(token) > 1 and not token.startswith("<<"):
            цели.append(token.lstrip("<"))
    return цели


def option_values(args: list[str]) -> list[str]:
    """Правые половины `опция=значение`: `dd if=файл`, `--file=файл`.

    Нарезка по пробелам оставляла такой аргумент цельным, и путь внутри него
    не проверялся вовсе. Применять можно только к аргументам ПОСЛЕ имени
    команды: до него та же форма означает переменную окружения.
    """
    return [a.split("=", 1)[1] for a in args if "=" in a]


def git_dump_target(sub: str, operands: list[str], flags: list[str],
                    cwd: str) -> bool:
    """Печатает ли этот вызов `git` содержимое файла проекта."""
    остальное = [a for a in operands if a != sub]
    if sub == "grep":
        # То же самое, что `grep -r` по дереву: наружу уезжают строки файлов
        # проекта. Для этого есть `search_for_pattern`.
        return our_tree(cwd) or any(project_path(a, cwd) for a in остальное)
    if sub in ("show", "cat-file"):
        # `git show HEAD:путь` — слева ревизия, справа путь в дереве.
        цели = остальное + [a.split(":", 1)[1] for a in остальное if ":" in a]
        return any(project_path(a, cwd) for a in цели)
    if sub in ("blame", "annotate"):
        # С `-L` разбор нацелен на диапазон строк и содержимое не выливает;
        # без него blame печатает файл целиком. Запрещать вместе с диапазоном
        # значило бы отнять вопрос «кто менял эту строку», на который в Serena
        # ответа нет вовсе.
        if any(f.startswith("-L") for f in flags):
            return False
        return any(project_path(a, cwd) for a in остальное)
    if sub == "diff" and "--no-index" in flags:
        # Файл вне индекса печатается целиком, а не разницей: это `cat`.
        return any(project_path(a, cwd) for a in остальное)
    return False


def classify_segment(tokens: list[str], segment: str, raw: str, cwd: str, piped: bool) -> str | None:
    """Что сегмент делает с файлами проекта: 'read', 'write' или ничего."""
    if not tokens:
        return None

    if redirects_to_project(tokens, cwd):
        return "write"

    # Правка на месте — где бы вызов ни стоял внутри сегмента: `find … -exec
    # sed -i …`, `xargs sed -i`, `command sed -i`. Ищем по всем токенам.
    for i, token in enumerate(tokens):
        if os.path.basename(token) not in ("sed", "perl"):
            continue
        rest = tokens[i + 1:]
        if any(_правит_на_месте(f) for f in rest):
            # `{}`, `+`, `;` — не пути, а сборка вызова у `find -exec`.
            paths = [a for a in rest
                     if not a.startswith("-") and a not in ("{}", "+", ";", "\\;")]
            # Первый операнд — сам скрипт (`s/a/b/`), если он не задан флагом.
            if paths and not any(f.lstrip("-").startswith(("e", "f")) for f in rest if f.startswith("-")):
                paths = paths[1:]
            if any(project_path(a, cwd) for a in paths):
                return "write"
            # Пути нет — правка идёт по тому, что подставит `find`/`xargs`,
            # то есть по текущему дереву.
            if not paths and our_tree(cwd):
                return "write"

    i = 0
    while i < len(tokens):
        head = os.path.basename(tokens[i])
        if _ENV_ASSIGN.match(tokens[i]) or head in WRAPPERS:
            i += 1
            continue
        # `uv run python -c …`, `poetry run …` — обёртка из двух слов.
        if head in RUNNERS and i + 1 < len(tokens) and tokens[i + 1] == "run":
            i += 2
            continue
        break
    if i >= len(tokens):
        return None
    name = os.path.basename(tokens[i])
    args = tokens[i + 1:]

    # `bash -c 'grep … internal/x.go'` — команда спрятана в строке, и разбирать
    # её надо как команду, а не как аргумент.
    if name in SHELLS:
        for j, arg in enumerate(args):
            if arg == "-c" and j + 1 < len(args):
                return classify(args[j + 1], cwd)
        return None
    flags = [a for a in args if a.startswith("-")]
    operands = [a for a in args if not a.startswith("-")]

    if name.lower() in _PS_WRITERS:
        return "write" if any(project_target(a, cwd) for a in operands) else None
    if name.lower() in _PS_READERS:
        return "read" if any(project_path(a, cwd) for a in operands) else None

    if name == "tee":
        return "write" if any(project_target(a, cwd) for a in operands) else None

    # `dd of=файл` — запись, но не перенаправление, поэтому мимо
    # `redirects_to_project`. Чтение (`if=`) ловится ниже вместе с READERS.
    if name == "dd":
        for a in args:
            if a.startswith("of=") and project_target(a[3:], cwd):
                return "write"

    if name == "git":
        # Общие ключи `git` идут ДО подкоманды, и два из них берут значение
        # отдельным словом. Без этого `git -C /tmp grep` разбирался как
        # подкоманда `/tmp`, и правило не срабатывало вовсе — а значит и
        # `git -C <каталог-проекта> grep` проходил мимо.
        здесь, sub, j = cwd, "", 0
        while j < len(args):
            a = args[j]
            if a == "-C" and j + 1 < len(args):
                перенос = resolve(args[j + 1], здесь)
                if os.path.isdir(перенос):
                    здесь = перенос
                j += 2
                continue
            if a == "-c" and j + 1 < len(args):
                j += 2
                continue
            if a.startswith("-"):
                j += 1
                continue
            sub = a
            break
        if sub in _GIT_ПЕЧАТАЮЩИЕ or sub == "diff":
            хвост = [a for a in args[j + 1:] if not a.startswith("-")]
            if git_dump_target(sub, [sub] + хвост, flags, здесь):
                return "read"
        return None

    if name in INTERPRETERS:
        # Считается только код, набранный ПРЯМО ЗДЕСЬ: запуск файла
        # (`python3 tools/x.py`) — исполнение, и оно молчит.
        #
        # Смотрим код именно этого вызова, а не всю команду: heredoc где-то
        # рядом и путь к проекту в соседнем сегменте — не повод объявлять
        # правкой запуск проверочного скрипта.
        code = ""
        for j, arg in enumerate(args):
            if arg in ("-c", "-e", "--eval") and j + 1 < len(args):
                code += "\n" + args[j + 1]
        if "<<" in segment or "-" in args:
            code += "\n" + heredoc_bodies(raw)
        if code.strip() and code_touches_project(code, cwd):
            # Три разных дела с одинаковым синтаксисом. Пишет — этому есть
            # прямая замена в Serena. Печатает тело файла — это `cat` в обход.
            # Всё прочее — вычисление над файлом, и оно законно: содержимое в
            # контекст не попадает, попадают числа.
            if _CODE_WRITE.search(code):
                return "write"
            if _CODE_DUMP.search(code):
                return "read"
            return None
        # `python3 -m json.tool файл-проекта` — модуль запущен над чужим
        # файлом: это чтение, а не исполнение своего скрипта.
        # Правило метило в `python3 -m json.tool файл`, но было написано шире:
        # ЛЮБОЙ модуль с проектным путём считался чтением. Под это попадали
        # `python3 -m py_compile файл` и `python3 -m pytest каталог` — проверка
        # синтаксиса и прогон тестов, где в контекст уезжает отчёт, а не тело
        # файла. Проверено запуском 29.08.2026: отменялись.
        #
        # Поэтому список модулей, которые действительно печатают содержимое.
        if "-m" in args:
            модуль = next((a for a in args[args.index("-m") + 1:]
                           if not a.startswith("-")), "")
            if модуль in _МОДУЛИ_ПЕЧАТАЮЩИЕ:
                after = [a for a in args[args.index("-m") + 2:] if not a.startswith("-")]
                if any(project_path(a, cwd) for a in after):
                    return "read"
        # `perl -pe '' файл`, `ruby -ne '…' файл` — неявный цикл «прочитать и
        # напечатать». Кода в нём нет или почти нет, поэтому разбор выше
        # ничего не находит, а на выход уезжает файл целиком. Замер
        # 02.09.2026: `perl -pe '' README.md` выливал 13 КБ мимо гарда.
        if name in ("perl", "ruby") and any(
                re.fullmatch(r"-[a-zA-Z]*[pn][a-zA-Z]*", f) for f in flags):
            if any(project_path(a, cwd) for a in operands):
                return "read"
        return None

    if name in READERS:
        # Путь приходит тремя способами, и раньше проверялся только первый:
        # операндом, значением опции (`dd if=файл`) и перенаправлением на
        # вход (`nl < файл`).
        цели = operands + option_values(args) + redirect_inputs(tokens)
        if any(project_path(a, cwd) for a in цели):
            return "read"
        # Каталог назван ЯВНО и он не наш — смотрят наружу, и это не наше дело.
        #
        # Иначе рекурсивная команда с чужим путём, запущенная из каталога
        # проекта, попадала под правило «пути нет, значит от текущего каталога».
        # Живой промах 28.08.2026: `find ~/.local/share/claude -maxdepth 1` —
        # осмотр установленных версий Claude Code, то есть ровно то, для чего
        # Bash и нужен, — был заблокирован как чтение проектных файлов.
        #
        # Признак пути, а не образца поиска: косая черта или тильда. Проверять
        # `_PATHISH` нельзя — под него попадает и `grep -rn 'foo.bar'`, а там
        # операнд это регулярка, и правило «от текущего каталога» обязано
        # остаться в силе.
        named = [a for a in operands if "/" in a or a.startswith("~")]
        if named:
            return None
        # Пути нет: рекурсия идёт от текущего каталога. После трубы это фильтр
        # над чужим выводом, а не чтение файлов.
        # Команда рассказывает о себе — она ничего не читает.
        if any(f in _СПРАВОЧНЫЕ for f in flags) and not operands:
            return None
        recursive = name in ("rg", "ag", "find") or any(
            re.fullmatch(r"-[a-zA-Z]*[rR][a-zA-Z]*", f) for f in flags
        )
        if not piped and recursive and our_tree(cwd):
            return "read"
    return None


def split_segments(text: str) -> list[str]:
    """Нарезка на команды, НЕ заглядывающая внутрь кавычек.

    Форма ответа та же, что у `_SEP.split`: чётные позиции — сегменты, нечётные
    — разделители между ними.

    ЗАЧЕМ СВОЯ. Регулярка режет по всему тексту разом, и разделитель ВНУТРИ
    строкового аргумента разваливает команду на куски, которых пользователь не
    писал. Живой промах 28.08.2026:

        gh issue list --jq '.[] | select(.createdAt > "2026-08-20")'

    Кавычки регулярку не остановили, `|` внутри `--jq` разрезал команду, и
    обрывок `select(.createdAt > "2026-08-20"` прочитался как перенаправление в
    файл `2026-08-20` — путь без каталога, то есть внутри проекта. Осмотр чужих
    issue был объявлен правкой проектных файлов вслепую и заблокирован.
    """
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            # В двойных кавычках обратный слэш экранирует следующий знак; в
            # одинарных он обычный символ, и закрывает их только сама кавычка.
            if ch == "\\" and quote == '"' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(text[i + 1])
            i += 2
            continue
        for sep in _SEP_TOKENS:
            if text.startswith(sep, i):
                parts.append("".join(buf))
                buf = []
                parts.append(sep)
                i += len(sep)
                break
        else:
            buf.append(ch)
            i += 1
    parts.append("".join(buf))
    return parts


def classify(command: str, cwd: str) -> str | None:
    verdict: str | None = None

    # Код в аргументе разбирается ДО нарезки на сегменты: нарезка идёт по
    # скобкам в том числе, а в коде их полно — `print(open('x').read())`
    # разваливается на куски, и ни в одном из них уже ничего не видно.
    code = inline_code(command)
    if code.strip() and code_touches_project(code, cwd):
        if _CODE_WRITE.search(code):
            return "write"
        if _CODE_DUMP.search(code):
            return "read"

    parts = split_segments(strip_heredocs(command))
    piped = False
    here = cwd
    видели_путь = False  # проектный путь встречался в предыдущих сегментах
    for index, part in enumerate(parts):
        if index % 2 == 1:
            piped = part.strip() == "|"
            continue
        segment = part.strip()
        if not segment:
            continue
        tokens = tokens_of(segment)
        # `cd` меняет каталог для ВСЕГО, что идёт дальше по команде: именно так
        # выглядит большинство команд («cd проект && …»), и без этого пути в
        # них не разрешаются.
        if target := chdir_target(tokens):
            moved = resolve(target, here)
            if os.path.isdir(moved):
                here = moved
            continue
        got = classify_segment(tokens, segment, command, here, piped)
        # `echo internal/x.go | xargs cat` — путь приезжает по трубе и
        # становится АРГУМЕНТОМ, поэтому в самом сегменте его нет и разбор
        # сегмента честно ничего не находит. Замер 02.09.2026: форма проходила
        # мимо и выливала файл целиком. Правило узкое — только `xargs`, потому
        # что он один превращает поток в аргументы; `ls проект | head` читает
        # чужой вывод, а не файлы, и обязан остаться законным.
        if (got is None and piped and видели_путь and tokens
                and os.path.basename(tokens[0]) == "xargs"
                and any(os.path.basename(t) in READERS for t in tokens[1:])):
            got = "read"
        if got == "write":
            return "write"  # правка важнее: о ней и говорим
        if got:
            verdict = got
        if any(project_path(t, here) for t in tokens):
            видели_путь = True
    if verdict is None and len(inline_code(command).strip().splitlines()) >= BULK_LINES:
        return "bulk"
    return verdict


def mode() -> str:
    """`warn`, `block` или `off`: сначала окружение, потом аргумент, иначе умолчание.

    Окружение старше аргумента намеренно. Аргумент — долговременная проводка в
    настройках, а `NUDGE_SERENA_MODE=block` — решение на одну сессию, и оно
    должно уметь перебить проводку, не переписывая её.

    `off` нужен профилям Притонозавра: уклад, работающий вне дерева Serena,
    получал бы одни ложные срабатывания, а выключать хук правкой настроек ради
    одного уклада значит выключать его для всех.
    """
    РЕЖИМЫ = ("warn", "block", "off")
    value = (os.environ.get("NUDGE_SERENA_MODE") or "").strip().lower()
    if value in РЕЖИМЫ:
        return value
    if len(sys.argv) > 1:
        value = sys.argv[1].strip().lower()
        if value in РЕЖИМЫ:
            return value
    return "warn"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    if payload.get("tool_name") not in ("Bash", "PowerShell"):
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    cwd = payload.get("cwd") or os.getcwd()
    if not command:
        return 0

    режим = mode()
    # `off` проверяется ДО разбора команды: выключенный хук не должен стоить
    # даже времени на разбор, и уж тем более не должен ошибаться в нём.
    if режим == "off":
        return 0

    verdict = classify(command, cwd)
    if not verdict:
        return 0

    blocking = режим == "block"
    if verdict == "bulk":
        message = BULK_MSG.format(n=len(inline_code(command).strip().splitlines()))
    elif verdict == "write":
        message = BLOCK_WRITE_MSG if blocking else WRITE_MSG
    else:
        message = BLOCK_READ_MSG if blocking else READ_MSG

    if blocking:
        # Exit 2 — вызов не состоится, stderr уходит модели как ошибка.
        sys.stderr.write(message + "\n")
        return 2

    sys.stdout.write(json.dumps({
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": message,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
