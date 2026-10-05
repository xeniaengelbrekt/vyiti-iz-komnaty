# -*- coding: utf-8 -*-
"""Единый запуск всех автотестов.

    python tests/run_tests.py            все наборы
    python tests/run_tests.py --python   только Python
    python tests/run_tests.py --browser  только браузерные
    python tests/run_tests.py -v         подробно, со всеми строками

Что запускается:
  1. Python (unittest): сборщик колоды, целостность и редполитика, статика проекта.
  2. Браузер, tools/proverka.html: свет, погода, правила выдачи, размеры, контрасты.
  3. Браузер, tests/e2e.html: сценарии «как человек» в кадре размером с телефон.

Браузер нужен любой на Chromium: Edge или Chrome. Ничего устанавливать не надо.
Свой можно указать переменной BROWSER. Код выхода 0 — всё сходится, 1 — есть провалы.
"""
import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BROWSER_PAGES = [
    ("Проверка сборки (свет, погода, выдача, размеры, контрасты)", "/tools/proverka.html"),
    ("Сквозные сценарии (как человек)", "/tests/e2e.html"),
]

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser():
    if os.environ.get("BROWSER") and Path(os.environ["BROWSER"]).exists():
        return os.environ["BROWSER"]
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({".webmanifest": "application/manifest+json", ".js": "text/javascript",
                           ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json"})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, *args):
        pass


def start_server():
    class Server(http.server.ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

        def handle_error(self, request, client_address):
            pass        # браузер сам обрывает соединения: это не ошибка проекта

    httpd = Server(("127.0.0.1", 0), NoCacheHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


# ——— Python ———

def run_python(verbose):
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")
    stream = sys.stdout if verbose else open(os.devnull, "w", encoding="utf-8")
    result = unittest.TextTestRunner(stream=stream, verbosity=2 if verbose else 0).run(suite)
    failures = []
    for test, tb in result.failures + result.errors:
        last = tb.strip().splitlines()[-1] if tb.strip() else ""
        failures.append((str(test), last))
    return {"title": "Python: колода, сборщик, статика проекта",
            "passed": result.testsRun - len(result.failures) - len(result.errors),
            "failed": len(result.failures) + len(result.errors),
            "warned": 0, "failures": failures, "warnings": []}


# ——— браузер ———

def run_page(browser, port, title, path, verbose):
    profile = tempfile.mkdtemp(prefix="vyiti-test-")
    url = "http://127.0.0.1:%d%s" % (port, path)
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--disable-component-update",
           "--disable-background-networking", "--user-data-dir=" + profile,
           "--window-size=1280,1000", "--virtual-time-budget=900000",
           "--enable-logging=stderr", "--v=0", "--dump-dom", url]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=420)
    except subprocess.TimeoutExpired:
        return {"title": title, "passed": 0, "failed": 1, "warned": 0,
                "failures": [(path, "браузер не уложился в 7 минут")], "warnings": []}
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    dom = proc.stdout.decode("utf-8", "replace")
    m = re.search(r'<script type="application/json" id="result">(.*?)</script>', dom, re.S)
    if not m:
        errors = [l for l in proc.stderr.decode("utf-8", "replace").splitlines()
                  if "CONSOLE" in l or "ERROR" in l][:6]
        return {"title": title, "passed": 0, "failed": 1, "warned": 0,
                "failures": [(path, "страница не выдала результат. " + " | ".join(errors))],
                "warnings": []}

    data = json.loads(m.group(1))
    data["title"] = title
    data["failures"] = [("%s — %s" % (r["section"], r["name"]), r["detail"])
                        for r in data["rows"] if r["status"] == "fail"]
    data["warnings"] = [("%s — %s" % (r["section"], r["name"]), r["detail"])
                        for r in data["rows"] if r["status"] == "warn"]
    data["seconds"] = round(time.time() - started, 1)
    if verbose:
        sec = None
        for r in data["rows"]:
            if r["section"] != sec:
                sec = r["section"]
                print("\n  %s" % sec)
            mark = {"pass": "✓", "fail": "✗", "warn": "!", "info": "·"}[r["status"]]
            print("    %s %s%s" % (mark, r["name"],
                                   "" if r["status"] in ("pass", "info") else " — " + r["detail"]))
    return data


# ——— вывод ———

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", action="store_true", help="только Python")
    ap.add_argument("--browser", action="store_true", help="только браузерные")
    ap.add_argument("-v", "--verbose", action="store_true", help="показать каждую проверку")
    args = ap.parse_args()
    want_py = args.python or not args.browser
    want_br = args.browser or not args.python

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    suites = []
    if want_py:
        suites.append(run_python(args.verbose))

    if want_br:
        browser = find_browser()
        if not browser:
            print("Браузер на Chromium не найден: нужен Edge или Chrome (или переменная BROWSER).")
            return 2
        httpd, port = start_server()
        try:
            for title, path in BROWSER_PAGES:
                print("запускаю: %s …" % title, flush=True)
                suites.append(run_page(browser, port, title, path, args.verbose))
        finally:
            httpd.shutdown()

    total_pass = sum(s["passed"] for s in suites)
    total_fail = sum(s["failed"] for s in suites)
    total_warn = sum(s["warned"] for s in suites)

    print("\n" + "═" * 64)
    for s in suites:
        flag = "✓" if s["failed"] == 0 else "✗"
        extra = ", известных пробелов: %d" % s["warned"] if s["warned"] else ""
        secs = ", %s с" % s["seconds"] if s.get("seconds") else ""
        print("%s %-58s %d проверок%s%s" % (flag, s["title"], s["passed"] + s["failed"] + s["warned"], extra, secs))
        if s["failed"]:
            print("    не сошлось: %d" % s["failed"])
    print("═" * 64)

    for s in suites:
        for name, detail in s["failures"]:
            print("✗ %s\n    %s" % (name, detail))
    for s in suites:
        for name, detail in s["warnings"]:
            print("! %s\n    %s" % (name, detail))

    print("\nИтого: %d прошло, %d не прошло, %d известных пробелов." % (total_pass, total_fail, total_warn))
    print("ВСЁ СХОДИТСЯ." if total_fail == 0 else "ЕСТЬ ПРОВАЛЫ.")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
