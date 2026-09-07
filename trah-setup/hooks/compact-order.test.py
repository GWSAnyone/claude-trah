#!/usr/bin/env python3
"""Проверки `compact-order.py`. Токенов не стоит.

Помощник заказывает сжатие — действие, которое сворачивает разговор целиком.
Поэтому проверяется не только «доехал кадр», но и каждый отказ: заказ без
чекпоинта, заказ по протухшему чекпоинту и повтор по горячим следам. Кадр
ловится настоящим сокетом, а не подменой функции: форма строки — это то, что
разбирает CLI, и ошибиться в ней значит промахнуться молча.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

СКРИПТ = str(Path(__file__).resolve().parent / "compact-order.py")
ХУКИ = str(Path(__file__).resolve().parent)

всего = 0
провалов = 0


def check(имя: str, условие: bool, подробность: str = "") -> None:
    global всего, провалов
    всего += 1
    if not условие:
        провалов += 1
        print(f"  ✗ {имя} {подробность}")


class Ухо:
    """Сокет вместо сессии: принимает одно соединение и запоминает строки."""

    def __init__(self, путь: str):
        self.путь = путь
        self.строки: list[str] = []
        self.сокет = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.сокет.bind(путь)
        self.сокет.listen(4)
        self.поток = threading.Thread(target=self._слушать, daemon=True)
        self.поток.start()

    def _слушать(self) -> None:
        while True:
            try:
                связь, _ = self.сокет.accept()
            except OSError:
                return
            with связь:
                данные = b""
                связь.settimeout(2)
                try:
                    while True:
                        кусок = связь.recv(65536)
                        if not кусок:
                            break
                        данные += кусок
                except OSError:
                    pass
                for строка in данные.decode("utf-8", "replace").splitlines():
                    if строка.strip():
                        self.строки.append(строка)

    def закрыть(self) -> None:
        self.сокет.close()


def чекпоинт(каталог: str, session_id: str, возраст_мин: int = 0) -> Path:
    """Кладёт чекпоинт нужной свежести по правилам самого `checkpoint.py`."""
    sys.path.insert(0, ХУКИ)
    import importlib.util
    спец = importlib.util.spec_from_file_location(
        "cp_for_test", str(Path(ХУКИ) / "checkpoint.py"))
    cp = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(cp)
    путь = Path(cp.resolve_checkpoint(каталог, session_id))
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps({
        "plan": "docs/plans/проба.md", "project": "проба",
        "next": "дописать проверку"}, ensure_ascii=False),
        encoding="utf-8")
    # Свежесть — по mtime файла: с 30.08.2026 метку времени в JSON никто не
    # пишет, её ставила модель по памяти и однажды промахнулась на три часа.
    когда = time.time() - возраст_мин * 60
    os.utime(путь, (когда, когда))
    return путь


def run(cwd: str, аргументы: list[str], сокет_путь: str | None,
        session_id: str = "abcdef12-0000"):
    env = dict(os.environ, TRAH_HOOKS_DIR=ХУКИ, CLAUDE_CODE_SESSION_ID=session_id)
    env.pop("CLAUDE_PID", None)
    if сокет_путь:
        env["CLAUDE_CODE_MESSAGING_SOCKET"] = сокет_путь
    else:
        env.pop("CLAUDE_CODE_MESSAGING_SOCKET", None)
    р = subprocess.run([sys.executable, СКРИПТ, *аргументы],
                       capture_output=True, text=True, cwd=cwd, env=env)
    return р.returncode, р.stdout, р.stderr


def main() -> int:
    # ── сломанное окружение ──────────────────────────────────────────────────
    print("окружение")
    with tempfile.TemporaryDirectory() as tmp:
        код, вых, ош = run(tmp, [], None)
        check("без сокета — код 2", код == 2, str(код))
        check("и сказано, чего не нашлось", "Сокет сессии не найден" in ош, ош[:120])

        код, вых, ош = run(tmp, [], str(Path(tmp) / "нет-такого.sock"))
        check("несуществующий сокет — тоже 2", код == 2, str(код))

    # ── отказы по чекпоинту ──────────────────────────────────────────────────
    print("чекпоинт")
    with tempfile.TemporaryDirectory() as tmp:
        ухо = Ухо(str(Path(tmp) / "сессия.sock"))
        try:
            код, вых, ош = run(tmp, [], ухо.путь)
            check("без чекпоинта — отказ", код == 1, str(код))
            check("и сказано почему", "чекпоинта нет" in ош, ош[:120])
            check("и кадр НЕ ушёл", not ухо.строки, str(ухо.строки))

            чекпоинт(tmp, "abcdef12-0000", возраст_мин=45)
            код, вых, ош = run(tmp, [], ухо.путь)
            check("протухший чекпоинт — отказ", код == 1, str(код))
            check("названы минуты", "протух на 4" in ош, ош[:160])
            check("кадр всё ещё не ушёл", not ухо.строки, str(ухо.строки))

            # Метка из будущего — не «бесконечно свежий» чекпоинт, а поломка
            # часов. 29.08.2026 ровно из-за неё сторож пропускал всё подряд.
            чекпоинт(tmp, "abcdef12-0000", возраст_мин=-26 * 60)
            код, вых, ош = run(tmp, [], ухо.путь)
            check("метка из будущего — отказ", код == 1, str(код))
            check("и названа настоящая причина", "В БУДУЩЕМ" in ош, ош[:200])
            check("кадр не ушёл и здесь", not ухо.строки, str(ухо.строки))
        finally:
            ухо.закрыть()

    # ── заказ ────────────────────────────────────────────────────────────────
    print("заказ")
    with tempfile.TemporaryDirectory() as tmp:
        ухо = Ухо(str(Path(tmp) / "сессия.sock"))
        try:
            чекпоинт(tmp, "abcdef12-0000", возраст_мин=1)

            код, вых, ош = run(tmp, ["--dry-run"], ухо.путь)
            check("вхолостую — код 0", код == 0, ош[:160])
            вхолостую = json.loads(вых)
            check("вхолостую кадр не уходит", not ухо.строки, str(ухо.строки))
            check("текст кадра — голая команда",
                  вхолостую["кадр"]["message"]["content"] == "/compact",
                  json.dumps(вхолостую, ensure_ascii=False))
            check("session_id по умолчанию НЕ ставится",
                  "session_id" not in вхолостую["кадр"], str(вхолостую["кадр"]))

            код, вых, ош = run(tmp, ["--dry-run", "--id"], ухо.путь)
            check("с ключом --id идентификатор появляется",
                  json.loads(вых)["кадр"].get("session_id") == "abcdef12-0000", вых)

            код, вых, ош = run(tmp, ["--dry-run", "сожми", "покороче"], ухо.путь)
            check("довесок приклеивается к команде",
                  json.loads(вых)["кадр"]["message"]["content"] == "/compact сожми покороче",
                  вых)

            код, вых, ош = run(tmp, [], ухо.путь)
            check("настоящий заказ — код 0", код == 0, ош[:200])
            time.sleep(0.6)
            check("кадр доехал ровно один", len(ухо.строки) == 1, str(ухо.строки))
            кадр = json.loads(ухо.строки[0])
            check("кадр — user-сообщение", кадр.get("type") == "user", str(кадр))
            check("в кадре команда", кадр["message"]["content"] == "/compact", str(кадр))
            check("в ответе сказано, когда сработает",
                  "в конце этого хода" in вых, вых[:200])

            # ── повтор ───────────────────────────────────────────────────────
            код, вых, ош = run(tmp, [], ухо.путь)
            check("повтор по горячим следам отбит", код == 1, str(код))
            check("и сказано про --again", "--again" in ош, ош[:200])
            time.sleep(0.4)
            check("повторный кадр не ушёл", len(ухо.строки) == 1, str(ухо.строки))

            код, вых, ош = run(tmp, ["--again"], ухо.путь)
            check("с ключом --again повтор проходит", код == 0, ош[:200])
            time.sleep(0.6)
            check("и второй кадр доехал", len(ухо.строки) == 2, str(ухо.строки))
        finally:
            ухо.закрыть()

    # ── метка повтора живёт у своей сессии ───────────────────────────────────
    print("разделение сессий")
    with tempfile.TemporaryDirectory() as tmp:
        ухо = Ухо(str(Path(tmp) / "сессия.sock"))
        try:
            чекпоинт(tmp, "aaaaaaaa-1111", возраст_мин=1)
            чекпоинт(tmp, "bbbbbbbb-2222", возраст_мин=1)
            run(tmp, [], ухо.путь, session_id="aaaaaaaa-1111")
            код, вых, ош = run(tmp, [], ухо.путь, session_id="bbbbbbbb-2222")
            check("заказ соседней сессии не мешает", код == 0, ош[:200])
        finally:
            ухо.закрыть()

    print(f"\nвсего: {всего}, провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    raise SystemExit(main())
