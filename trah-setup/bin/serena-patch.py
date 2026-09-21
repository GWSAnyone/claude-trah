#!/usr/bin/env python3
"""Serena с нашими патчами: поставить, проверить, переехать на новый коммит апстрима.

    serena-patch.py status              что стоит, какой прицел, какие патчи наложены
    serena-patch.py apply [--check]     наложить недостающие патчи на установленную Serena
    serena-patch.py install [--check]   поставить прицел, если Serena нет вовсе, и наложить
    serena-patch.py upgrade [КОММИТ]    переезд на коммит апстрима (по умолчанию main)

ЗАЧЕМ. Serena ставится `uv tool` прямо из git апстрима, а наши правки жили
правкой файлов в `site-packages`: ни в одном репозитории, только копии
`*.orig-before-*` рядом. Любая переустановка стирала их молча, и узнать об этом
можно было только по вернувшемуся бегу (зависший регэксп, склеенный markdown).
Теперь патчи — часть комплекта, `trah-setup/serena/patches/*.patch`, а прицел —
коммит апстрима в `trah-setup/serena/upstream.txt`, по образцу `version.txt`.

ПЕРЕЕЗД НЕ ОСТАВЛЯЕТ ПОЛОВИНЫ. Прицел переписывает только `upgrade`, и только
после того как:
  1. все патчи легли на ИСХОДНИКИ цели всухую — до установки, из архива git;
  2. установка прошла;
  3. все патчи легли на установленное;
  4. живая проверка прошла (импорт и таймаут регэкспа на настоящем модуле).
Сорвался шаг 3 или 4 — ставится обратно прежний прицел с его патчами. Сорвался
шаг 1 — ничего не ставится вовсе, а промахи названы все разом.

ПОЧЕМУ `--fuzz=0`. Патч с fuzz «ложится» и на изменившийся контекст, то есть
может лечь не туда и промолчать. Сдвиг по строкам допустим, размытие контекста —
нет: не легло — значит апстрим поменял место, и смотреть надо глазами.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

КОМПЛЕКТ = Path(__file__).resolve().parent.parent
ПАТЧИ = КОМПЛЕКТ / "serena" / "patches"
ПРИЦЕЛ = КОМПЛЕКТ / "serena" / "upstream.txt"
АПСТРИМ = "https://github.com/oraios/serena"
ПАКЕТ = "serena-agent"
КЭШ = Path.home() / ".cache" / "trah-serena" / "src"


def патчи() -> list[Path]:
    return sorted(ПАТЧИ.glob("*.patch"))


def прицел() -> str:
    return ПРИЦЕЛ.read_text(encoding="utf-8").strip() if ПРИЦЕЛ.exists() else ""


def каталог_инструмента() -> Path:
    г = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True)
    return Path(г.stdout.strip()) / ПАКЕТ


def установка() -> tuple[Path | None, str | None]:
    """Каталог `site-packages` установленной Serena и коммит, из которого она поставлена."""
    for site in sorted(каталог_инструмента().glob("lib/python*/site-packages")):
        for инфо in site.glob("serena_agent-*.dist-info"):
            адрес = инфо / "direct_url.json"
            коммит = None
            if адрес.exists():
                коммит = json.loads(адрес.read_text()).get("vcs_info", {}).get("commit_id")
            return site, коммит
    return None, None


def _patch(каталог: Path, патч: Path, *флаги: str) -> bool:
    with патч.open("rb") as вход:
        г = subprocess.run(["patch", "-p1", "-d", str(каталог), "-f", "-s", "--fuzz=0",
                            "--no-backup-if-mismatch", "-r", "-", *флаги],
                           stdin=вход, capture_output=True)
    return г.returncode == 0


def состояние(каталог: Path, патч: Path) -> str:
    """«наложен», «ложится» или «не ложится» — всухую, ничего не меняя.

    Наложенность опознаётся обратным прогоном: если патч снимается начисто, он
    стоит. Прямой прогон на наложенном файле не годится — он бы ответил
    «не ложится», и наложенный патч выглядел бы сломанным.
    """
    if _patch(каталог, патч, "--dry-run", "-R"):
        return "наложен"
    if _patch(каталог, патч, "--dry-run"):
        return "ложится"
    return "не ложится"


def наложить(каталог: Path, патчи_: list[Path], всухую: bool) -> list[str]:
    """Доводит наложение до конца. Возвращает имена патчей, которые не легли."""
    плохо = []
    for п in патчи_:
        с = состояние(каталог, п)
        if с == "ложится" and not всухую:
            с = "наложен сейчас" if _patch(каталог, п) else "не ложится"
        print(f"  {'✗' if с == 'не ложится' else '✓'}  {п.name}: {с}")
        if с == "не ложится":
            плохо.append(п.name)
    return плохо


ЖИВАЯ_ПРОВЕРКА = """
import time
import serena.code_editor, serena.hooks, serena.util.yaml
from serena.util.regex_timeout import RegexTimeoutError, compile_pattern
from serena.util.text_utils import search_text
начало = time.monotonic()
try:
    # `(a+)+$` сюда не годится: модуль regex его оптимизирует и не зависает (замер 16.09.2026).
    compile_pattern(r"(\\w|\\w\\w)*$", timeout_seconds=0.5).search("a" * 60 + "!")
    raise SystemExit("регэксп с экспоненциальным перебором не прервался")
except RegexTimeoutError:
    pass
if time.monotonic() - начало > 5:
    raise SystemExit("таймаут сработал, но слишком поздно")
if len(search_text("def", content="def a():\\n    pass\\ndef b():\\n    pass\\n")) != 2:
    raise SystemExit("обычный поиск сломан")
