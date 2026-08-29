#!/usr/bin/env python3
"""Тесты чекпоинта вокруг компакции."""
import contextlib
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoint.py")

# Порт 1 привилегированный, на нём никто не слушает: связь рвётся сразу, и
# «службы нет» проверяется без ожидания таймаута.
DEAD = "http://127.0.0.1:1"


def run(mode: str, payload: dict, addr: str = DEAD) -> tuple[int, str, str]:
    """Запуск хука.

    `TZ_ADDR` задаём ВСЕГДА, по умолчанию — в заведомо мёртвый адрес. Иначе
    хук постучится в настоящую службу на 127.0.0.1:8181, которая на этой
    машине обычно жива, и половина проверок стала бы зависеть от того, что
    она сейчас думает о сессии с выдуманным номером.

    `TZ_SELF` вычищаем: решения он больше не принимает, но тесты запускаются
    то из терминала, то из сессии под службой, и оставить в окружении
    признак, от которого мы ушли, значит однажды не заметить возвращения
    к нему.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("TZ_SELF", "TZ_ADDR")}
    env["TZ_ADDR"] = addr
    p = subprocess.run(
        [sys.executable, HOOK, mode],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )
    return p.returncode, p.stdout, p.stderr


@contextlib.contextmanager
def speaking_service(known: set[str]):
    """Служба, признающая своими перечисленные `session_id`.

    Отвечает ровно то, что отвечает `/api/compact-speaks`: чужой номер —
    `speaks: false`, и хук тогда печатает структуру сам.
    """
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            sid = json.loads(body).get("session_id", "")
            out = json.dumps({"speaks": sid in known}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def suffix(session_id: str = "") -> str:
    """Как хук называет свои файлы: хост плюс восемь знаков сессии."""
    host = socket.gethostname()
    return f"{host}-{session_id[:8]}" if session_id else host


def checkpoint_path(cwd: str, session_id: str = "") -> str:
    return os.path.join(cwd, ".claude", f".checkpoint-{suffix(session_id)}")


def pending_path(cwd: str, session_id: str = "") -> str:
    return os.path.join(cwd, ".claude", f".checkpoint-pending-{suffix(session_id)}")


def spec_note_path(cwd: str, session_id: str = "") -> str:
    return os.path.join(cwd, ".claude", f".checkpoint-spec-{suffix(session_id)}")


def write_checkpoint(cwd: str, minutes_ago: float, session_id: str = "t",
                     next_action: str = "дописать replaceWorker") -> None:
    os.makedirs(os.path.join(cwd, ".claude"), exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S",
                          time.localtime(time.time() - minutes_ago * 60))
    with open(checkpoint_path(cwd, session_id), "w", encoding="utf-8") as f:
        json.dump({"plan": "X/docs/plans/p.md", "project": "SyncedProjects",
                   "next": next_action, "at": stamp}, f)


def main() -> int:
    failed = 0

    def check(name: str, ok: bool) -> None:
        nonlocal failed
        failed += not ok
        print(f"  {'✓' if ok else '✗'} {name}")

    tmp = tempfile.mkdtemp()
    try:
        base = {"cwd": tmp, "session_id": "t"}

        # --- guard: без чекпоинта ручная компакция блокируется ---
        code, _, err = run("guard", {**base, "trigger": "manual"})
        check("guard блокирует ручную компакцию без чекпоинта", code == 2 and "no checkpoint" in err)

        # --- guard: авто-компакцию не блокируем никогда ---
        code, _, _ = run("guard", {**base, "trigger": "auto"})
        check("guard пропускает авто-компакцию без чекпоинта", code == 0)

        # --- guard: свежий чекпоинт пропускается ---
        write_checkpoint(tmp, minutes_ago=1)
        code, _, _ = run("guard", {**base, "trigger": "manual"})
        check("guard пропускает при свежем чекпоинте", code == 0)

        # --- указания к пересказу печатаются ровно один раз ---
        #
        # Там, где структуру диктует служба, её хук `PreCompact` складывается
        # с хостовым, а не замещает его. Печатать своё поверх значит прислать
        # модели два одинаковых раздела «## Compact Instructions» в одном
        # промпте сжатия.
        code, out, _ = run("guard", {**base, "trigger": "manual"})
        check("службы не дозваться — guard печатает структуру сам",
              code == 0 and "## Compact Instructions" in out)

        with speaking_service({"t"}) as addr:
            code, out, err = run("guard", {**base, "trigger": "manual"}, addr=addr)
            check("служба диктует сама — guard молчит", code == 0 and out == "")

            # Опасная сторона развилки не должна быть бесшумной: потерянную
            # структуру надо находить по следу, а не по догадке «пересказ
            # что-то выглядит стандартным».
            check("о молчании сказано в stderr",
                  "структуру пересказа диктует служба" in err)
            check("молчание записано рядом с чекпоинтом",
                  os.path.exists(spec_note_path(tmp, "t")))

            # Признак не должен наследоваться: сессия, поднятая ИЗНУТРИ нашей
            # (`cmd/launch`, терминал, вызов из инструмента), носит то же
            # окружение, но службе неизвестна — и диктовать ей некому.
            write_checkpoint(tmp, 1, "zzzzzzzz")
            code, out, _ = run("guard", {"cwd": tmp, "session_id": "zzzzzzzz",
                                         "trigger": "manual"}, addr=addr)
            check("сессию, которой служба не знает, guard не бросает молча",
                  code == 0 and "## Compact Instructions" in out)

            # Молчание не должно стоить сторожа: под службой он тут
            # единственный — свой она намеренно не включает там, где стоит
            # хостовый.
            os.remove(checkpoint_path(tmp, "t"))
            code, out, err = run("guard", {**base, "trigger": "manual"}, addr=addr)
            check("под говорящей службой guard всё ещё блокирует без чекпоинта",
                  code == 2 and "no checkpoint" in err and out == "")
            write_checkpoint(tmp, minutes_ago=1)

            # Заметку кладём заново: прошлый `guard` отбился сторожем и до неё
            # не дошёл, а следующая проверка про архив ждёт её на месте.
            run("guard", {**base, "trigger": "manual"}, addr=addr)

        # --- guard: устаревший блокируется ---
        write_checkpoint(tmp, minutes_ago=45)
        code, _, err = run("guard", {**base, "trigger": "manual"})
        check("guard блокирует при чекпоинте старше 30 мин", code == 2 and "stale" in err)

        # --- guard: метка из БУДУЩЕГО тоже блокируется ---
        # 29.08.2026 в чекпоинте лежала дата на сутки вперёд: возраст выходил
        # отрицательным, «старше получаса» не срабатывало никогда, и сторож
        # пропускал любое сжатие. Проверка была включена и не работала.
        write_checkpoint(tmp, minutes_ago=-26 * 60)
        code, _, err = run("guard", {**base, "trigger": "manual"})
        check("guard блокирует при метке из будущего",
              code == 2 and "FUTURE" in err)

        # --- mark: ставит метку и сохраняет пересказ ---
        write_checkpoint(tmp, minutes_ago=1)
        code, _, _ = run("mark", {**base, "trigger": "manual",
                                  "compact_summary": "тестовый пересказ"})
        pending = pending_path(tmp, "t")
        saved = os.path.join(tmp, ".claude", "compact-summaries")
        check("mark ставит метку", code == 0 and os.path.exists(pending))
        check("mark сохраняет пересказ", os.path.isdir(saved) and len(os.listdir(saved)) == 1)

        # Кто диктовал структуру — в заголовке архива. Ради этого заметку и
        # пишет `guard`: пересказ, вышедший стандартным оттого, что смолчали
        # оба, иначе не отличить от пересказа, которому просто не последовали.
        with open(os.path.join(saved, os.listdir(saved)[0]), encoding="utf-8") as f:
            head = f.read()
        check("архив называет, кто диктовал структуру", "Структуру диктовал: служба" in head)
        check("заметка одноразовая: mark её убрал",
              not os.path.exists(spec_note_path(tmp, "t")))

        # --- restore: отдаёт указатель и снимает метку ---
        code, out, _ = run("restore", base)
        # Проверяем ДВЕ вещи: что вернулось содержимое указателя и что вернулась
        # памятка о восстановлении. Раньше вторая половина проверялась по строке
        # `mem:core` — имени памяти конкретной экосистемы. Утверждение держало
        # текст хука привязанным к одной раскладке: на чужой машине такой памяти
        # нет, а тест всё равно требовал её упоминания. Проверяем действие
        # (`list_memories`), а не имя.
        # Указатель — ради `next`; вторая половина проверки про то, КАК читать
        # план. Текст подрезан 27.08: инструкции про активацию проекта и про
        # вложенные CLAUDE.md убраны (под trah Серена поднимается с `--project`,
        # активировать нечем), осталось поточечное чтение записи.
        check("restore отдаёт указатель",
              "дописать replaceWorker" in out and "Где я сейчас" in out)
        check("restore снимает метку", not os.path.exists(pending))

        # --- restore: без метки молчит ---
        code, out, _ = run("restore", base)
        check("restore молчит без метки", code == 0 and out == "")

        # --- restore: метка есть, указателя нет ---
        with open(pending, "w") as f:
            f.write("manual")
        os.remove(checkpoint_path(tmp, "t"))
        code, out, _ = run("restore", base)
        check("restore честно сообщает об отсутствии указателя", "There is no pointer" in out)

        # --- битый JSON на входе не роняет хук ---
        p = subprocess.run([sys.executable, HOOK, "guard"], input="не json",
                           capture_output=True, text=True)
        check("битый вход не роняет хук", p.returncode == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- две сессии на одной машине: ради этого имена и подписаны сессией ---
    tmp2 = tempfile.mkdtemp()
    try:
        first = {"cwd": tmp2, "session_id": "aaaaaaaa"}
        second = {"cwd": tmp2, "session_id": "bbbbbbbb"}

        write_checkpoint(tmp2, 1, "aaaaaaaa", next_action="работа первой сессии")
        code, _, _ = run("guard", {**first, "trigger": "manual"})
        check("первая сессия: свой чекпоинт разрешает компакцию", code == 0)

        # У второй чекпоинта нет — и чужой её пропускать не должен: иначе
        # компакция сотрёт состояние, которого никто не записывал.
        code, _, err = run("guard", {**second, "trigger": "manual"})
        check("вторая сессия: чужой чекпоинт не считается своим",
              code == 2 and "no checkpoint" in err)

        write_checkpoint(tmp2, 1, "bbbbbbbb", next_action="работа второй сессии")
        code, _, _ = run("guard", {**second, "trigger": "manual"})
        check("вторая сессия: свой чекпоинт разрешает компакцию", code == 0)

        # И первая при этом не потеряла своё состояние.
        with open(checkpoint_path(tmp2, "aaaaaaaa"), encoding="utf-8") as f:
            saved = json.load(f)
        check("чекпоинт первой сессии не затёрт", saved["next"] == "работа первой сессии")

        # Метка восстановления тоже своя у каждой.
        run("mark", {**first, "trigger": "manual"})
        check("метка первой сессии не видна второй",
              os.path.exists(pending_path(tmp2, "aaaaaaaa"))
              and not os.path.exists(pending_path(tmp2, "bbbbbbbb")))
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

    print(f"\nвсего: 24   провалов: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
