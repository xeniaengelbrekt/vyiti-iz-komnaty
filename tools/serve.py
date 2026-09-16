# -*- coding: utf-8 -*-
"""Статический сервер для местной проверки.

Отличается от `python -m http.server` одним: ничего не кэширует. Иначе браузер
показывает вчерашний CSS и полдня уходит на выяснение, почему правка не видна.

Запуск:  python tools/serve.py [порт]
"""
import http.server
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8123


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({
        ".webmanifest": "application/manifest+json",
        ".json": "application/json",
        ".svg": "image/svg+xml",
        ".js": "text/javascript",
        ".css": "text/css",
        ".md": "text/markdown; charset=utf-8",
    })

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        http.server.SimpleHTTPRequestHandler.end_headers(self)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))


# многопоточный: одного зависшего соединения хватает, чтобы однопоточный встал
class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


with Server(("127.0.0.1", PORT), Handler) as httpd:
    sys.stderr.write("http://localhost:%d\n" % PORT)
    httpd.serve_forever()
