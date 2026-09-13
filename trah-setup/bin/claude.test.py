#!/usr/bin/env python3
"""Тесты обёртки `claude`.

Главное, что здесь проверяется, — не экономия, а отказ в безопасную сторону:
обёртка не имеет права помешать claude запуститься. Поэтому большая часть
случаев — про то, когда флаг НЕ добавляется.

Настоящий claude не запускается ни разу: вместо него подставной бинарь, который
печатает полученные аргументы. Проверяем именно командную строку.
"""
import os
import shutil
import subprocess
import sys
import tempfile

WRAPPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude")

# Подставной claude: печатает аргументы по одному в строке.
FAKE = """#!/usr/bin/env bash
for a in "$@"; do printf '%s\\n' "$a"; done
exit ${FAKE_EXIT:-0}
"""

# Подставной claude версии, которая флага не знает: ровно так ведёт себя
# настоящий CLI при неизвестной опции — отказ стартовать, а не предупреждение.
FAKE_OLD = """#!/usr/bin/env bash
for a in "$@"; do
  if [ "$a" = "--append-system-prompt-file" ]; then
    printf "error: unknown option '--append-system-prompt-file'\\n" >&2
    exit 1
  fi
done
for a in "$@"; do printf '%s\\n' "$a"; done
"""


def write(path: str, text: str, mode: int = 0o644) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, mode)
    return path


