#!/usr/bin/env python3
"""SessionStart: вернуть на место обёртку `claude`, если её снесло обновление.

`~/.local/bin/claude` — не бинарь, а точка входа, которую установщик Claude
Code пересоздаёт симлинком при каждом обновлении. Наша обёртка (она подаёт
правила экосистемы через --append-system-prompt-file и тем самым переносит их
в кэшируемую часть промпта) живёт ровно по этому пути, значит любое обновление
её молча стирает. Молча — потому что без обёртки claude работает как ни в чём
не бывало, просто дороже: заметить пропажу можно только по счёту.

Поэтому починка автоматическая. Хук ничего не блокирует: код возврата всегда 0,
любая неожиданность — молчаливый выход, а не помеха старту сессии.

Заодно хук — единственный установщик обёртки, и второй его долг — следить за
свалкой версий. Установщик Claude Code, увидев на месте точки входа не симлинк,
перестаёт убирать старые версии («the installer cannot tell which version your
launcher needs, so it keeps them all»). Каждая весит около 330 МБ и выходит
почти ежедневно, а заметно это только по свободному месту — то есть никогда.
Поэтому хук их считает и говорит вслух; сносит человек, руками.

Какую версию запускать, хук больше не решает: обёртка сама берёт новейшую.
Памятку `wrapper-target` он писал до 21.08.2026, и она оказалась ловушкой —
почему, написано в комментарии «Настоящий бинарь» в `trah-setup/bin/claude`.

Переменные окружения GWS_CLAUDE_WRAPPER_{LINK,KIT,VERSIONS,PIN} подменяют пути —
нужны тестам, в работе не задаются.
"""

import json
import os
import shutil
import stat
import sys

MARK = "GWS-CLAUDE-WRAPPER"

WINDOWS = os.name == "nt"

# Под Windows точка входа другая. `~/.local/bin/claude.exe` — копия бинаря,
# её ведёт установщик Claude Code, и подменять её нечем: bash-скрипт на месте
# `.exe` не запустится. Обёртка живёт в своём каталоге парой: шим `claude.cmd`
# (его и находит cmd/PowerShell) и `claude-wrapper.sh` рядом, которому шим
# передаёт управление через bash Git. Каталог обязан стоять в PATH РАНЬШЕ
# `~/.local/bin`: иначе `.EXE` выигрывает по PATHEXT, и обёртка молча не
# зовётся. Обновление Claude Code этот каталог не трогает — хук здесь нужен,
# чтобы доносить новую редакцию обёртки из комплекта.
LINK = os.environ.get("GWS_CLAUDE_WRAPPER_LINK") \
    or os.path.expanduser("~/.local/claude-wrapper/claude-wrapper.sh" if WINDOWS
                          else "~/.local/bin/claude")


def _kit_from_note() -> str:
    """Путь к комплекту из памятки, которую пишет установщик.

    Хук живёт в `~/.claude/hooks`, то есть вдали от репозитория, а восстановить
    обёртку может только из него. Догадка про `~/Ledevia/<что-то>` работала
    ровно на одной машине и врала на всякой другой; памятка `trah-kit-path`
    говорит правду на любой, потому что её пишет тот, кто ставил.
    """
    try:
        with open(os.path.expanduser("~/.claude/trah-kit-path"),
                  encoding="utf-8") as f:
            root = f.read().strip()
    except OSError:
        return ""
    candidate = os.path.join(root, "bin", "claude") if root else ""
    return candidate if candidate and os.path.isfile(candidate) else ""


def _kit_beside() -> str:
    """Комплект рядом с хуком: так бывает, когда хук зовут прямо из репозитория."""
    candidate = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "claude")
    return candidate if os.path.isfile(candidate) else ""


# Порядок: явное указание переменной (тесты и ручной обход) → памятка от
# установщика → комплект рядом с хуком. Догадки про чужой дом здесь больше нет.
KIT = os.environ.get("GWS_CLAUDE_WRAPPER_KIT") \
    or _kit_from_note() or _kit_beside()