print("живая проверка: импорт, таймаут регэкспа и обычный поиск в порядке")
"""


def живая_проверка() -> bool:
    питон = каталог_инструмента() / "bin" / "python"
    г = subprocess.run([str(питон), "-c", ЖИВАЯ_ПРОВЕРКА], capture_output=True, text=True)
    print("  " + (г.stdout.strip() or г.stderr.strip()[-600:]))
    return г.returncode == 0


def клон() -> None:
    """Кэш-клон апстрима без блобов: коммиты и деревья есть, файлы тянутся по требованию."""
    if not КЭШ.exists():
        КЭШ.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        АПСТРИМ, str(КЭШ)], check=True)
    subprocess.run(["git", "-C", str(КЭШ), "fetch", "-q", "origin"], check=True)


def исходники(коммит: str) -> Path:
    """Чистые исходники коммита во временном каталоге — через `git archive`, без checkout."""
    клон()
    куда = Path(tempfile.mkdtemp(prefix="trah-serena-"))
    архив = subprocess.run(["git", "-C", str(КЭШ), "archive", коммит, "src/serena"],
                           capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(куда)], input=архив, check=True)
    return куда / "src"


def коммит_апстрима(ссылка: str) -> str:
    клон()
    имя = f"origin/{ссылка}" if ссылка == "main" else ссылка
    return subprocess.run(["git", "-C", str(КЭШ), "rev-parse", имя],
                          capture_output=True, text=True, check=True).stdout.strip()


def поставить(коммит: str) -> bool:
    """`uv tool install --force` ровно этого коммита, на той же версии Python, что стояла."""
    команда = ["uv", "tool", "install", "--force", f"{ПАКЕТ} @ git+{АПСТРИМ}@{коммит}"]
    site, _ = установка()
    if site is not None:
        команда[3:3] = ["--python", site.parent.name.removeprefix("python")]
    print("  " + " ".join(команда))
    return subprocess.run(команда).returncode == 0


def status(_: list[str]) -> int:
    site, коммит = установка()
    свой = прицел()
    print(f"прицел (upstream.txt):  {свой[:12] or '—'}")
    print(f"установлена:            {(коммит or '?')[:12] if site else 'НЕТ'}"
          + ("" if not site or коммит == свой else "   ← расходится с прицелом"))
    if site:
        наложить(site, патчи(), всухую=True)
    return 0


def apply(аргументы: list[str]) -> int:
    всухую = "--check" in аргументы
    site, коммит = установка()
    if site is None:
        print("Serena не установлена — сначала `install`")
        return 1
    if коммит != прицел():
        # Патчи сняты с прицела; на другом коммите «легло» не доказывает «верно».
        print(f"стоит {коммит}, прицел {прицел()} — наложение только через `upgrade {коммит}`"
              " или `install` прицела")
        return 1
    плохо = наложить(site, патчи(), всухую)
    if плохо:
        return 1
    return 0 if всухую else (0 if живая_проверка() else 1)


def install(аргументы: list[str]) -> int:
    всухую = "--check" in аргументы
    site, коммит = установка()
    if site is not None:
        # Чужую установку другого коммита не трогаем: переезд — решение, а не побочный эффект.
        return apply(аргументы)
    if всухую:
        print(f"Serena нет — поставил бы {прицел()[:12]} и наложил {len(патчи())} патча")
        return 0
    if not поставить(прицел()):
        return 1
    return apply([])


def upgrade(аргументы: list[str]) -> int:
    ссылка = next((а for а in аргументы if not а.startswith("-")), "main")
    цель = коммит_апстрима(ссылка)
    # Откатываться на то, что СТОЯЛО, а не на прицел: прицел мог уже разойтись с установкой.
    _, прежний = установка()
    прежний = прежний or прицел()
    print(f"переезд Serena {прежний[:12] or '—'} → {цель[:12]}")

    print("[1/4] патчи на исходники цели, всухую")
    чистые = исходники(цель)
    try:
        плохо = наложить(чистые, патчи(), всухую=True)
    finally:
        shutil.rmtree(чистые.parent, ignore_errors=True)
    if плохо:
        print(f"не легли: {', '.join(плохо)} — ничего не ставлю, прицел прежний")
        return 1

    print("[2/4] установка")
    if not поставить(цель):
        print("установка сорвалась — прицел прежний")
        return 1

    print("[3/4] патчи на установленное")
    site, _ = установка()
    сорвано = site is None or наложить(site, патчи(), всухую=False)
    print("[4/4] живая проверка")
    if сорвано or not живая_проверка():
        if прежний:
            print(f"откат на {прежний[:12]}")
            if поставить(прежний):
                site, _ = установка()
                if site is not None:
                    наложить(site, патчи(), всухую=False)
        return 1

    ПРИЦЕЛ.write_text(цель + "\n", encoding="utf-8")
    print(f"upstream.txt: {прежний[:12] or '—'} → {цель[:12]}")
    print("Серверы Serena, поднятые раньше, работают на прежнем коде — перезапусти сессии.")
    return 0


def stamp(_: list[str]) -> int:
    """Одна строка «установленный-коммит прицел» — для `./trah`, без разбора человеческого вывода."""
    site, коммит = установка()
    print(f"{(коммит or '?') if site else 'нет'} {прицел() or '?'}")
    return 0


def main() -> int:
    команда = sys.argv[1] if len(sys.argv) > 1 else "status"
    действия = {"status": status, "apply": apply, "install": install, "upgrade": upgrade,
                "stamp": stamp}
    if команда not in действия:
        print(__doc__)
        return 2
    return действия[команда](sys.argv[2:])


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.exit(main())
