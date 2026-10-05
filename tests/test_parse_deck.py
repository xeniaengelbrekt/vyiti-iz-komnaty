# -*- coding: utf-8 -*-
"""Сборщик колоды на вымышленных примерах.

Исходные markdown-файлы с настоящими карточками в репозитории не лежат, поэтому
разбор проверяется на tests/fixtures: по одной карточке каждой формы.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSER = ROOT / "tools" / "parse_deck.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run_parser(source):
    """Запускает сборщик и возвращает (код выхода, вывод, карточки по id)."""
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "cards.json"
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run(
            [sys.executable, str(PARSER), str(source), "-o", str(dst)],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(ROOT))
        cards = {}
        js = ""
        if dst.exists():
            cards = {c["id"]: c for c in json.loads(dst.read_text(encoding="utf-8"))}
            js = (Path(tmp) / "cards.js").read_text(encoding="utf-8")
        return proc.returncode, proc.stdout, cards, js


class ParseGoodFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.out, cls.cards, cls.js = run_parser(FIXTURES / "mini.md")

    def test_clean_parse_exits_zero(self):
        self.assertEqual(self.code, 0, self.out)
        self.assertIn("проблем: 0", self.out)

    def test_all_seven_cards_found(self):
        self.assertEqual(len(self.cards), 7, sorted(self.cards))

    def test_modes_by_prefix(self):
        modes = {i: c["mode"] for i, c in self.cards.items()}
        self.assertEqual(modes["НАР-01"], "наружу")
        self.assertEqual(modes["ЧМ-01"], "читать-место")
        self.assertEqual(modes["СПб-01"], "читать-место")
        self.assertEqual(modes["СВ-01"], "совместное-внимание")
        self.assertEqual(modes["ПД-08а"], "полевой-дневник")

    def test_block_format_fields(self):
        c = self.cards["НАР-01"]
        self.assertEqual(c["level"], 2)
        self.assertEqual(c["modality"], "кросс")
        self.assertEqual(c["light"], ["сумерки"])
        self.assertEqual(c["weather"], ["сухо"])
        self.assertEqual(c["criterion"], "два пятна")
        self.assertEqual(c["text"], "Найдите красное пятно и синее. Что из них ярче?")
        self.assertEqual(c["back"], "Объяснение первой пробы.")

    def test_weather_exclusion_tag(self):
        self.assertEqual(self.cards["НАР-01"]["weatherNot"], ["ясно"])
        self.assertEqual(self.cards["ЧМ-01"]["weatherNot"], [])

    def test_read_place_fields(self):
        c = self.cards["ЧМ-01"]
        self.assertEqual(c["level"], 3)
        self.assertEqual(c["layer"], "починка")
        self.assertEqual(c["light"], ["день", "низкое-солнце"])

    def test_city_pack_and_building(self):
        c = self.cards["СПб-01"]
        self.assertEqual(c["cityPack"], "спб")
        self.assertEqual(c["buildingType"], "исторический-центр")
        self.assertIsNone(self.cards["ЧМ-01"]["cityPack"])

    def test_inline_format_text_and_back(self):
        c = self.cards["СВ-01"]
        self.assertEqual(c["text"], "Покажите ребёнку что-то красное.")
        self.assertEqual(c["back"], "Объяснение четвёртой пробы.")

    def test_age_comes_from_section_heading(self):
        self.assertEqual(self.cards["СВ-01"]["age"], "2-3")
        self.assertEqual(self.cards["СВ-45"]["age"], "со-взрослым")
        self.assertIsNone(self.cards["НАР-01"]["age"])

    def test_hint_label_is_the_new_one(self):
        self.assertEqual(self.cards["СВ-01"]["fallback"], "назовите предмет сами.")

    def test_adult_tier_has_no_hint(self):
        self.assertIsNone(self.cards["СВ-45"]["fallback"])

    def test_split_diary_card_conditions(self):
        a, b = self.cards["ПД-08а"], self.cards["ПД-08б"]
        self.assertTrue(a["noHistory"] and not a["needsHistory"])
        self.assertTrue(b["needsHistory"] and not b["noHistory"])

    def test_diary_entry_type(self):
        self.assertEqual(self.cards["ПД-08а"]["entryType"], "свободная")

    def test_js_file_matches_json(self):
        self.assertTrue(self.js.startswith("/* Сгенерировано"))
        body = self.js.split("window.KOLODA = ", 1)[1].rstrip().rstrip(";")
        self.assertEqual({c["id"] for c in json.loads(body)}, set(self.cards))


class ParseBadFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.out, cls.cards, cls.js = run_parser(FIXTURES / "bad.md")

    def test_problems_give_nonzero_exit(self):
        self.assertEqual(self.code, 1, self.out)

    def test_missing_back_is_reported(self):
        self.assertIn("пустой оборот", self.out)

    def test_missing_light_is_reported(self):
        self.assertIn("нет тега света", self.out)

    def test_duplicate_id_is_reported(self):
        self.assertIn("дубликаты id", self.out)


if __name__ == "__main__":
    unittest.main()
