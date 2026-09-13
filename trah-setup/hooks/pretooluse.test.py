#!/usr/bin/env python3
"""Проверки диспетчера `pretooluse.py`. Токенов не стоит.

Диспетчер — общий процесс для всех сторожей, поэтому проверять надо не только
то, что он делает, но и то, чего он НЕ делает: не глотает запрет, не роняет
вызов из-за сломанного модуля, не зовёт чужой модуль на чужой инструмент.

Подставные модули кладутся во временный каталог под теми же именами, что и
настоящие: диспетчер берёт их через PRETOOLUSE_DIR.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ХУК = str(Path(__file__).resolve().parent / "pretooluse.py")
РЕПО = str(Path(__file__).resolve().parents[2])

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


ПОДСТАВНОЙ = '''\
import sys, json
def main():
    sys.stdin.read()
    {тело}
'''


def положить(каталог: Path, имя: str, тело: str) -> None:
    (каталог / имя).write_text(ПОДСТАВНОЙ.replace("{тело}", тело), encoding="utf-8")


# Образцы подставных модулей — те же и в том же порядке, что в реестре
# комплекта: проверки опираются и на порядок (сторож раньше подсказчика), и на
# отбор по инструменту.
ОБРАЗЦЫ = (
    ("guard-destructive.py", "Bash"),
    ("guard-sleep.py", "Bash|PowerShell"),
    ("guard-serena-scope.py", "mcp__serena__.*"),
    ("nudge-serena.py", "Bash|PowerShell"),
    ("serena-remind-shim.py", ".*"),
)


def реестр(каталог: Path) -> None:
    """Реестр по тому, что лежит в каталоге сейчас. Подставные модули по ходу
    проверок появляются и исчезают, а диспетчер читает список из файла — значит
    файл надо держать в согласии с диском."""
    записи = [{"файл": и, "образец": о} for и, о in ОБРАЗЦЫ if (каталог / и).exists()]
    (каталог / "modules.json").write_text(
        json.dumps({"модули": записи}, ensure_ascii=False), encoding="utf-8")


def прогнать(каталог, инструмент="Bash", команда="ls -la", raw=None,
             окружение=None):
    полезное = raw if raw is not None else json.dumps(
        {"tool_name": инструмент, "cwd": РЕПО,
         "tool_input": {"command": команда}}, ensure_ascii=False)
    реестр(Path(каталог))
    env = dict(os.environ, PRETOOLUSE_DIR=str(каталог))
    env.pop("PRETOOLUSE", None)
    env.pop("PRETOOLUSE_ONLY", None)
    env.pop("TRAH_MODE", None)
    env.update(окружение or {})
    р = subprocess.run([sys.executable, ХУК], input=полезное,
                       capture_output=True, text=True, env=env)
    return р.returncode, р.stdout, р.stderr


def json_ответ(вывод: str) -> dict:
    try:
        return json.loads(вывод)
    except ValueError:
        return {}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        к = Path(tmp)

        # ── запрет кодом 2 доходит наружу дословно ───────────────────────────
        положить(к, "guard-destructive.py",
                 'sys.stderr.write("НЕЛЬЗЯ: так не делают"); return 2')
        положить(к, "nudge-serena.py",
                 '(Path := None); print("НЕ ДОЛЖЕН БЫЛ ЗВАТЬСЯ"); return 0')
        код, вывод, ошибки = прогнать(к)
        check("запрет отдаётся кодом 2", код == 2, str(код))
        check("текст запрета не искажён", "НЕЛЬЗЯ: так не делают" in ошибки,
              repr(ошибки[:80]))
        check("после запрета следующие модули не зовутся",
              "НЕ ДОЛЖЕН" not in вывод, repr(вывод[:80]))

        # ── запрет, выраженный JSON'ом (так делает апстрим Serena) ───────────
        os.remove(к / "guard-destructive.py")
        положить(к, "serena-remind-shim.py",
                 'print(json.dumps({"hookSpecificOutput": '
                 '{"hookEventName": "PreToolUse", "permissionDecision": "deny", '
                 '"permissionDecisionReason": "too-many-greps"}})); return 0')
        os.remove(к / "nudge-serena.py")
        код, вывод, _ = прогнать(к)
        check("JSON-запрет проходит дословно",
              код == 0 and "deny" in вывод and "too-many-greps" in вывод,
              repr(вывод[:120]))

        # ── образцы: чужой инструмент чужой модуль не зовёт ──────────────────
        os.remove(к / "serena-remind-shim.py")
        положить(к, "guard-destructive.py", 'print("ЗВАЛИ BASH"); return 0')
        положить(к, "guard-serena-scope.py", 'print("ЗВАЛИ SERENA"); return 0')
        код, вывод, _ = прогнать(к, инструмент="Read")
        check("Bash-модуль не зовётся на Read", "ЗВАЛИ BASH" not in вывод,
              repr(вывод[:80]))
        check("serena-модуль не зовётся на Read", "ЗВАЛИ SERENA" not in вывод,
              repr(вывод[:80]))
        код, вывод, _ = прогнать(к, инструмент="mcp__serena__find_symbol")
        check("serena-модуль зовётся на свой инструмент", "ЗВАЛИ SERENA" in вывод,
              repr(вывод[:80]))
        код, вывод, _ = прогнать(к, инструмент="Bash")
        check("Bash-модуль зовётся на Bash", "ЗВАЛИ BASH" in вывод, repr(вывод[:80]))

        # ── два сообщения склеиваются, а не затирают друг друга ──────────────
        положить(к, "guard-destructive.py",
                 'print(json.dumps({"systemMessage": "первое", '
                 '"hookSpecificOutput": {"hookEventName": "PreToolUse", '
                 '"additionalContext": "контекст-раз"}})); return 0')
        положить(к, "nudge-serena.py",
                 'print(json.dumps({"systemMessage": "второе", '
                 '"hookSpecificOutput": {"hookEventName": "PreToolUse", '
                 '"additionalContext": "контекст-два"}})); return 0')
        os.remove(к / "guard-serena-scope.py")
        код, вывод, _ = прогнать(к)
        д = json_ответ(вывод)
        check("оба сообщения на месте",
              "первое" in д.get("systemMessage", "")
              and "второе" in д.get("systemMessage", ""), repr(вывод[:120]))
        добавка = (д.get("hookSpecificOutput") or {}).get("additionalContext", "")
        check("обе добавки к контексту на месте",
              "контекст-раз" in добавка and "контекст-два" in добавка,
              repr(добавка[:120]))
        check("порядок сохранён: сторож раньше подсказчика",
              д.get("systemMessage", "").index("первое")
              < д.get("systemMessage", "").index("второе"), д.get("systemMessage"))

        # ── сломанный модуль: заметно, но не запрет, и соседи работают ───────
        положить(к, "guard-destructive.py", 'raise ValueError("я сломался")')
        код, вывод, ошибки = прогнать(к)
        д = json_ответ(вывод)
        check("падение модуля не запрещает вызов", код == 0, str(код))
        check("виновник назван",
              "guard-destructive.py" in д.get("systemMessage", "")
              and "ValueError" in д.get("systemMessage", ""), repr(вывод[:140]))
        check("соседний модуль всё равно отработал",
              "второе" in д.get("systemMessage", ""), repr(вывод[:140]))

        # Модуль, вызывающий sys.exit(2) вместо return, — тоже запрет.
        положить(к, "guard-destructive.py",
                 'sys.stderr.write("выход двойкой"); sys.exit(2)')
        код, _, ошибки = прогнать(к)
        check("sys.exit(2) считается запретом", код == 2, str(код))
        check("текст такого запрета доходит", "выход двойкой" in ошибки,
              repr(ошибки[:80]))

        # ── отсутствующий файл модуля — не беда ──────────────────────────────
        # `__pycache__` появляется от самого импорта; сносим и его, иначе
        # «ни одного модуля» окажется неправдой.
        for f in к.iterdir():
            shutil.rmtree(f) if f.is_dir() else f.unlink()
        код, вывод, ошибки = прогнать(к)
        check("нет ни одного модуля — тишина и ноль",
              код == 0 and вывод == "" and ошибки == "",
              repr((вывод + ошибки)[:80]))

        # ── мусор на входе и выключатель ─────────────────────────────────────
        положить(к, "guard-destructive.py", 'print("не должно быть"); return 0')
        код, вывод, _ = прогнать(к, raw="не json")
        check("мусор на входе не роняет", код == 0 and вывод == "", repr(вывод[:60]))
        код, вывод, _ = прогнать(к, raw=json.dumps([1, 2, 3]))
        check("не словарь на входе не роняет", код == 0 and вывод == "",
              repr(вывод[:60]))
        код, вывод, _ = прогнать(к, окружение={"PRETOOLUSE": "off"})
        check("выключатель гасит всё", код == 0 and вывод == "", repr(вывод[:60]))
        код, вывод, _ = прогнать(к, окружение={"PRETOOLUSE_ONLY": "nudge-serena.py"})
        check("отбор модулей работает", код == 0 and вывод == "", repr(вывод[:60]))

    # ── на настоящих модулях: запрет и тишина ───────────────────────────────
    свои = Path(__file__).resolve().parent
    полезное = json.dumps({"tool_name": "Bash", "cwd": РЕПО,
                           "tool_input": {"command": "git reset --hard HEAD~1"}})
    р = subprocess.run([sys.executable, ХУК], input=полезное, capture_output=True,
                       text=True, env=dict(os.environ, PRETOOLUSE_DIR=str(свои)))
    check("настоящий сторож запрещает разрушительное", р.returncode == 2,
          f"{р.returncode} {р.stdout[:60]}{р.stderr[:60]}")

    полезное = json.dumps({"tool_name": "Bash", "cwd": РЕПО,
                           "tool_input": {"command": "go build ./..."}})
    р = subprocess.run([sys.executable, ХУК], input=полезное, capture_output=True,
                       text=True, env=dict(os.environ, PRETOOLUSE_DIR=str(свои)))
    check("обычная сборка проходит молча",
          р.returncode == 0 and not р.stdout.strip(),
          f"{р.returncode} {р.stdout[:80]}")

    # ── реестр комплекта сверен с диском ────────────────────────────────────
    #
    # Диспетчер молчит о пропавшем модуле НАМЕРЕННО: сторож, снесённый вместе с
    # переездом на другую машину, не должен ронять каждый вызов Bash. Цена этой
    # мягкости — что опечатка в имени и снесённый файл выглядят одинаково, то
    # есть никак. Здесь и стоит проверка: в НАШЕМ реестре все файлы на месте.
    #
    # Чужих модулей в своём реестре не бывает по устройству: для них есть
    # `modules.local.json`, и комплект его не пишет.
    спец_ = importlib.util.spec_from_file_location("pretooluse", ХУК)
    модуль = importlib.util.module_from_spec(спец_)
    спец_.loader.exec_module(модуль)
    свой = json.loads((свои / "modules.json").read_text(encoding="utf-8"))
    записи = свой["модули"]
    check("в реестре комплекта шесть модулей", len(записи) == 6, f"={len(записи)}")
    пропавшие = [з["файл"] for з in записи if not (свои / з["файл"]).exists()]
    check("каждый модуль реестра лежит на диске", not пропавшие, f"={пропавшие}")
    чужие = [з["файл"] for з in записи if з.get("требует")]
    check("свой реестр не требует чужих утилит", not чужие, f"={чужие}")

    # ── чужой реестр: читается обычным claude, но не режимом `trah` ──────────
    #
    # Ради этого реестр и заводился. Сессия режима не подчиняется правилам
    # продукта, с которым она не работает, — а вне режима те же правила стоят.
    with tempfile.TemporaryDirectory() as tmp:
        к = Path(tmp)
        положить(к, "guard-destructive.py", 'print("СВОЙ"); return 0')
        реестр(к)
        (к / "guard-chuzhoy.py").write_text(
            ПОДСТАВНОЙ.replace("{тело}", 'print("ЧУЖОЙ"); return 0'),
            encoding="utf-8")
        (к / "modules.local.json").write_text(json.dumps(
            {"модули": [{"файл": "guard-chuzhoy.py", "образец": "Bash"}]},
            ensure_ascii=False), encoding="utf-8")

        env = dict(os.environ, PRETOOLUSE_DIR=str(к))
        env.pop("PRETOOLUSE", None)
        env.pop("PRETOOLUSE_ONLY", None)
        полезное = json.dumps({"tool_name": "Bash", "cwd": РЕПО,
                               "tool_input": {"command": "ls"}})

        env.pop("TRAH_MODE", None)
        р = subprocess.run([sys.executable, ХУК], input=полезное,
                           capture_output=True, text=True, env=env)
        check("вне режима чужой модуль зовётся",
              "ЧУЖОЙ" in р.stdout and "СВОЙ" in р.stdout, repr(р.stdout[:100]))

        р = subprocess.run([sys.executable, ХУК], input=полезное,
                           capture_output=True, text=True,
                           env=dict(env, TRAH_MODE="1"))
        check("в режиме `trah` чужой модуль не зовётся",
              "ЧУЖОЙ" not in р.stdout and "СВОЙ" in р.stdout, repr(р.stdout[:100]))

        # Утилита, которой нет: модуль объявлен, но не зовётся.
        (к / "modules.local.json").write_text(json.dumps(
            {"модули": [{"файл": "guard-chuzhoy.py", "образец": "Bash",
                         "требует": ["этой-утилиты-нет"]}]},
            ensure_ascii=False), encoding="utf-8")
        р = subprocess.run([sys.executable, ХУК], input=полезное,
                           capture_output=True, text=True, env=env)
        check("модуль без своей утилиты не зовётся", "ЧУЖОЙ" not in р.stdout,
              repr(р.stdout[:100]))

        # Битый реестр не роняет вызов.
        (к / "modules.local.json").write_text("{ это не json", encoding="utf-8")
        р = subprocess.run([sys.executable, ХУК], input=полезное,
                           capture_output=True, text=True, env=env)
        check("битый реестр не роняет вызов",
              р.returncode == 0 and "СВОЙ" in р.stdout,
              f"{р.returncode} {р.stdout[:80]}")

    print(f"всего: {всего}   провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
