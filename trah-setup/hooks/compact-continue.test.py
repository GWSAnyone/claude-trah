#!/usr/bin/env python3
"""Проверки `compact-continue.py`. Токенов не стоит.

Хук решает, подгонять ли работу после сжатия, и обе стороны развилки стоят
дорого: промолчав там, где сессия сама заказала сжатие, мы оставляем работу
стоять до следующей реплики владельца; заговорив там, где он нажал сам, —
отнимаем у него возможность перехватить. Поэтому проверяется каждая ветка, и
отдельно — что метка съедается в любом случае.
"""
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "compact-continue.py")
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
    def __init__(self, путь: str):
        self.путь = путь
        self.строки: list[str] = []
        self.сокет = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.сокет.bind(путь)
        self.сокет.listen(4)
        threading.Thread(target=self._слушать, daemon=True).start()

    def _слушать(self) -> None:
        while True:
            try:
                связь, _ = self.сокет.accept()
            except OSError:
                return
            with связь:
                связь.settimeout(2)
                данные = b""
                try:
                    while кусок := связь.recv(65536):
                        данные += кусок
                except OSError:
                    pass
                self.строки += [с for с in данные.decode("utf-8", "replace").splitlines() if с.strip()]

    def закрыть(self) -> None:
        self.сокет.close()


def cp_модуль():
    спец = importlib.util.spec_from_file_location(
        "cp_for_test", str(Path(ХУКИ) / "checkpoint.py"))
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


CP = cp_модуль()


def метка(каталог: str, session_id: str, возраст_сек: float = 0) -> Path:
    путь = Path(каталог) / ".claude" / f".compact-ordered-{CP.suffix_for(session_id)}"
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text("заказано\n", encoding="utf-8")
    if возраст_сек:
        когда = time.time() - возраст_сек
        os.utime(путь, (когда, когда))
    return путь


def чекпоинт(каталог: str, session_id: str) -> None:
    путь = Path(CP.resolve_checkpoint(каталог, session_id))
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps({
        "plan": "docs/plans/проба.md", "project": "проба",
        "next": "дописать проверку",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False),
        encoding="utf-8")


def run(cwd: str, session_id: str, сокет: str | None,
        режим: str | None = None, сырьё: str | None = None,
        событие: str = "PostCompact"):
    env = dict(os.environ, TRAH_HOOKS_DIR=ХУКИ)
    env.pop("CLAUDE_PID", None)
    env["CLAUDE_CODE_MESSAGING_SOCKET"] = сокет or str(Path(cwd) / "нет.sock")
    if режим is None:
        env.pop("COMPACT_CONTINUE", None)
    else:
        env["COMPACT_CONTINUE"] = режим
    вход = сырьё if сырьё is not None else json.dumps(
        {"cwd": cwd, "session_id": session_id, "trigger": "manual",
         "hook_event_name": событие})
    р = subprocess.run([sys.executable, HOOK], input=вход,
                       capture_output=True, text=True, env=env)
    return р.returncode, р.stdout, р.stderr


