#!/usr/bin/env python3
"""Тесты хука восстановления обёртки `claude`.

Разыгрывается ровно тот случай, ради которого хук заведён: обновление Claude
Code пересоздало `~/.local/bin/claude` симлинком, обёртки не стало. Хук должен
вернуть её на место.

Второй случай — свалка версий: установщик перестал убирать старые, потому что
точка входа больше не его симлинк. Хук обязан сказать об этом числом.

Настоящие пути не трогаются: и точка входа, и каталог версий подменяются
переменными окружения, HOME — временный.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "restore-claude-wrapper.py")
# комплект лежит рядом с хуком (trah-setup/) либо, после установки хука
# в ~/.claude/hooks, по обычному пути экосистемы
KIT = os.path.join(os.path.dirname(HERE), "bin", "claude")
if not os.path.isfile(KIT):
    KIT = os.path.expanduser("~/Ledevia/claude-trah/trah-setup/bin/claude")

FAKE = "#!/usr/bin/env bash\nfor a in \"$@\"; do printf '%s\\n' \"$a\"; done\n"


def write(path: str, text: str, mode: int = 0o644) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, mode)
    return path


def run_hook(home: str, link: str, versions: str, kit: str = KIT, pin: str = ""
             ) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update({
        "HOME": home,
        "GWS_CLAUDE_WRAPPER_LINK": link,
        "GWS_CLAUDE_WRAPPER_VERSIONS": versions,
        "GWS_CLAUDE_WRAPPER_KIT": kit,
        "GWS_CLAUDE_WRAPPER_PIN": pin or os.path.normpath(
            os.path.join(versions, os.pardir, "wrapper-pin")),
    })
    return subprocess.run([sys.executable, HOOK],
                          input=json.dumps({"hook_event_name": "SessionStart"}),
                          capture_output=True, text=True, env=env)


def is_wrapper(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "GWS-CLAUDE-WRAPPER" in f.read(4096)
    except OSError:
        return False


def main() -> int:
    failed = 0
    results: list[tuple[bool, str, str]] = []

    def check(ok: bool, title: str, detail: str = "") -> None:
        nonlocal failed
        failed += not ok
        results.append((ok, title, detail))

    with tempfile.TemporaryDirectory(prefix="restore-wrapper-test-") as root:
        home = os.path.join(root, "home")
        link = os.path.join(home, ".local", "bin", "claude")
        versions = os.path.join(home, ".local", "share", "claude", "versions")
        real = write(os.path.join(versions, "2.1.236"), FAKE, 0o755)

        # ── обновление пересоздало симлинк: обёртки нет ──────────────────────
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(real, link)
        proc = run_hook(home, link, versions)
        check(proc.returncode == 0, "хук ничего не блокирует", f"код {proc.returncode}")
        check(is_wrapper(link) and not os.path.islink(link),
              "снесённая обёртка восстановлена")
        check(os.access(link, os.X_OK), "восстановленная обёртка исполняема")
        check("hookSpecificOutput" in proc.stdout and "restore" not in proc.stderr,
              "о починке доложено одной строкой", proc.stdout[:120])

        # ── восстановленная обёртка действительно доходит до бинаря ──────────
        env = dict(os.environ)
        env.update({"HOME": home, "XDG_CACHE_HOME": os.path.join(root, "cache")})
        env.pop("CLAUDE_WRAPPER_TARGET", None)
        out = subprocess.run([link, "--version"], capture_output=True, text=True,
                             env=env, cwd=root)
        check(out.stdout.splitlines() == ["--version"],
              "через восстановленную обёртку запускается новейшая версия",
              repr(out.stdout))

        # ── обёртка на месте: молчим и ничего не трогаем ─────────────────────
        before = os.stat(link).st_mtime_ns
        proc = run_hook(home, link, versions)
        check(proc.stdout.strip() == "" and proc.returncode == 0,
              "обёртка на месте — хук молчит", proc.stdout[:120])
        check(os.stat(link).st_mtime_ns == before, "и файл не переписывается")

        # ── обёртка НАША, но устаревшая ──────────────────────────────────────
        #
        # Маркер на месте, содержимое от прежней редакции. До 07.09.2026 хук
        # такую пропускал — смотрел только на маркер. Измерено в тот же день:
        # установка отрапортовала «✓ обёртка», а на точке входа осталась
        # редакция без `export TRAH_MODE`, и сессия режима подхватывала чужие
        # модули диспетчера.
        образец = open(KIT, encoding="utf-8").read()
        write(link, образец + "\n# прежняя редакция\n", 0o755)
        proc = run_hook(home, link, versions)
        check(open(link, encoding="utf-8").read() == образец,
              "устаревшая обёртка обновляется из комплекта")
        check("stale" in proc.stdout, "об устаревшей сказано отдельно", proc.stdout[:160])
        check(not os.path.exists(link + ".before-trah"),
              "своя старая обёртка копией не сопровождается")

        # ── точки входа нет вовсе ───────────────────────────────────────────
        os.remove(link)
        proc = run_hook(home, link, versions)
        check(is_wrapper(link), "обёртка ставится и когда точки входа нет вовсе")
        check(proc.returncode == 0, "код возврата 0 и в этом случае")

        # ── комплект недоступен: не молчим, но и не ломаем ───────────────────
        os.remove(link)
        proc = run_hook(home, link, versions, kit=os.path.join(root, "no-such-kit"))
        check(proc.returncode == 0, "недоступный комплект не роняет старт сессии",
              f"код {proc.returncode}")
        check("kit is unavailable" in proc.stdout, "о недоступном комплекте сказано",
              proc.stdout[:120])
        check(not os.path.exists(link), "и ничего не подсовывается вместо обёртки")

        # ── чужой файл на месте точки входа (не симлинк, не наша обёртка) ────
        #
        # Замена — правильное поведение, а вот молчаливое уничтожение — нет:
        # `os.replace` не оставляет от чужого файла ничего. Копия делается один
        # раз, иначе второй заход перезапишет оригинал нашей же обёрткой.
        чужой = "#!/bin/sh\necho чужой\n"
        write(link, чужой, 0o755)
        proc = run_hook(home, link, versions)
        check(is_wrapper(link), "чужой файл на точке входа заменяется обёрткой")
        спасён = link + ".before-trah"
        check(os.path.isfile(спасён), "и сохраняется рядом, а не уничтожается")
        check(open(спасён, encoding="utf-8").read() == чужой,
              "сохранено именно его содержимое")
        check(".before-trah" in proc.stdout, "о спасённом файле сказано",
              proc.stdout[:200])

        os.remove(link)
        run_hook(home, link, versions)
        check(open(спасён, encoding="utf-8").read() == чужой,
              "повторный заход не затирает спасённое своей обёрткой")
        os.remove(спасён)

        # Симлинк штатного установщика в сторону не копируется: он приезжает
        # заново при каждом обновлении Claude Code, и копии были бы мусором.
        os.remove(link)
        os.symlink(real, link)
        run_hook(home, link, versions)
        check(not os.path.exists(спасён), "штатный симлинк копией не сопровождается")

        # ── свалка версий: установщик их больше не убирает ───────────────────
        for name in ("2.1.233", "2.1.234", "2.1.235", "2.1.237", "2.1.238"):
            write(os.path.join(versions, name), FAKE, 0o755)
        proc = run_hook(home, link, versions)
        check("6 claude versions have piled up" in proc.stdout, "о свалке версий сказано числом",
              proc.stdout[:200])
        to_remove = proc.stdout.split("rm ")[-1]
        check("2.1.233" in to_remove and "2.1.238" not in to_remove,
              "к сносу предложены старые, новейшие оставлены", to_remove[:200])

        # Закреплённую руками версию сносить не предлагаем: её оставили намеренно.
        pin = write(os.path.join(home, ".local", "share", "claude", "wrapper-pin"),
                    os.path.join(versions, "2.1.233") + "\n")
        proc = run_hook(home, link, versions, pin=pin)
        to_remove = proc.stdout.split("rm ")[-1]
        check("2.1.233" not in to_remove, "закреплённая версия из сноса вычтена",
              to_remove[:200])

        # Оригинал пропатченной копии trah — тоже: без него копию не пересобрать.
        trah = os.path.join(home, ".local", "share", "claude", "trah")
        os.makedirs(trah, exist_ok=True)
        os.symlink("2.1.234", os.path.join(trah, "current"))
        proc = run_hook(home, link, versions, pin=pin)
        to_remove = proc.stdout.split("rm ")[-1]
        check("2.1.234" not in to_remove and "2.1.235" in to_remove,
              "оригинал копии trah из сноса вычтен, остальное старьё — нет", to_remove[:200])
        os.remove(os.path.join(trah, "current"))

        # ── версий немного — молчание ───────────────────────────────────────
        for name in ("2.1.233", "2.1.234", "2.1.235"):
            os.remove(os.path.join(versions, name))
        proc = run_hook(home, link, versions, pin=pin)
        check(proc.stdout.strip() == "", "три версии — хук молчит", proc.stdout[:200])

    for ok, title, detail in results:
        print(f"{'✓' if ok else '✗'} {title}" + ("" if ok else f"  ← {detail}"))
    print(f"\nвсего: {len(results)}   провалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
