#!/usr/bin/env python3
"""SessionStart: назвать сессии её первое действие — и назвать конкретно.

Заменяет `serena-hooks activate`, который вкладывал три общие строки: «активируй
проект, прочитай инструкцию Serena, сделай это раньше остального». Ни про корень
экосистемы, ни про то, что инструменты Serena отложены и до `ToolSearch` её для
сессии не существует, там не говорилось.

Почему это стоит отдельного хука, а не строчки в стиле вывода. Текст
`SessionStart` приходит ПОСЛЕ системного промпта — то есть свежее стиля, ровно
как приходит блок «делай работу через Bash» в разрешительных режимах. Место
здесь дорогое, и занимать его общими словами жалко.

Правила работы этот хук НЕ повторяет: с 22.08.2026 они живут в системном промпте
(глобальный бриф, раздел «Serena and sequential-thinking»), а не в ответе на
активацию — тот стоил 2 100 токенов и оплачивался заново после каждого сжатия.
Хук называет первое действие, корень экосистемы и — если панель Serena отвечает —
какой проект сервер уже держит активным, чтобы сессия не активировала его впустую.
"""

import json
import os
import sys
import urllib.request

# Инструменты, которые стоит подтянуть первым же вызовом. Не весь список Serena:
# столько, чтобы хватило на разведку и правку, а остальное добирается по мере
# надобности.
TOOLS = (
    "mcp__serena__initial_instructions,"
    "mcp__serena__get_symbols_overview,mcp__serena__find_symbol,"
    "mcp__serena__find_referencing_symbols,mcp__serena__search_for_pattern,"
    "mcp__serena__find_file,mcp__serena__list_dir,"
    "mcp__serena__replace_symbol_body,mcp__serena__replace_content,"
    "mcp__serena__insert_after_symbol,mcp__serena__get_diagnostics_for_file"
)


def _ancestors(cwd: str):
    """Рабочий каталог и все каталоги над ним, снизу вверх."""
    try:
        path = os.path.realpath(cwd)
    except OSError:
        return
    while True:
        yield path
        parent = os.path.dirname(path)
        if parent == path:
            return
        path = parent


def _names_serena(names) -> bool:
    return any("serena" in str(name).lower() for name in (names or ()))


