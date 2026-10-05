# -*- coding: utf-8 -*-
"""Статическая проверка проекта: файлы, ссылки между ними и запретное.

Не запускает браузер. Ловит то, что ломается тихо: id, на который ссылается скрипт,
но которого нет в разметке; файл из списка офлайн-кэша, которого нет на диске;
README с устаревшим числом карточек.
"""
import json
import re
import struct
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
JS_FILES = sorted((ROOT / "js").glob("*.js"))
SW = (ROOT / "sw.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
MANIFEST = json.loads((ROOT / "manifest.webmanifest").read_text(encoding="utf-8"))
CARDS = json.loads((ROOT / "cards.json").read_text(encoding="utf-8"))
README = (ROOT / "README.md").read_text(encoding="utf-8")

# наружу уходят только запросы погоды, и только с округлёнными координатами
ALLOWED_HOSTS = {"api.open-meteo.com", "geocoding-api.open-meteo.com", "www.w3.org",
                 "www.b17.ru", "t.me"}


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "%s — не PNG" % path.name
    w, h = struct.unpack(">II", data[16:24])
    return w, h


class Markup(unittest.TestCase):
    def test_ids_unique(self):
        ids = re.findall(r'\sid="([^"]+)"', HTML)
        self.assertEqual([i for i, n in Counter(ids).items() if n > 1], [])

    def test_every_id_the_script_asks_for_exists(self):
        ids = set(re.findall(r'\sid="([^"]+)"', HTML))
        wanted = set(re.findall(r"\$\('([\w-]+)'\)", APP))
        wanted |= set(re.findall(r"getElementById\('([\w-]+)'\)", APP))
        self.assertEqual(sorted(wanted - ids), [])

    def test_every_navigation_target_exists(self):
        screens = set(re.findall(r'data-screen="([\w-]+)"', HTML))
        targets = set(re.findall(r'data-go="([\w-]+)"', HTML))
        # «return» — не экран, а возврат к предыдущему
        self.assertEqual(sorted(targets - screens - {"return"}), [])

    def test_all_screens_present(self):
        screens = set(re.findall(r'data-screen="([\w-]+)"', HTML))
        self.assertEqual(screens, {"intro", "start", "card", "note", "back", "archive", "about"})

    def test_there_is_no_separate_end_screen(self):
        # оборот и конец — один экран
        self.assertNotIn('data-screen="end"', HTML)
        self.assertNotIn("btn-back-next", HTML)
        self.assertNotIn("Дальше</button>\n      </div>\n    </div>\n  </div>\n</section>\n\n<!-- Архив", HTML)

    def test_scripts_and_styles_exist(self):
        refs = re.findall(r'<script src="([^"]+)"', HTML) + re.findall(r'href="([^"]+\.css)"', HTML)
        self.assertGreater(len(refs), 5)
        self.assertEqual([r for r in refs if not (ROOT / r).exists()], [])

    def test_html_basics(self):
        self.assertIn('<html lang="ru"', HTML)
        self.assertIn("viewport-fit=cover", HTML)
        self.assertIn('name="theme-color"', HTML)
        self.assertIn('rel="manifest"', HTML)
        self.assertIn('rel="apple-touch-icon"', HTML)
        self.assertEqual(len(re.findall(r"<h1[\s>]", HTML)), 1)
        self.assertIn('class="skip-link"', HTML)

    def test_screens_are_labelled(self):
        # у каждого экрана есть заголовок или подпись для скринридера
        for m in re.finditer(r'<section class="screen[^"]*" id="([\w-]+)"[^>]*>', HTML):
            tag = m.group(0)
            self.assertTrue("aria-labelledby" in tag or "aria-label" in tag, m.group(1))

    def test_every_button_declares_type(self):
        buttons = re.findall(r"<button\b[^>]*>", HTML)
        self.assertGreater(len(buttons), 20)
        self.assertEqual([b for b in buttons if "type=" not in b], [])

    def test_no_decorative_media(self):
        # ни иллюстраций, ни иконок-украшений, ни прогресса
        for tag in ("<img", "<svg", "<canvas", "<video", "<audio", "<progress", "<meter", "<iframe"):
            self.assertNotIn(tag, HTML, tag)

    def test_external_links_open_safely(self):
        links = re.findall(r'<a\b[^>]*href="https?://[^"]+"[^>]*>', HTML)
        self.assertEqual(len(links), 2)
        for a in links:
            self.assertIn('target="_blank"', a)
            self.assertIn("noopener", a)

    def test_disclaimer_is_verbatim(self):
        text = re.sub(r"\s+", " ", HTML)
        self.assertIn("Это инструмент самопомощи, а не лечение и не замена терапии. "
                      "При паническом расстройстве, ПТСР и выраженной агорафобии "
                      "пользоваться им стоит вместе со специалистом.", text)

    def test_hint_label_renamed_everywhere(self):
        for name, blob in (("html", HTML), ("app", APP), ("css", CSS)):
            self.assertNotIn("Если не пошло", blob, name)
            self.assertIn("Если не получается", HTML)


class Privacy(unittest.TestCase):
    """Нет аналитики, трекеров, чужих шрифтов, уведомлений и регистрации."""

    SOURCES = [("index.html", HTML), ("styles.css", CSS), ("sw.js", SW)] + \
              [(p.name, p.read_text(encoding="utf-8")) for p in JS_FILES]

    def test_only_allowed_hosts(self):
        found = set()
        for _, blob in self.SOURCES:
            found |= set(re.findall(r"https?://([a-z0-9.-]+)", blob))
        self.assertEqual(found - ALLOWED_HOSTS, set())

    def test_no_third_party_scripts_or_fonts(self):
        self.assertEqual(re.findall(r'<script[^>]+src="https?:', HTML), [])
        self.assertNotIn("@import", CSS)
        self.assertNotIn("fonts.googleapis", HTML + CSS)

    def test_no_notifications_or_push(self):
        blob = "\n".join(b for _, b in self.SOURCES)
        for word in ("Notification", "pushManager", "PushManager", "showNotification"):
            self.assertNotIn(word, blob, word)

    def test_no_trackers_or_accounts(self):
        blob = "\n".join(b for _, b in self.SOURCES).lower()
        for word in ("analytics", "gtag", "fbq(", "metrika", "mixpanel", "sentry",
                     "login", "password", "signup", "sessionstorage"):
            self.assertNotIn(word, blob, word)

    def test_storage_is_local_only_and_prefixed(self):
        keys = set()
        for p in JS_FILES:
            src = p.read_text(encoding="utf-8")
            keys |= set(re.findall(r"'(vyiti:[a-z]+)'", src))          # ключ целиком
            prefix = re.search(r"PREFIX = '([^']+)'", src)             # или приставка + имя
            if prefix:
                keys |= {prefix.group(1) + n for n in re.findall(r"PREFIX \+ '([a-z]+)'", src)}
        self.assertEqual(keys, {"vyiti:state", "vyiti:seen", "vyiti:diary", "vyiti:weather"})

    def test_weather_request_rounds_coordinates(self):
        weather = (ROOT / "js" / "weather.js").read_text(encoding="utf-8")
        self.assertIn("round2(lat)", weather)
        self.assertIn("round2(lon)", weather)

    def test_no_engagement_words_in_markup(self):
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", "", HTML, flags=re.S)).lower()
        words = re.split(r"[^a-zа-яё]+", text)
        banned = ["балл", "очк", "достижен", "рейтинг", "streak", "поздрав", "молодец",
                  "уведомл", "напомин", "подписк", "регистрац", "профил", "синхрониз",
                  "аналитик", "прогресс"]
        found = sorted({b for b in banned for w in words if w.startswith(b)})
        self.assertEqual(found, [])

    def test_no_stats_in_the_diary_archive(self):
        # архив — просто список записей с датами, без статистики и сравнений
        for word in ("всего записей", "записей:", "среднее", "график", "по сравнению",
                     "вы писали об этом"):
            self.assertNotIn(word, HTML.lower(), word)
            self.assertNotIn(word, APP.lower(), word)


class Manifest(unittest.TestCase):
    def test_required_keys(self):
        for key in ("name", "short_name", "start_url", "display", "icons", "lang",
                    "background_color", "theme_color"):
            self.assertIn(key, MANIFEST)
        self.assertEqual(MANIFEST["display"], "standalone")
        self.assertEqual(MANIFEST["lang"], "ru")

    def test_colors_match_palette(self):
        self.assertEqual(MANIFEST["background_color"].upper(), "#141C26")
        self.assertEqual(MANIFEST["theme_color"].upper(), "#141C26")

    def test_icons_exist_with_declared_sizes(self):
        for icon in MANIFEST["icons"]:
            path = ROOT / icon["src"]
            self.assertTrue(path.exists(), icon["src"])
            if icon["type"] == "image/png":
                w, h = png_size(path)
                self.assertEqual("%dx%d" % (w, h), icon["sizes"], icon["src"])

    def test_has_192_and_512(self):
        sizes = {i["sizes"] for i in MANIFEST["icons"]}
        self.assertTrue({"192x192", "512x512"} <= sizes)

    def test_apple_touch_icon(self):
        self.assertEqual(png_size(ROOT / "icons" / "apple-touch-icon.png"), (180, 180))

    def test_icons_are_not_blank(self):
        # иконка не должна быть залита одним цветом
        data = (ROOT / "icons" / "icon-512.png").read_bytes()
        self.assertGreater(len(data), 1500)


class ServiceWorker(unittest.TestCase):
    def shell(self):
        body = re.search(r"var SHELL = \[(.*?)\];", SW, re.S).group(1)
        return re.findall(r"'([^']+)'", body)

    def test_cache_name_is_versioned(self):
        self.assertRegex(SW, r"var CACHE = 'vyiti-\d+';")

    def test_every_cached_file_exists(self):
        missing = [f for f in self.shell() if f != "./" and not (ROOT / f).exists()]
        self.assertEqual(missing, [])

    def test_app_shell_is_fully_cached(self):
        shell = set(self.shell())
        needed = {"index.html", "styles.css", "cards.js", "manifest.webmanifest"}
        needed |= {"js/%s" % p.name for p in JS_FILES}
        self.assertEqual(sorted(needed - shell), [])

    def test_tools_and_tests_never_cached(self):
        self.assertIn("/tools/", SW)
        self.assertIn("/tests/", SW)
        self.assertEqual([f for f in self.shell() if f.startswith(("tools/", "tests/"))], [])

    def test_only_same_origin_is_intercepted(self):
        self.assertIn("url.origin !== self.location.origin", SW)


class Docs(unittest.TestCase):
    def test_readme_states_the_real_card_count(self):
        # README с устаревшим числом карточек — частая тихая ошибка
        m = re.search(r"(\d+) карточ", README)
        self.assertIsNotNone(m, "в README не названо число карточек")
        self.assertEqual(int(m.group(1)), len(CARDS))

    def test_source_markdown_is_not_published(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("koloda-svod.md", gitignore)
        self.assertIn("koloda-dopolnenie.md", gitignore)

    def test_github_pages_marker(self):
        self.assertTrue((ROOT / ".nojekyll").exists())


class Styles(unittest.TestCase):
    def test_no_shadows_no_external_images(self):
        # «скругления малые, теней нет»
        self.assertNotRegex(CSS, r"box-shadow:\s*[^;]*\d+px\s+\d+px\s+\d+px")
        self.assertNotRegex(CSS, r"url\(\s*['\"]?https?:")

    def test_both_themes_define_every_token(self):
        light = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S).group(1)
        dark = re.search(r'html\[data-theme="dark"\]\s*\{(.*?)\n\}', CSS, re.S).group(1)
        tokens = ("--bg", "--plate", "--text", "--muted", "--line", "--accent",
                  "--accent-ink", "--on-accent", "--press")
        for t in tokens:
            self.assertIn(t + ":", light, t)
            self.assertIn(t + ":", dark, t)

    def test_palette_from_the_brief(self):
        for hexcolor in ("#141C26", "#FFFFFF", "#EDF1F4", "#D9944A", "#1B2430", "#5A6B7B"):
            self.assertIn(hexcolor, CSS.upper(), hexcolor)

    def test_tap_target_token(self):
        self.assertIn("--tap: 56px", CSS)

    def test_reduced_motion_respected(self):
        self.assertIn("prefers-reduced-motion", CSS)

    def test_hidden_attribute_wins(self):
        self.assertIn("[hidden] { display: none !important; }", CSS)


if __name__ == "__main__":
    unittest.main()
