#!/usr/bin/env python3
"""Прозрачный посредник: записывает запросы и пропускает их к настоящему API.

Ловушка `sink.py` отвечает отказом — она годится, чтобы посмотреть, ЧТО уехало
в первом запросе, и не стоит ни одного токена. Но подагент запускается уже
после ответа модели, а ловушка ответа не даёт: до промпта подагента ею не
добраться в принципе.

Здесь ответ настоящий, и прогон стоит настоящих токенов. Зато в улове лежат ВСЕ
запросы сессии, включая те, что CLI шлёт от имени подагента, — а это
единственный способ увидеть его системный промпт.

Использование:
    relay.py <порт> <улов.jsonl> [--upstream https://api.anthropic.com]

Потом:
    ANTHROPIC_BASE_URL=http://127.0.0.1:<порт> claude --print '<задача>'
    check-subagent.py <улов.jsonl>

Заголовки идут насквозь, включая `authorization`: посредник ничего не решает за
CLI и ничего не подписывает сам. Тело ответа тоже пересылается как есть, кусками
— поток SSE не собирается в память и не ломается.
"""
import http.client
import http.server
import json
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

# Заголовки уровня соединения: их нельзя пересылать дальше, они описывают
# ЭТОТ канал, а не сообщение. Длину и способ нарезки считаем заново сами.
ПОСОЕДИНЕНИЮ = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "host",
}

замок = threading.Lock()


def сделать_обработчик(улов: Path, upstream: str):
    разбор = urllib.parse.urlparse(upstream)
    хост, порт = разбор.hostname, разбор.port
    защищённо = разбор.scheme == "https"

    class Обработчик(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:
            pass  # иначе каждый запрос печатается в вывод прогона

        def do_POST(self) -> None:  # noqa: N802 — имя задано базовым классом
            длина = int(self.headers.get("Content-Length") or 0)
            тело = self.rfile.read(длина)

            # Пишем ДО пересылки: если апстрим оборвётся, запрос всё равно в
            # улове. Замок нужен — соединений несколько, файл один.
            try:
                разобрано = json.loads(тело)
            except Exception:
                разобрано = None
            if разобрано is not None:
                with замок:
                    with улов.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"path": self.path, "body": разобрано},
                                           ensure_ascii=False) + "\n")

            заголовки = {k: v for k, v in self.headers.items()
                         if k.lower() not in ПОСОЕДИНЕНИЮ}
            заголовки["Host"] = хост
            заголовки["Content-Length"] = str(len(тело))

            Соединение = (http.client.HTTPSConnection if защищённо
                          else http.client.HTTPConnection)
            вверх = Соединение(хост, порт, timeout=600)
            try:
                вверх.request("POST", self.path, body=тело, headers=заголовки)
                ответ = вверх.getresponse()
                self.send_response(ответ.status)
                for k, v in ответ.getheaders():
                    if k.lower() not in ПОСОЕДИНЕНИЮ:
                        self.send_header(k, v)
                # Длина ответа заранее неизвестна: поток SSE идёт кусками.
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    кусок = ответ.read(8192)
                    if not кусок:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(кусок), кусок))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception as e:
                try:
                    self.send_response(502)
                    self.end_headers()
                    self.wfile.write(str(e).encode())
                except Exception:
                    pass
            finally:
                вверх.close()

        do_GET = do_POST

    return Обработчик


class Сервер(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    порт = int(sys.argv[1])
    улов = Path(sys.argv[2])
    upstream = "https://api.anthropic.com"
    if "--upstream" in sys.argv:
        upstream = sys.argv[sys.argv.index("--upstream") + 1]
    улов.parent.mkdir(parents=True, exist_ok=True)
    Сервер(("127.0.0.1", порт), сделать_обработчик(улов, upstream)).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