def serena_available(cwd: str) -> bool:
    """Есть ли у этой сессии Serena вообще.

    Смотрим туда же, куда смотрит сам CLI: пользовательские серверы в
    `~/.claude.json`, серверы конкретного проекта там же и `.mcp.json` в дереве
    над рабочим каталогом — с оглядкой на список выключенных.

    Зачем проверка. Указание, которое нельзя исполнить, — не помощь, а шум в
    самом дорогом месте контекста: сессия послушно зовёт `ToolSearch`, ничего
    не находит и остаётся с ощущением, что у неё что-то сломано. Нет Serena —
    хук молчит.
    """
    try:
        with open(os.path.expanduser("~/.claude.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        cfg = {}

    if _names_serena(cfg.get("mcpServers")):
        return True

    projects = cfg.get("projects") or {}
    for path in _ancestors(cwd):
        entry = projects.get(path) or {}
        if _names_serena(entry.get("mcpServers")):
            return True
        shared = os.path.join(path, ".mcp.json")
        if os.path.isfile(shared):
            try:
                with open(shared, encoding="utf-8") as fh:
                    mcp = json.load(fh)
            except (OSError, ValueError):
                mcp = {}
            if _names_serena(mcp.get("mcpServers")) and not _names_serena(
                entry.get("disabledMcpjsonServers")
            ):
                return True
    return False


# Панель Serena слушает первый свободный порт начиная с 24282 — при нескольких
# серверах номера идут подряд, поэтому опрашиваем небольшой диапазон.
DASHBOARD_PORTS = (24282, 24283, 24284)


def dashboard_project(timeout: float = 0.15) -> tuple[str, str] | None:
    """Какой проект сервер Serena держит активным — по данным его же панели.

    Зачем. Активация не бесплатна: ответ на `activate_project` — это около
    2 100 токенов, и сессия платит их заново после каждого сжатия, хотя сервер
    всё это время держит нужный проект активным (он один на всех). Спросить
    панель дешевле на два порядка, чем вызвать активацию впустую.

    Возвращает (имя, реальный путь) первого ответившего сервера либо None —
    панель выключена, сервера нет, ответ не разобрался. Хук в этом случае
    говорит то же, что говорил раньше: активируй корень.

    Порты можно подменить через `SERENA_DASHBOARD_PORTS` — это нужно тестам,
    чтобы не зависеть от того, поднята ли Serena на машине.
    """
    raw = os.environ.get("SERENA_DASHBOARD_PORTS", "")
    ports = tuple(int(p) for p in raw.replace(",", " ").split() if p.isdigit()) or DASHBOARD_PORTS
    for port in ports:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/get_config_overview", timeout=timeout
            ) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        active = (data or {}).get("active_project") or {}
        name, path = active.get("name"), active.get("path")
        if name and path:
            return str(name), os.path.realpath(os.path.expanduser(str(path)))
    return None


def ecosystem_root(cwd: str) -> str:
    """Корень экосистемы для рабочего каталога.

    Правило без зашитой таблицы: это САМЫЙ ВНЕШНИЙ каталог на пути от дома до
    `cwd`, в котором лежит `.serena/project.yml`. Так и определяется корень —
    под-проект внутри экосистемы своего `project.yml` иметь не должен, а если
    заведёт, внешний всё равно победит.

    Пустая строка означает «не определился»: тогда указания даются без имени.
    """
    try:
        cwd = os.path.realpath(cwd)
    except OSError:
        return ""
    home = os.path.realpath(os.path.expanduser("~"))
    if not (cwd == home or cwd.startswith(home + os.sep)):
        return ""

    found = ""
    path = cwd
    while True:
        # Сам дом кандидатом не считается, даже с меткой внутри.
        #
        # `~/.serena/project.yml` существует — дом зарегистрирован в Serena
        # проектом. Без этой оговорки «самый внешний» всегда оказывается домом,
        # и хук велит активировать `~`: Serena уходит обходить кэши, хранилище
        # пакетов и исходники ядра минутами и не даёт взамен ни одного
        # языкового сервера. Ровно эту ловушку уже закрыли в nudge-serena.py
        # (коммит «дом — место, где живут, а не проект»); здесь она осталась.
        if path != home and os.path.isfile(
            os.path.join(path, ".serena", "project.yml")
        ):
            found = path  # идём дальше вверх: нужен самый внешний
        if path == home or os.path.dirname(path) == path:
            break
        path = os.path.dirname(path)
    return found


def message(cwd: str) -> str:
    root = ecosystem_root(cwd)
    home = os.path.expanduser("~")

    def shorten(path: str) -> str:
        return "~" + path[len(home):] if path.startswith(home) else path

    # Кто привязал Серену и к чему. Источника два, и они НЕ равноценны.
    #
    # Переменная приезжает от обёртки `claude trah`, которая сама и поднимает
    # сервер с `--project`, — это знание из первых рук.
    #
    # Панель — знание из третьих. Наш сервер её не поднимает вовсе
    # (`--enable-web-dashboard false`), поэтому на опрос портов отвечает сервер
    # ЧУЖОЙ сессии. Обмер 29.08.2026: хук отрапортовал `SyncedProjects`, пока
    # наш сервер держал `tausozavr`, и на этом основании велел активировать
    # проект — инструментом, которого в сборке нет вовсе (`single_project:
    # true`). Сессия платила за это ходом. Поэтому панели верим ТОЛЬКО когда
    # она согласна с корнем: согласие безвредно, расхождение ничего не значит.
    bound = os.environ.get("TRAH_SERENA_PROJECT") or ""
    known: tuple[str, str] | None = None
    if bound and os.path.isdir(bound):
        known = ("the launcher", os.path.realpath(bound))
    else:
        active = dashboard_project()
        if active and root and os.path.realpath(root) == active[1]:
            known = ("Serena's dashboard", active[1])

    # Указания «активируй» здесь нет НИ В ОДНОЙ ветке, и это осознанно:
    # активировать нечем. Единственный способ сменить дерево — перезапуск
    # сессии из нужного каталога, так и написано.
    нет_инструмента = (
        "   There is no `activate_project` in the tool list: this build runs one "
        "project per server and cannot take a second one.\n"
    )
    if known and root and known[1] == os.path.realpath(root):
        second = (
            f"2. Nothing to activate: {known[0]} already bound Serena to "
            f"`{shorten(known[1])}`, and that is the root you need.\n"
            + нет_инструмента
        )
    elif known:
        second = (
            f"2. Serena is bound to `{shorten(known[1])}` by {known[0]}, while the root of "
            f"this ecosystem is `{shorten(root) if root else 'not detected'}`.\n"
            + нет_инструмента
            + "   If paths do not resolve, restart the session from the right directory.\n"
        )
    elif root:
        second = (
            f"2. The root of this ecosystem is `{shorten(root)}` — give paths relative to "
            "THAT, never to a sub-project inside it: the root indexes every sub-project "
            "at once.\n"
            + нет_инструмента
        )
    else:
        second = (
            "2. No ecosystem root above this directory — Serena is likely up without a "
            "project, and the symbolic tools will have nothing to answer for.\n"
            + нет_инструмента
            + "   Restart the session from the repository you mean.\n"
        )

    return (
        "**The first action in this session — before reading any file and before any search.**\n"
        "\n"
        "1. Pull in Serena's tools. They are deferred: until you request the schemas, "
        "Serena does not exist for you, and your hand reaches for `grep` by itself.\n"
        f'   `ToolSearch("select:{TOOLS}")`\n'
        "\n"
        f"{second}"
        "\n"
        "The working rules — the tool-choice ladder, the mandatory search scope, batching, "
        "the ban on excuses — are already in your system prompt, the section "
        '"Serena and sequential-thinking". Read them there; the activation answer no '
        "longer carries them."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    cwd = payload.get("cwd", "")
    # Serena к этой сессии не подключена — молчим совсем. Пустой ответ хука
    # ничего в контекст не кладёт, и сессия не получает указаний про
    # инструменты, которых у неё нет.
    if not serena_available(cwd):
        return 0
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message(cwd),
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