VERSIONS_DIR = os.environ.get("GWS_CLAUDE_WRAPPER_VERSIONS") \
    or os.path.expanduser("~/.local/share/claude/versions")
PIN_FILE = os.environ.get("GWS_CLAUDE_WRAPPER_PIN") \
    or os.path.expanduser("~/.local/share/claude/wrapper-pin")

# Сколько версий держать: текущую, предыдущую на случай отката и одну про запас.
KEEP_VERSIONS = 3


def is_wrapper(path: str) -> bool:
    """Обычный файл с маркером. Симлинк — уже не обёртка, а восстановленная точка."""
    try:
        if os.path.islink(path) or not os.path.isfile(path):
            return False
        with open(path, encoding="utf-8", errors="replace") as f:
            return MARK in f.read(4096)
    except OSError:
        return False


def matches_kit(path: str) -> bool:
    """Совпадает ли обёртка с образцом из комплекта, байт в байт.

    Маркера мало. Хук ставился только когда обёртки НЕТ вовсе, и УСТАРЕВШУЮ он
    пропускал: маркер на месте, значит «всё хорошо». Измерено 07.09.2026 —
    установка отрапортовала «✓ обёртка», а на точке входа осталась редакция без
    `export TRAH_MODE`, из-за чего сессия режима подхватывала чужие модули
    диспетчера. Ровно та поломка, против которой комплект и написан: молчит.

    Сравнение целиком, а не по одной строке: любая правка обёртки — от новой
    переменной до починки разбора аргументов — обязана доезжать сама, иначе
    следующая такая же дыра будет обнаружена тем же способом, через неделю.
    """
    try:
        with open(path, "rb") as текущая, open(KIT, "rb") as образец:
            return текущая.read() == образец.read()
    except OSError:
        return False


def version_key(name: str):
    """Ключ сортировки версий по номеру. Нечисловое имя уезжает в конец."""
    try:
        return (0, tuple(int(p) for p in name.split(".")))
    except ValueError:
        return (1, name)


def versions_note() -> str | None:
    """Доклад о свалке версий. None, пока их немного."""
    try:
        names = [n for n in os.listdir(VERSIONS_DIR)
                 if os.path.isfile(os.path.join(VERSIONS_DIR, n))]
    except OSError:
        return None
    if len(names) <= KEEP_VERSIONS:
        return None

    size = 0
    for name in names:
        try:
            size += os.path.getsize(os.path.join(VERSIONS_DIR, name))
        except OSError:
            pass

    # Закреплённую руками версию из списка на снос вычитаем: её оставили
    # намеренно, и предложить снести её значило бы отменить чужое решение.
    pinned = ""
    try:
        with open(PIN_FILE, encoding="utf-8") as f:
            pinned = os.path.basename(f.readline().strip())
    except OSError:
        pass

    stale = [n for n in sorted(names, key=version_key)[:-KEEP_VERSIONS] if n != pinned]
    if not stale:
        return None
    paths = " ".join(os.path.join(VERSIONS_DIR, n) for n in stale)
    return (f"{len(names)} claude versions have piled up ({size / 2 ** 30:.1f} GB). "
            f"The installer stopped removing the old ones — the entry point is not its "
            f"symlink but a wrapper, and it does not know which version that wrapper "
            f"needs. The newest one always runs, so the spare ones can be removed:"
            f"\n    rm {paths}")


