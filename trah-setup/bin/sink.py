#!/usr/bin/env python3
"""Ловушка для исходящего запроса: записать тело и не пустить дальше.

Единственный способ увидеть системный блок ровно таким, каким его видит модель —
перехватить запрос. Пересылать его наружу не нужно: нам интересен запрос, а не
ответ, и так проба не стоит ни одного токена. Отвечаем 400, клиент ругнётся и
завершится.

Заголовки не пишем: там OAuth-токен. Пишем только тело.

Использование: sink.py <порт> <куда писать>
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "sink.jsonl")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):        # без шума в stderr
        pass

    def _capture(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else b""
        rec = {"path": self.path, "len": n}
        try:
            rec["body"] = json.loads(body)
        except Exception:
            rec["raw"] = body[:2000].decode("utf-8", "replace")
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        payload = json.dumps({"type": "error", "error": {"type": "invalid_request_error",
                                                         "message": "sink"}}).encode()
        self.send_response(400)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_POST = _capture
    do_GET = _capture


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