class Sandbox:
    """Отдельные HOME и кэш: тест не должен зависеть от настоящего рабочего места."""

    def __init__(self, root: str):
        self.root = root
        self.home = os.path.join(root, "home")
        self.cache = os.path.join(root, "cache")
        self.fake = write(os.path.join(root, "fake", "claude"), FAKE, 0o755)
        self.fake_old = write(os.path.join(root, "fake", "claude-old"), FAKE_OLD, 0o755)
        os.makedirs(self.home, exist_ok=True)
        os.makedirs(self.cache, exist_ok=True)

    def run(self, args: list[str], cwd: str, target: str | None = "fake",
            env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update({"HOME": self.home, "XDG_CACHE_HOME": self.cache})
        env.pop("CLAUDE_WRAPPER_TARGET", None)
        if target == "fake":
            env["CLAUDE_WRAPPER_TARGET"] = self.fake
        elif target == "old":
            env["CLAUDE_WRAPPER_TARGET"] = self.fake_old
        env.update(env_extra or {})
        return subprocess.run([WRAPPER, *args], cwd=cwd, env=env,
                              capture_output=True, text=True)


def argv(proc: subprocess.CompletedProcess) -> list[str]:
    return proc.stdout.splitlines()


def main() -> int:
    failed = 0
    results: list[tuple[bool, str, str]] = []

    def check(ok: bool, title: str, detail: str = "") -> None:
        nonlocal failed
        failed += not ok
        results.append((ok, title, detail))

    with tempfile.TemporaryDirectory(prefix="claude-wrapper-test-") as root:
        box = Sandbox(root)

        # ── бриф находится и подаётся ────────────────────────────────────────
        proj = os.path.join(root, "proj")
        brief = write(os.path.join(proj, ".claude", "brief.md"), "правила проекта\n")
        deep = os.path.join(proj, "a", "b", "c")
        os.makedirs(deep, exist_ok=True)

        p = box.run(["-p", "привет"], cwd=deep)
        check(argv(p) == ["--append-system-prompt-file", brief, "-p", "привет"],
              "бриф найден из глубокого подкаталога", str(argv(p)))

        p = box.run(["-p", "привет"], cwd=proj)
        check(argv(p) == ["--append-system-prompt-file", brief, "-p", "привет"],
              "бриф найден в самом корне проекта", str(argv(p)))

        # ── режим гарда ставится ВСЕМ сессиям, не только `claude trah` ───────
        #
        # До 30.08.2026 `NUDGE_SERENA_MODE=block` жил в ветке режима, и обычная
        # сессия шла с мягким `warn`: чтение файла проекта через оболочку в ней
        # проходило. Тест закрывает именно это — вердикт спрашиваем у подставного
        # бинаря, потому что переменная уезжает в окружение, а не в argv.
        env_probe = write(os.path.join(root, "fake", "claude-env"),
                          "#!/usr/bin/env bash\n"
                          "printf 'NUDGE_SERENA_MODE=%s\\n' \"${NUDGE_SERENA_MODE:-НЕТ}\"\n",
                          0o755)
        plain = os.path.join(root, "plain")
        os.makedirs(plain, exist_ok=True)
        outside_probe = plain
        p = box.run(["-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": env_probe})
        check(argv(p) == ["NUDGE_SERENA_MODE=block"],
              "обычный запуск идёт с block", str(argv(p)))

        p = box.run(["trah", "-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": env_probe})
        check(argv(p) == ["NUDGE_SERENA_MODE=block"],
              "режим trah тоже с block", str(argv(p)))

        # ── режим trah включает разделы Delivering work и Corrections ────────
        #
        # Сервер 12.09.2026 перестал включать их свежим сессиям, и кусок
        # `sys-delivering-work-at-full-scope` молча умер: он встаёт в текст
        # раздела. Переменные ставятся только в режиме trah и не перебивают
        # значение, заданное снаружи.
        sections_probe = write(os.path.join(root, "fake", "claude-sections"),
                               "#!/usr/bin/env bash\n"
                               "printf 'BISON=%s LARCH=%s\\n' "
                               "\"${CLAUDE_CODE_BISON_CAIRN:-НЕТ}\" "
                               "\"${CLAUDE_CODE_LARCH_CISTERN:-НЕТ}\"\n",
                               0o755)
        p = box.run(["trah", "-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": sections_probe})
        check(argv(p) == ["BISON=1 LARCH=1"],
              "режим trah включает оба раздела", str(argv(p)))

        p = box.run(["-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": sections_probe})
        check(argv(p) == ["BISON=НЕТ LARCH=НЕТ"],
              "обычный запуск разделы не трогает", str(argv(p)))

        p = box.run(["trah", "-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": sections_probe,
                               "CLAUDE_CODE_BISON_CAIRN": "0"})
        check(argv(p) == ["BISON=0 LARCH=1"],
              "заданное снаружи значение сильнее умолчания", str(argv(p)))

        p = box.run(["-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": env_probe,
                               "NUDGE_SERENA_MODE": "warn"})
        check(argv(p) == ["NUDGE_SERENA_MODE=warn"],
              "заданное снаружи значение сильнее умолчания", str(argv(p)))

        # ── потолок батчинга ставится ВСЕМ сессиям ───────────────────────────
        #
        # До 30.08.2026 `export CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY=32` стоял в
        # ветке режима, а комментарий рядом обещал одинаковость двух контуров.
        # У обычной сессии оставались зашитые в CLI десять — втрое уже, и замер
        # ширины батча из одного контура ничего не говорил о другом.
        batch_probe = write(os.path.join(root, "fake", "claude-batch"),
                            "#!/usr/bin/env bash\n"
                            "printf 'BATCH=%s\\n' "
                            "\"${CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY:-НЕТ}\"\n",
                            0o755)
        p = box.run(["-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": batch_probe})
        check(argv(p) == ["BATCH=32"],
              "обычный запуск идёт с потолком 32", str(argv(p)))

        p = box.run(["trah", "-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": batch_probe})
        check(argv(p) == ["BATCH=32"],
              "режим trah тоже с потолком 32", str(argv(p)))

        p = box.run(["-p", "x"], cwd=outside_probe,
                    env_extra={"CLAUDE_WRAPPER_TARGET": batch_probe,
                               "CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY": "8"})
        check(argv(p) == ["BATCH=8"],
              "заданный снаружи потолок сильнее умолчания", str(argv(p)))

        # ── вне проекта ──────────────────────────────────────────────────────
        outside = os.path.join(root, "outside")
        os.makedirs(outside, exist_ok=True)
        p = box.run(["-p", "привет"], cwd=outside)
        check(argv(p) == ["-p", "привет"], "вне проекта флага нет", str(argv(p)))

        # ── отказ в безопасную сторону ───────────────────────────────────────
        bad = os.path.join(root, "bad")
        unreadable = write(os.path.join(bad, ".claude", "brief.md"), "правила\n", 0o000)
        p = box.run(["-p", "x"], cwd=bad)
        check(argv(p) == ["-p", "x"], "нечитаемый бриф — запуск без флага", str(argv(p)))
        os.chmod(unreadable, 0o644)

        empty = os.path.join(root, "empty")
        write(os.path.join(empty, ".claude", "brief.md"), "")
        p = box.run(["-p", "x"], cwd=empty)
        check(argv(p) == ["-p", "x"], "пустой бриф — запуск без флага", str(argv(p)))

        p = box.run(["-p", "x"], cwd=deep, target="old")
        check(argv(p) == ["-p", "x"],
              "версия не знает флага — запуск без флага", str(argv(p)))

        # ── чужое управление системным промптом ──────────────────────────────
        # Проверено пробой на 2.1.236: вместе с --append-system-prompt CLI
        # отказывается стартовать. Таусозавр передаёт его в режиме ультракода.
        for extra in (["--append-system-prompt", "текст"],
                      ["--append-system-prompt=текст"],
                      ["--append-system-prompt-file", "/tmp/x.md"],
                      ["--append-system-prompt-file=/tmp/x.md"],
                      ["--system-prompt", "текст"],
                      ["--system-prompt-file", "/tmp/x.md"],
                      ["--system-prompt-file=/tmp/x.md"]):
            p = box.run([*extra, "-p", "x"], cwd=deep)
            got = argv(p)
            check(got == [*extra, "-p", "x"],
                  f"насквозь: {' '.join(extra)[:40]}", str(got))

        # ── служебные вызовы ─────────────────────────────────────────────────
        for extra in (["--version"], ["--help"], ["-h"], ["-v"], ["--bare"],
                      ["update"], ["install", "stable"], ["mcp", "list"],
                      ["doctor"], ["plugin", "list"], ["setup-token"]):
            p = box.run(extra, cwd=deep)
            check(argv(p) == extra, f"насквозь: claude {' '.join(extra)}", str(argv(p)))

        # ── код возврата и потоки ────────────────────────────────────────────
        p = box.run(["-p", "x"], cwd=deep, env_extra={"FAKE_EXIT": "42"})
        check(p.returncode == 42, "код возврата настоящего бинаря доходит",
              f"код {p.returncode}")

        # ── глобальный бриф ──────────────────────────────────────────────────
        global_brief = write(os.path.join(box.home, ".claude", "brief.md"),
                             "ГЛОБАЛЬНОЕ правило\n")
        p = box.run(["-p", "x"], cwd=outside)
        check(argv(p) == ["--append-system-prompt-file", global_brief, "-p", "x"],
              "вне проекта берётся глобальный бриф", str(argv(p)))

        p = box.run(["-p", "x"], cwd=deep)
        got = argv(p)
        merged_ok = len(got) >= 2 and got[0] == "--append-system-prompt-file" \
            and got[1] not in (brief, global_brief) and os.path.isfile(got[1])
        text = open(got[1], encoding="utf-8").read() if merged_ok else ""
        check(merged_ok and "ГЛОБАЛЬНОЕ правило" in text and "правила проекта" in text,
              "глобальный + проектный склеены в ОДИН файл", str(got))
        check(text.index("ГЛОБАЛЬНОЕ") < text.index("правила проекта") if text else False,
              "в склейке глобальное идёт первым", "порядок нарушен")

        # склейка должна быть устойчивой: то же содержимое — тот же файл,
        # иначе кэш промпта пересоздавался бы каждый запуск
        p2 = box.run(["-p", "y"], cwd=deep)
        check(argv(p2)[:2] == got[:2], "склейка не меняет имени между запусками",
              str(argv(p2)[:2]))
        os.remove(global_brief)

        # ── поиск настоящего бинаря ──────────────────────────────────────────
        #
        # Главное здесь — что по умолчанию берётся САМАЯ СВЕЖАЯ версия. До
        # 21.08.2026 первой стояла памятка `wrapper-target`: она приколачивала
        # обёртку к версии, записанной однажды, и свежие скачивались, но не
        # запускались — `claude update` рапортовал успех вхолостую.
        def named(tag: str) -> str:
            """Подставной claude, который первой строкой называет себя."""
            return f"#!/usr/bin/env bash\nprintf '{tag}\\n'\n" \
                   'for a in "$@"; do printf \'%s\\n\' "$a"; done\n'

        versions = os.path.join(box.home, ".local", "share", "claude", "versions")
        write(os.path.join(versions, "2.1.9"), named("СТАРАЯ"), 0o755)
        write(os.path.join(versions, "2.1.10"), named("НОВАЯ"), 0o755)
        p = box.run(["-p", "x"], cwd=deep, target=None)
        check(argv(p)[:1] == ["НОВАЯ"],
              "без закрепки берётся новейшая версия (2.1.10, а не 2.1.9)", str(argv(p)))
        check(argv(p)[1:] == ["--append-system-prompt-file", brief, "-p", "x"],
              "и флаг при этом на месте", str(argv(p)))

        # Закрепка руками — намеренный откат на старую версию; она сильнее.
        pin = os.path.join(box.home, ".local", "share", "claude", "wrapper-pin")
        write(pin, os.path.join(versions, "2.1.9") + "\n")
        p = box.run(["-p", "x"], cwd=deep, target=None)
        check(argv(p)[:1] == ["СТАРАЯ"], "закрепка сильнее новейшей версии", str(argv(p)))

        # Закрепка в никуда — не отказ, а возврат к новейшей.
        write(pin, os.path.join(root, "no-such-binary") + "\n")
        p = box.run(["-p", "x"], cwd=deep, target=None)
        check(argv(p)[:1] == ["НОВАЯ"], "мёртвая закрепка — берётся новейшая", str(argv(p)))

        # Памятка старого образца лежит у всех, кто ставил обёртку до 21.08.
        # Читать её больше нельзя: там записана версия, устаревшая навсегда.
        write(os.path.join(box.home, ".local", "share", "claude", "wrapper-target"),
              os.path.join(versions, "2.1.9") + "\n")
        p = box.run(["-p", "x"], cwd=deep, target=None)
        check(argv(p)[:1] == ["НОВАЯ"], "памятка wrapper-target больше не читается",
              str(argv(p)))

        # ── обёртка не зовёт саму себя ───────────────────────────────────────
        selfdir = os.path.join(root, "selfbin")
        os.makedirs(selfdir, exist_ok=True)
        shutil.copyfile(WRAPPER, os.path.join(selfdir, "claude"))
        os.chmod(os.path.join(selfdir, "claude"), 0o755)
        write(pin, os.path.join(selfdir, "claude") + "\n")
        p = box.run(["-p", "x"], cwd=deep, target=None)
        check(argv(p)[:1] == ["НОВАЯ"],
              "закрепка на копию себя — не зацикливается, берётся версия",
              str(argv(p)))

        # ── режим `trah`: дом не подбирается проектным брифом ────────────────
        #
        # Ветка `trah` не проверялась здесь вовсе — и ровно в ней жил баг.
        # `find_project_brief` поднимался до `/` и подбирал `$HOME/.claude/brief.md`
        # как ПРОЕКТНЫЙ. В обычном режиме это гасило сравнение путей (глобальный
        # и «проектный» — один файл), а в режиме `trah` глобальный был ДРУГОЙ
        # (`brief-trah.md`), пути расходились, и в системный промпт уезжали ОБА
        # брифа. Обмер 28.08.2026 на живой машине: склейка 29 554 байта при
        # глобальном в 14 193, ~3800 лишних токенов каждым ходом.
        #
        # Двух брифов больше нет — он один на оба режима, — но подъём всё равно
        # обязан обрывать дом: иначе тот же файл склеился бы сам с собой, стоило
        # завести любой второй глобальный.
        # Глобальный бриф выше по тесту удалён (`os.remove(global_brief)`) —
        # кладём заново, иначе проверка идёт на пустом месте и «брифа нет»
        # читается как успех обрыва подъёма.
        trah_brief = write(global_brief, "ГЛОБАЛЬНОЕ правило\n")
        under_home = os.path.join(box.home, "work")
        os.makedirs(under_home, exist_ok=True)

        # Режим добавляет к запуску ещё `--mcp-config` и разрешающий флаг,
        # поэтому сверяем не весь список, а поданный бриф: он обязан быть
        # ФАЙЛОМ РЕЖИМА, а не склейкой.
        def поданный_бриф(proc) -> str | None:
            a = argv(proc)
            if "--append-system-prompt-file" not in a:
                return None
            return a[a.index("--append-system-prompt-file") + 1]

        p = box.run(["trah", "-p", "x"], cwd=under_home)
        check(поданный_бриф(p) == trah_brief,
              "режим trah из каталога под домом: только бриф режима", str(argv(p)))

        # Обратная сторона: настоящий проектный бриф под домом обязан работать.
        # Обрыв подъёма на доме не должен превратиться в «под домом проектов нет».
        proj_home = os.path.join(box.home, "proj2")
        brief_home = write(os.path.join(proj_home, ".claude", "brief.md"),
                           "правила proj2\n")
        deep_home = os.path.join(proj_home, "x", "y")
        os.makedirs(deep_home, exist_ok=True)

        p = box.run(["trah", "-p", "x"], cwd=deep_home)
        got = поданный_бриф(p)
        merged = got is not None and got not in (trah_brief, brief_home) \
            and os.path.isfile(got)
        text = open(got, encoding="utf-8").read() if merged else ""
        check(merged and "ГЛОБАЛЬНОЕ правило" in text and "правила proj2" in text,
              "режим trah: проектный бриф под домом склеивается с глобальным",
              str(got))

    for ok, title, detail in results:
        print(f"{'✓' if ok else '✗'} {title}" + ("" if ok else f"  ← {detail}"))
    print(f"\nвсего: {len(results)}   провалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