def main() -> int:
    print("развилка «кто заказал»")
    with tempfile.TemporaryDirectory() as tmp:
        ухо = Ухо(str(Path(tmp) / "сессия.sock"))
        try:
            чекпоинт(tmp, "aaaaaaaa-1111")

            # Метки нет — нажал человек.
            код, вых, ош = run(tmp, "aaaaaaaa-1111", ухо.путь)
            time.sleep(0.5)
            check("без метки молчит", код == 0 and not ухо.строки, str(ухо.строки))

            # Метка свежая — заказала сессия.
            м = метка(tmp, "aaaaaaaa-1111")
            код, вых, ош = run(tmp, "aaaaaaaa-1111", ухо.путь)
            time.sleep(0.6)
            check("со свежей меткой кадр уходит", len(ухо.строки) == 1, str(ухо.строки))
            check("метка съедена", not м.exists())
            кадр = json.loads(ухо.строки[0]) if ухо.строки else {}
            текст = кадр.get("message", {}).get("content", "")
            check("кадр — user-сообщение", кадр.get("type") == "user", str(кадр))
            check("сказано, что заказывал сам",
                  "You ordered this yourself" in текст, текст[:200])
            check("назван план из чекпоинта",
                  "docs/plans/проба.md" in текст, текст[:400])
            check("названо следующее действие",
                  "дописать проверку" in текст, текст[:400])
            check("сказано не начинать заново",
                  "Do not start over" in текст, текст[-300:])

            # Метка протухшая — заказ был, но до сжатия не дошёл. Окно с
            # 01.09.2026 равно часу: между заказом и удавшимся сжатием
            # умещается круг отказа сторожа и обновление записи.
            старая = метка(tmp, "aaaaaaaa-1111", возраст_сек=90 * 60)
            ухо.строки.clear()
            код, вых, ош = run(tmp, "aaaaaaaa-1111", ухо.путь)
            time.sleep(0.5)
            check("протухшая метка не подгоняет работу",
                  not ухо.строки, str(ухо.строки))
            check("но съедается тоже", not старая.exists())

            # Метка соседней сессии — не наша.
            метка(tmp, "bbbbbbbb-2222")
            ухо.строки.clear()
            код, вых, ош = run(tmp, "aaaaaaaa-1111", ухо.путь)
            time.sleep(0.5)
            check("метка другой сессии не считается своей",
                  not ухо.строки, str(ухо.строки))
        finally:
            ухо.закрыть()

    print("отказоустойчивость")
    with tempfile.TemporaryDirectory() as tmp:
        ухо = Ухо(str(Path(tmp) / "сессия.sock"))
        try:
            чекпоинт(tmp, "cccccccc-3333")
            метка(tmp, "cccccccc-3333")
            код, вых, ош = run(tmp, "cccccccc-3333", ухо.путь, режим="off")
            time.sleep(0.4)
            check("выключатель работает", not ухо.строки, str(ухо.строки))
        finally:
            ухо.закрыть()

        метка(tmp, "dddddddd-4444")
        чекпоинт(tmp, "dddddddd-4444")
        код, вых, ош = run(tmp, "dddddddd-4444", None)
        check("без сокета не падает", код == 0, ош[:200])
        check("и говорит об этом в stderr", "compact-continue" in ош, ош[:200])

        код, вых, ош = run(tmp, "eeeeeeee-5555", None, сырьё="это не json")
        check("битый вход не роняет хук", код == 0, ош[:200])

        # Чекпоинта нет — кадр всё равно уходит: работа важнее указателя.
        ухо2 = Ухо(str(Path(tmp) / "вторая.sock"))
        try:
            метка(tmp, "ffffffff-6666")
            код, вых, ош = run(tmp, "ffffffff-6666", ухо2.путь)
            time.sleep(0.6)
            check("без чекпоинта кадр всё равно уходит",
                  len(ухо2.строки) == 1, str(ухо2.строки))
            текст = json.loads(ухо2.строки[0])["message"]["content"] if ухо2.строки else ""
            check("и без указателя текст осмысленный",
                  "Carry on from that step" in текст, текст[:300])
        finally:
            ухо2.закрыть()

    # Stop при активном `/goal`: без остановки хода заказ в очереди не
    # исполняется, потому что отказ оценщика продолжает ход.
    print("Stop: заказ исполняется и при /goal")
    with tempfile.TemporaryDirectory() as tmp:
        sid = "abababab-7777"
        код, вых, ош = run(tmp, sid, None, событие="Stop")
        check("без заказа ход не держит", код == 0 and not вых.strip(), вых)

        м = метка(tmp, sid, возраст_сек=30)
        было = м.stat().st_mtime_ns
        код, вых, ош = run(tmp, sid, None, событие="Stop")
        ответ = json.loads(вых) if вых.strip() else {}
        check("свежий заказ кончает ход", ответ.get("continue") is False, вых)
        check("и называет причину", "сжатие" in ответ.get("stopReason", ""), вых)
        check("метка на месте для PostCompact", м.exists())
        check("время метки не сдвинуто", м.stat().st_mtime_ns == было,
              f"{было} → {м.stat().st_mtime_ns}")

        код, вых, ош = run(tmp, sid, None, событие="Stop")
        check("второй раз тот же заказ ход не держит", not вых.strip(), вых)

        with tempfile.TemporaryDirectory() as tmp2:
            ухо = Ухо(str(Path(tmp2) / "сессия.sock"))
            try:
                метка(tmp2, sid)
                run(tmp2, sid, ухо.путь, событие="Stop")
                код, вых, ош = run(tmp2, sid, ухо.путь)
                time.sleep(0.6)
                check("придержанная метка всё равно возвращает к работе",
                      len(ухо.строки) == 1, str(ухо.строки))
            finally:
                ухо.закрыть()

        метка(tmp, sid, возраст_сек=90 * 60)
        код, вых, ош = run(tmp, sid, None, событие="Stop")
        check("протухший заказ ход не держит", not вых.strip(), вых)

        метка(tmp, sid)
        код, вых, ош = run(tmp, sid, None, режим="off", событие="Stop")
        check("выключатель действует и на Stop", not вых.strip(), вых)

    print(f"\nвсего: {всего}, провалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    raise SystemExit(main())
