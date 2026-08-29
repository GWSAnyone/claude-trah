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

LINK = os.environ.get("GWS_CLAUDE_WRAPPER_LINK") \
    or os.path.expanduser("~/.local/bin/claude")
# Запасной путь к комплекту — предположение про ЭТУ машину, и на чужой оно
# неверно. Поэтому первым делом спрашивается переменная: у того, кто склонировал
# репозиторий в другое место, работает она, а не догадка.
KIT = os.environ.get("GWS_CLAUDE_WRAPPER_KIT") \
    or os.path.expanduser("~/Ledevia/tausozavr/trah-setup/bin/claude")
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

    try:
        os.makedirs(os.path.dirname(LINK), exist_ok=True)
        tmp = f"{LINK}.part.{os.getpid()}"
        shutil.copyfile(KIT, tmp)
        os.chmod(tmp, os.stat(tmp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(tmp, LINK)          # замена атомарна: полусостояния не бывает
    except OSError as e:
        return f"the claude wrapper could not be restored: {e}"

    return f"The claude wrapper was restored at {LINK} from the kit."


def main() -> int:
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()               # полезной нагрузки нет, но ввод дочитываем
    except (OSError, ValueError):
        pass

    notes: list[str | None] = []
    try:
        if not is_wrapper(LINK):
            notes.append(install())
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
