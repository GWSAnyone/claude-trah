#!/usr/bin/env python3
"""Посредник: пересылает насквозь и пишет запрос в улов.

Настоящий API в тест не зовём — вместо него поднимается свой сервер-эхо. Иначе
проверка стоила бы токенов и падала бы от чужой сети.
"""
import http.client
import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))
ПОСРЕДНИК = os.path.join(ЗДЕСЬ, "relay.py")


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Эхо:
    """Сервер вместо API: отвечает кусками и называет полученные заголовки."""

    def __init__(self) -> None:
        куски = [b"data: one\n\n", b"data: two\n\n"]

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self) -> None:  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                тело = self.rfile.read(n)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("X-Seen-Auth", self.headers.get("Authorization", "-"))
                self.send_header("X-Seen-Len", str(len(тело)))
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for к in куски:
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(к), к))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()

            def log_message(self, *args) -> None:
                pass

        self.port = свободный_порт()
        self._srv = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def __enter__(self) -> "Эхо":
        return self

    def __exit__(self, *exc) -> None:
        self._srv.shutdown()
        self._srv.server_close()


def main() -> int:
    провалов = 0

    def check(имя: str, ок: bool, деталь: str = "") -> None:
        nonlocal провалов
        if not ок:
            провалов += 1
        print(f"{'✓' if ок else '✗'} {имя}" + (f"  — {деталь}" if not ок and деталь else ""))

    with Эхо() as эхо, tempfile.TemporaryDirectory() as tmp:
        улов = os.path.join(tmp, "улов.jsonl")
        порт = свободный_порт()
        процесс = subprocess.Popen(
            [sys.executable, ПОСРЕДНИК, str(порт), улов,
             "--upstream", f"http://127.0.0.1:{эхо.port}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            # Ждём готовности сокета, а не спим наугад: на медленной машине
            # фиксированная пауза даёт мигающий тест.
            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1", порт), 0.1):
                        break
                except OSError:
                    time.sleep(0.1)

            запрос = {"model": "проба", "messages": [{"role": "user", "content": "два"}]}
            c = http.client.HTTPConnection("127.0.0.1", порт, timeout=10)
            c.request("POST", "/v1/messages", body=json.dumps(запрос),
                      headers={"Content-Type": "application/json",
                               # Значение заголовка — только latin-1: HTTP не
                               # даёт положить туда кириллицу, и настоящий
                               # токен её и не содержит.
                               "Authorization": "Bearer token-42"})
            ответ = c.getresponse()
            тело = ответ.read()

            check("ответ апстрима доехал целиком", тело == b"data: one\n\ndata: two\n\n",
                  repr(тело[:60]))
            check("код ответа пересылается", ответ.status == 200, str(ответ.status))
            # Заголовок авторизации идёт насквозь: посредник ничего не
            # подписывает сам и не решает за CLI.
            check("authorization пересылается насквозь",
                  ответ.getheader("X-Seen-Auth") == "Bearer token-42",
                  str(ответ.getheader("X-Seen-Auth")))
            check("длина тела не потерялась",
                  ответ.getheader("X-Seen-Len") == str(len(json.dumps(запрос))),
                  str(ответ.getheader("X-Seen-Len")))
            # Заголовки уровня соединения наружу отдавать нельзя: они описывают
            # ЧУЖОЙ канал, и клиент на них подавится.
            check("длина от апстрима не протекла", ответ.getheader("Content-Length") is None)

            строки = [s for s in open(улов, encoding="utf-8").read().splitlines() if s.strip()]
            check("запрос записан в улов", len(строки) == 1, str(len(строки)))
            if строки:
                запись = json.loads(строки[0])
                check("в улове лежит разобранное тело",
                      запись["body"] == запрос, str(запись)[:120])
                check("в улове лежит путь", запись["path"] == "/v1/messages",
                      str(запись.get("path")))
        finally:
            процесс.terminate()
            процесс.wait(timeout=10)

    print(f"\nпровалов: {провалов}")
    return 1 if провалов else 0


if __name__ == "__main__":
    sys.exit(main())
