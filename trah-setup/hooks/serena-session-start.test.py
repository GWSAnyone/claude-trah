#!/usr/bin/env python3
"""Тесты хука SessionStart, называющего первое действие сессии."""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serena-session-start.py")


def run(cwd: str, ports: str = "1", bound: str | None = None) -> dict:
    """Запускает хук. `ports` — что подсунуть вместо портов панели Serena.

    По умолчанию порт 1: соединение отказывают сразу, и хук ведёт себя так, как
    на машине без поднятой Serena. Иначе тест зависел бы от того, работает ли
    сейчас сервер у того, кто его запускает.

    `bound` — что положить в `TRAH_SERENA_PROJECT`, переменную обёртки. Она
    ВСЕГДА выставляется явно, даже пустым значением: тест запускают и из живой
    сессии `claude trah`, где переменная уже стоит, и без этой чистки прогон
    проверял бы чужой каталог вместо заданного.
    """
    payload = json.dumps({"session_id": "s1", "cwd": cwd, "hook_event_name": "SessionStart"})
    env = dict(os.environ, SERENA_DASHBOARD_PORTS=ports)
    env.pop("TRAH_SERENA_PROJECT", None)
    if bound is not None:
        env["TRAH_SERENA_PROJECT"] = bound
    res = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True,
                         text=True, env=env)
    assert res.returncode == 0, f"хук вернул {res.returncode}: {res.stderr}"
    return json.loads(res.stdout)


def context(cwd: str, ports: str = "1", bound: str | None = None) -> str:
    return run(cwd, ports, bound)["hookSpecificOutput"]["additionalContext"]


def make_tree(base: str, *rel_dirs: str) -> None:
    """Создаёт каталоги и кладёт в каждый по `.serena/project.yml`."""
    for rel in rel_dirs:
        path = os.path.join(base, rel, ".serena")
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "project.yml"), "w", encoding="utf-8") as f:
            f.write("project_name: проба\n")


class Dashboard:
    """Заглушка панели Serena: отвечает на любой GET заданным проектом.

    Настоящую панель в тест не затащишь: она есть не на всякой машине, а её
    активный проект меняется от того, что делает соседняя сессия.
    """

    def __init__(self, name: str, path: str | None) -> None:
        payload = {"active_project": {"name": name, "path": path}} if path else {}
        body = json.dumps(payload).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 — имя задано базовым классом
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:
                pass  # без этого каждый запрос печатается в вывод теста

        self._srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def __enter__(self) -> "Dashboard":
        return self

    def __exit__(self, *exc) -> None:
        self._srv.shutdown()
        self._srv.server_close()


def main() -> int:
    failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        if not ok:
            failed += 1
        print(f"{'✓' if ok else '✗'} {name}" + (f"  — {detail}" if not ok and detail else ""))

    # Хук всегда называет оба шага: подтянуть инструменты и получить правила.
    text = context(os.path.expanduser("~"))
    check("зовёт ToolSearch", "ToolSearch(" in text)
    # `activate_project` в списке для ToolSearch быть НЕ ДОЛЖНО: сборка держит
    # один проект на сервер (`single_project: true`), инструмент отключён, и
    # имя молча выпадает из ответа — а сессия остаётся с верой, что он есть.
    check("не просит несуществующий activate_project",
          'select:' in text and "activate_project," not in text.split("ToolSearch(")[1][:600])
    # Сказать, что его нет, хук обязан — иначе указание «дай пути относительно
    # корня» читается как «активируй корень».
    check("говорит, что активировать нечем",
          "There is no `activate_project` in the tool list" in text)
    check("не повторяет сами правила", "Лестница выбора" not in text and "DOTALL" not in text)
    check("отсылает за правилами в системный промпт", "system prompt" in text)

    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as home_tmp:
        # Экосистема с под-проектом внутри: победить обязан ВНЕШНИЙ корень,
        # иначе сессия активирует под-проект и потеряет кросс-проектный поиск.
        make_tree(home_tmp, "eco", os.path.join("eco", "sub"))
        deep = os.path.join(home_tmp, "eco", "sub", "internal", "x")
        os.makedirs(deep, exist_ok=True)

        text = context(deep)
        check("выбран внешний корень, а не под-проект",
              "/eco`" in text and "/eco/sub`" not in text, text[:200])

        # Дом корнем быть не может, даже когда метка в нём лежит: ~/.serena
        # существует у всех, кто хоть раз активировал Serena из дома, и без
        # оговорки «самый внешний» вырождается в домашний каталог. Ловушка
        # уже срабатывала дважды — в nudge-serena.py и здесь.
        check("дом корнем не считается", "is `~`" not in text, text[:200])

        # Каталог вне какой-либо экосистемы — указания без имени, но без ошибки.
        plain = os.path.join(home_tmp, "просто-каталог")
        os.makedirs(plain, exist_ok=True)
        text = context(plain)
        check("без экосистемы — говорит про перезапуск, а не про активацию",
              "No ecosystem root above this directory" in text
              and "Restart the session" in text, text[:220])

    # Панель Serena знает, какой проект активен. Пока она это говорит, активация
    # после сжатия — выброшенные две тысячи токенов, и хук обязан это назвать.
    with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as home_tmp:
        make_tree(home_tmp, "eco")
        root = os.path.realpath(os.path.join(home_tmp, "eco"))
        inside = os.path.join(root, "internal")
        os.makedirs(inside, exist_ok=True)

        # Переменная обёртки — знание из первых рук, и она бьёт панель.
        text = context(inside, ports="1", bound=root)
        check("обёртка назвала корень — активировать нечего",
              "Nothing to activate" in text and "the launcher" in text, text[:220])

        # Обёртка привязала не туда — честно сказать об этом и позвать
        # перезапуститься, а не активировать.
        text = context(inside, ports="1", bound=os.path.expanduser("~"))
        check("обёртка привязала чужое дерево — зовёт перезапуститься",
              "Serena is bound to" in text and "restart the session" in text.lower(),
              text[:220])

        with Dashboard("eco", root) as dash:
            text = context(inside, ports=str(dash.port))
            check("панель согласна с корнем — активировать нечего",
                  "Nothing to activate" in text and "dashboard" in text, text[:220])

        # ГЛАВНАЯ ловушка. Панель нашего сервера выключена, отвечает сервер
        # ЧУЖОЙ сессии — и раньше хук на этом основании велел активировать
        # проект инструментом, которого нет. Теперь расхождение не значит
        # ничего: корень называется, приказа активировать нет.
        with Dashboard("чужой", os.path.expanduser("~")) as dash:
            text = context(inside, ports=str(dash.port))
            check("панель назвала чужой проект — приказа активировать нет",
                  "/eco`" in text and "Activate" not in text
                  and "There is no `activate_project`" in text, text[:220])

        with Dashboard("eco", None) as dash:
            text = context(inside, ports=str(dash.port))
            check("ответ панели без проекта — просто корень, без активации",
                  "/eco`" in text and "Activate" not in text, text[:220])

        text = context(inside, ports="1")
        check("панель молчит — просто корень, без активации",
              "/eco`" in text and "Activate" not in text, text[:220])

    # Пустой и небывалый каталог хук не роняют.
    check("пустой cwd не роняет", "ToolSearch(" in context(""))
    check("несуществующий cwd не роняет", "ToolSearch(" in context("/нет/такого/пути"))

    # Битый ввод — молча ноль: хук не имеет права ломать подъём сессии.
    res = subprocess.run([sys.executable, HOOK], input="не json", capture_output=True, text=True)
    check("битый ввод не ломает подъём", res.returncode == 0)

    print(f"\nпровалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
