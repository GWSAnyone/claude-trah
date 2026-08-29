#!/usr/bin/env python3
"""Проверка nudge-serena: что он ловит, что пропускает и чем режимы отличаются.

Главное здесь — не то, что хук ругается, а то, на что он НЕ ругается. В режиме
`block` ложное срабатывание не советует, а отменяет вызов, и цена ошибки другая:
запрет на python-калькулятор оставил бы сессию без арифметики по журналам.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nudge-serena.py")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run(command: str, mode: str = "warn", cwd: str = ROOT, roots: str | None = None):
    payload = json.dumps({"tool_name": "Bash", "cwd": cwd,
                          "tool_input": {"command": command}})
    env = dict(os.environ, NUDGE_SERENA_MODE=mode)
    # `roots=None` — умолчание хука (`~/Ledevia`), а не то, что случайно стоит
    # в окружении машины: иначе тест мерит настройку хоста, а не хук.
    if roots is None:
        env.pop("NUDGE_SERENA_ROOTS", None)
    else:
        env["NUDGE_SERENA_ROOTS"] = roots
    res = subprocess.run([sys.executable, HOOK], input=payload,
                         capture_output=True, text=True, env=env)
    text = res.stderr if res.returncode == 2 else res.stdout
    if res.returncode == 0 and res.stdout.strip():
        text = json.loads(res.stdout)["hookSpecificOutput"]["additionalContext"]
    return res.returncode, text


def main() -> int:
    failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        if not ok:
            failed += 1
        print(f"{'✓' if ok else '✗'} {name}" + (f"  — {detail}" if not ok and detail else ""))

    # ── что ловится ──────────────────────────────────────────────────────────
    code, text = run("cat README.md")
    check("cat файла проекта — предупреждение", code == 0 and "not a reading tool" in text, text[:90])

    code, text = run("cat README.md", mode="block")
    check("cat файла проекта — в block отказ", code == 2 and "BLOCKED" in text, text[:90])

    code, text = run("sed -i 's/a/b/' README.md", mode="block")
    check("sed -i по файлу проекта — отказ", code == 2 and "blind" in text, text[:90])

    code, text = run("python3 -c \"open('README.md','w').write('x')\"", mode="block")
    check("inline python ПИШЕТ файл проекта — отказ", code == 2 and "BLOCKED" in text, text[:90])

    code, text = run("python3 -c \"print(open('README.md').read())\"", mode="block")
    check("inline python печатает тело файла — отказ как за чтение",
          code == 2 and "reading tool" in text, text[:90])

    # ── что обязано проходить ────────────────────────────────────────────────
    compute = ("python3 - <<'PY'\n"
               "import io\n"
               "s = io.open('README.md', encoding='utf-8').read()\n"
               "print(len(s.splitlines()), 'строк')\n"
               "PY")
    code, text = run(compute, mode="block")
    check("python считает по файлу проекта и печатает числа — проходит",
          code == 0 and not text, f"код={code} {text[:90]}")

    code, text = run("python3 tools/check-doc-links.py", mode="block")
    check("запуск скрипта проекта — проходит", code == 0 and not text, text[:90])

    code, text = run("go build ./... && go test ./...", mode="block")
    check("сборка и тесты — проходят", code == 0 and not text, text[:90])

    code, text = run("git diff README.md | head -40", mode="block")
    check("git diff — проходит", code == 0 and not text, text[:90])

    code, text = run("cat ~/.zshrc", mode="block")
    check("файл вне проекта — проходит", code == 0 and not text, text[:90])

    code, text = run("cp workspace-setup/global-brief.md ~/.claude/brief.md", mode="block")
    check("cp — не правка, проходит", code == 0 and not text, text[:90])

    # ── два живых промаха 28.08.2026 ─────────────────────────────────────────
    #
    # Оба — про Bash в его законной роли: посмотреть на окружение. Хук ловил их
    # как работу с файлами проекта и отнимал по ходу за штуку.

    # Разделитель внутри кавычек резал команду на куски, которых никто не писал:
    # обрывок `select(.createdAt > "2026-08-20"` читался как перенаправление в
    # файл `2026-08-20` — без каталога, то есть внутри проекта.
    code, text = run(
        """gh issue list -R o/r --json createdAt --jq '.[] | select(.createdAt > "2026-08-20")'""",
        mode="block")
    check("разделитель внутри кавычек не режет команду",
          code == 0 and not text, text[:120])

    # Явно названный чужой каталог попадал под правило «пути нет, значит от
    # текущего каталога»: рекурсивная команда из каталога проекта считалась
    # чтением проекта, куда бы её ни направили.
    code, text = run("find ~/.local/share/claude -maxdepth 1 -type f", mode="block")
    check("рекурсия по ЧУЖОМУ каталогу — проходит", code == 0 and not text, text[:120])

    # Обратная сторона: без пути правило обязано остаться в силе.
    code, text = run("rg -n 'func main'", mode="block")
    check("рекурсия без пути из каталога проекта — отказ", code != 0 or bool(text),
          f"код={code} {text[:90]}")

    # И образец с точкой — не путь: `foo.bar` это регулярка, а не файл.
    code, text = run("grep -rn 'foo.bar'", mode="block")
    check("образец с точкой не считается путём — отказ", code != 0 or bool(text),
          f"код={code} {text[:90]}")

    # ── чьё это дерево: настройка, а не метка Serena ─────────────────────────
    # Хук решал «наше или нет» по метке `.serena/project.yml`. Метка отвечает на
    # другой вопрос, и обе ошибки были живыми: `asynchronus` без метки хук не
    # видел вовсе, а клон в песочнице с меткой считал своим.
    with tempfile.TemporaryDirectory() as времянка:
        песочница = os.path.join(времянка, "клон")
        os.makedirs(os.path.join(песочница, ".serena"))
        os.makedirs(os.path.join(песочница, "internal"))
        with open(os.path.join(песочница, ".serena", "project.yml"), "w") as f:
            f.write("project_name: клон\n")
        with open(os.path.join(песочница, "internal", "x.go"), "w") as f:
            f.write("package x\n")

        code, text = run("cat internal/x.go", mode="block", cwd=песочница)
        check("песочница под /tmp с меткой .serena — чужая, проходит",
              code == 0 and not text, f"код={code} {text[:90]}")

        code, text = run("cat internal/x.go", mode="block", cwd=песочница, roots=песочница)
        check("та же песочница, объявленная корнем, — наша, отказ",
              code == 2 and "BLOCKED" in text, f"код={code} {text[:90]}")

        дерево = os.path.join(времянка, "дерево")
        os.makedirs(os.path.join(дерево, "internal"))
        with open(os.path.join(дерево, "internal", "y.go"), "w") as f:
            f.write("package y\n")

        code, text = run("cat internal/y.go", mode="block", cwd=дерево, roots=дерево)
        check("наше дерево БЕЗ метки .serena — отказ", code == 2 and "BLOCKED" in text,
              f"код={code} {text[:90]}")

        code, text = run("cat internal/y.go", mode="block", cwd=дерево)
        check("оно же, не объявленное корнем, — проходит", code == 0 and not text,
              f"код={code} {text[:90]}")

    # Проект вне настроенных корней, но и не в чужом месте: метка по-прежнему
    # работает — старый способ никуда не делся, он лишь перестал быть единственным.
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as свой:
        os.makedirs(os.path.join(свой, ".serena"))
        with open(os.path.join(свой, ".serena", "project.yml"), "w") as f:
            f.write("project_name: сбоку\n")
        with open(os.path.join(свой, "a.go"), "w") as f:
            f.write("package a\n")
        code, text = run("cat a.go", mode="block", cwd=свой, roots="")
        check("проект с меткой вне корней — по-прежнему наш",
              code == 2 and "BLOCKED" in text, f"код={code} {text[:90]}")

    # ── длинная программа в аргументе ────────────────────────────────────────
    bulk = "python3 - <<'PY'\n" + "\n".join(f"x{i} = {i}" for i in range(14)) + "\nPY"
    code, text = run(bulk)
    check("длинный heredoc — совет положить в файл",
          code == 0 and "put it in a file" in text, text[:90])
    code, text = run(bulk, mode="block")
    check("длинный heredoc — в block отказ", code == 2 and "put it in a file" in text, text[:90])

    # Heredoc не всегда программа. Поймано на живом коммите 22.08: сообщение на
    # 31 строку хук счёл длинной программой, а в режиме block отменил бы коммит.
    msg = "git commit -F- <<'MSG'\n" + "\n".join(f"строка {i}" for i in range(20)) + "\nMSG"
    code, text = run(msg, mode="block")
    check("сообщение коммита в heredoc — не программа", code == 0 and not text, text[:90])

    code, text = run("mail -s тема кто@то <<'EOF'\n" + "текст\n" * 15 + "EOF", mode="block")
    check("длинный текст в heredoc у не-интерпретатора — проходит",
          code == 0 and not text, text[:90])

    short = "python3 - <<'PY'\nprint(2 + 2)\nPY"
    code, text = run(short, mode="block")
    check("короткий однострочник — проходит", code == 0 and not text, text[:90])

    # ── режим ────────────────────────────────────────────────────────────────
    payload = json.dumps({"tool_name": "Bash", "cwd": ROOT,
                          "tool_input": {"command": "cat README.md"}})
    env = {k: v for k, v in os.environ.items() if k != "NUDGE_SERENA_MODE"}
    res = subprocess.run([sys.executable, HOOK, "block"], input=payload,
                         capture_output=True, text=True, env=env)
    check("режим берётся из аргумента", res.returncode == 2, res.stderr[:90])

    res = subprocess.run([sys.executable, HOOK], input=payload,
                         capture_output=True, text=True, env=env)
    check("без аргумента и переменной — warn", res.returncode == 0 and res.stdout.strip() != "")

    res = subprocess.run([sys.executable, HOOK, "block"], input=payload, capture_output=True,
                         text=True, env=dict(env, NUDGE_SERENA_MODE="warn"))
    check("переменная старше аргумента", res.returncode == 0)

    # ── хук не имеет права ломать вызов ──────────────────────────────────────
    res = subprocess.run([sys.executable, HOOK], input="не json", capture_output=True, text=True)
    check("битый ввод не ломает вызов", res.returncode == 0)

    print(f"\nпровалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