def install() -> str | None:
    """Поставить обёртку из комплекта. Возвращает строку для доклада или None."""
    if not is_wrapper(KIT):
        return f"the claude wrapper is gone and the kit is unavailable or substituted: {KIT}"

    была_наша = is_wrapper(LINK)

    # Ничего не затирать молча — правило комплекта, и здесь оно про ЧУЖОЙ файл на
    # точке входа: `os.replace` ниже уничтожает его без следа.
    #
    # Своя же устаревшая обёртка в копии не нуждается: она лежит в комплекте, в
    # git, и точно такая же копия рядом была бы мусором при каждом обновлении.
    #
    # Симлинк тоже не в счёт. По этому пути его кладёт штатный установщик Claude
    # Code и пересоздаёт при КАЖДОМ обновлении, а восстанавливается он одной
    # строкой `ln -s`.
    #
    # Копия делается один раз: второй заход перезаписал бы настоящий оригинал
    # нашей же обёрткой, и спасать было бы уже нечего.
    saved = None
    if os.path.isfile(LINK) and not os.path.islink(LINK) and not была_наша:
        candidate = f"{LINK}.before-trah"
        try:
            if not os.path.exists(candidate):
                shutil.copy2(LINK, candidate)
                saved = candidate
        except OSError:
            saved = None

    try:
        os.makedirs(os.path.dirname(LINK), exist_ok=True)
        tmp = f"{LINK}.part.{os.getpid()}"
        shutil.copyfile(KIT, tmp)
        os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, LINK)          # замена атомарна: полусостояния не бывает
    except OSError as e:
        return f"the claude wrapper could not be restored: {e}"

    if была_наша:
        return (f"The claude wrapper at {LINK} was stale and has been updated from "
                f"the kit. Sessions already running still use the old one — restart "
                f"them to pick up the change.")
    return (f"The claude wrapper was restored at {LINK} from the kit."
            + (f" The file that was there is kept as {saved}." if saved else ""))


def windows_shim() -> str | None:
    """Шим `claude.cmd` рядом с обёрткой — и проверка, что PATH зовёт именно его.

    Шим кладётся из комплекта, если его нет или он отличается. Порядок в PATH
    хук не правит (это настройка пользователя, и чинить её тайком нельзя), но
    называет вслух: без этого обёртка есть, а зовётся мимо неё голый `.exe`.
    """
    образец = os.path.join(os.path.dirname(KIT), "claude.cmd") if KIT else ""
    шим = os.path.join(os.path.dirname(LINK), "claude.cmd")
    заметки = []
    if образец and os.path.isfile(образец):
        try:
            with open(образец, "rb") as а:
                нужно = а.read()
            есть = b""
            if os.path.isfile(шим):
                with open(шим, "rb") as б:
                    есть = б.read()
            if есть != нужно:
                os.makedirs(os.path.dirname(шим), exist_ok=True)
                tmp = f"{шим}.part.{os.getpid()}"
                with open(tmp, "wb") as в:
                    в.write(нужно)
                os.replace(tmp, шим)
                заметки.append(f"The claude.cmd shim at {шим} was updated from the kit.")
        except OSError as e:
            заметки.append(f"the claude.cmd shim could not be updated: {e}")
    найдено = shutil.which("claude")
    if найдено and os.path.normcase(os.path.abspath(найдено)) != os.path.normcase(шим) \
            and not os.environ.get("GWS_CLAUDE_WRAPPER_LINK"):
        заметки.append(
            f"`claude` resolves to {найдено}, not to the wrapper shim {шим}: the wrapper "
            f"is bypassed and sessions start without the brief. Put "
            f"{os.path.dirname(шим)} BEFORE {os.path.dirname(найдено)} in the user PATH.")
    return "\n\n".join(заметки) or None


def main() -> int:
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()               # полезной нагрузки нет, но ввод дочитываем
    except (OSError, ValueError):
        pass

    notes: list[str | None] = []
    try:
        # Два условия, а не одно. `is_wrapper` отвечает «наша ли она», а
        # `matches_kit` — «та ли она». До 07.09.2026 стояло только первое, и
        # устаревшая обёртка жила на точке входа сколько угодно: хук видел
        # маркер и молчал, а установка рапортовала успех.
        if not is_wrapper(LINK) or not matches_kit(LINK):
            notes.append(install())
        if WINDOWS:
            notes.append(windows_shim())
        notes.append(versions_note())
    except Exception:                      # хук не имеет права мешать старту
        return 0

    message = "\n\n".join(note for note in notes if note)
    if not message:
        return 0
    sys.stdout.write(json.dumps({
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
