# -*- coding: utf-8 -*-
"""Колода как данные: целостность, словари, редполитика, покрытие.

Тесты читают собранные cards.json и cards.js, поэтому исходные markdown-файлы
не нужны и в репозитории их нет.
"""
import json
import re
import unittest
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = json.loads((ROOT / "cards.json").read_text(encoding="utf-8"))

MODES = {"наружу", "читать-место", "совместное-внимание", "с-собакой", "полевой-дневник"}
AGES = ["2-3", "4-5", "6-8", "9-12", "со-взрослым"]
LIGHT = {"день", "низкое-солнце", "сумерки", "темнота", "неважно"}
SEASONS = {"любой", "зима", "весна", "лето", "осень"}
WEATHER = {"ясно", "облачно", "сухо", "дождь", "снег", "после-дождя", "мороз",
           "оттепель", "свежий-снег", "наст", "ветер", "туман", "неважно"}
MODALITY = {"зрение", "слух", "обоняние", "температура", "кросс", None}
ENVIRONMENTS = {"город", "природа", "везде"}
ENVS = ("город", "природа")      # то, что выбирает человек

# слова, по которым видно, что карточке нужна застройка
URBAN = re.compile(
    r"здани|фасад|подъезд|двор|арк[аиуе]\b|арку|асфальт|машин|вывеск|крыш|кладк|улиц|тротуар|"
    r"балкон|гараж|витрин|кирпич|проём|штукатур|бордюр|подвал|цоколь|лестниц|квартал|"
    r"табличк|провод|фонар|окн[аоуе]|окон|\bдом[аеу]?\b|\bдомов|\bдомом\b|стен[аыуе]\b|стену|"
    r"столб|магазин|светофор|перекр[её]ст|этаж|капот|шлагбаум|забор|вентиляц|люк[аиоуе]?\b",
    re.IGNORECASE)

# «везде»-карточки, в которых такие слова встречаются, но застройка не нужна:
# разобраны вручную, по одной
URBAN_WORD_BUT_ANYWHERE = {
    "НАР-12": "три отражения: не в зеркале и не в витрине — подойдёт лужа",
    "НАР-26": "«проверить можно дома» — это не здание",
    "НАР-56": "ветки, вода, люди, машины — хватит веток и воды",
    "СВ-08": "окна, машины, камешки, ступени — подойдут камешки",
    "СВ-64": "светлое пятно на земле или на стене",
}

# Меньше стольких карточек в любом сочетании «ступень × свет × сезон» — провал.
# Три — это минимум, при котором семидневное правило не сводит выдачу к одной и той же.
MIN_POOL = 3


def of(mode):
    return [c for c in CARDS if c["mode"] == mode]


def groups():
    """Все «ступени»: режим и то, чем он делится для пользователя."""
    out = {}
    for lvl in (1, 2, 3):
        out[("наружу", lvl)] = [c for c in of("наружу") if c["level"] == lvl]
    for age in AGES:
        out[("совместное-внимание", age)] = [c for c in of("совместное-внимание") if c["age"] == age]
    for mode in ("читать-место", "с-собакой", "полевой-дневник"):
        out[(mode, None)] = of(mode)
    return out


def fits(card, light, season):
    """Подходит ли карточка по свету и сезону — как в js/deck.js, без погоды."""
    light_ok = "неважно" in card["light"] or light in card["light"]
    season_ok = "любой" in card["seasons"] or season in card["seasons"]
    return light_ok and season_ok


def env_fits(card, env):
    return env is None or card["environment"] in ("везде", env)


def pool(key, light, season, city=None, env="город"):
    out = []
    for c in groups()[key]:
        if c.get("cityPack") and c["cityPack"] != city:
            continue
        if env_fits(c, env) and fits(c, light, season):
            out.append(c)
    return out


class Integrity(unittest.TestCase):
    def test_not_empty(self):
        self.assertGreater(len(CARDS), 100)

    def test_ids_unique(self):
        dup = [i for i, n in Counter(c["id"] for c in CARDS).items() if n > 1]
        self.assertEqual(dup, [])

    def test_titles_unique_within_mode(self):
        seen = Counter((c["mode"], c["title"]) for c in CARDS)
        self.assertEqual([k for k, n in seen.items() if n > 1], [])

    def test_required_fields(self):
        bad = [c["id"] for c in CARDS
               if not all(c.get(f) for f in ("id", "mode", "title", "text", "back", "light",
                                             "seasons", "weather"))]
        self.assertEqual(bad, [])

    def test_modes_known(self):
        self.assertEqual({c["mode"] for c in CARDS} - MODES, set())

    def test_every_mode_present(self):
        self.assertEqual({c["mode"] for c in CARDS}, MODES)

    def test_vocabularies(self):
        errors = []
        for c in CARDS:
            for v in c["light"]:
                if v not in LIGHT:
                    errors.append((c["id"], "свет", v))
            for v in c["seasons"]:
                if v not in SEASONS:
                    errors.append((c["id"], "сезон", v))
            for v in c["weather"] + c.get("weatherNot", []):
                if v not in WEATHER:
                    errors.append((c["id"], "погода", v))
            if c["modality"] not in MODALITY:
                errors.append((c["id"], "модальность", c["modality"]))
        self.assertEqual(errors, [])

    def test_environment_values_known(self):
        self.assertEqual({c["environment"] for c in CARDS} - ENVIRONMENTS, set())

    def test_every_environment_is_used(self):
        self.assertEqual({c["environment"] for c in CARDS}, ENVIRONMENTS)

    def test_city_pack_cards_need_a_city(self):
        self.assertEqual([c["id"] for c in CARDS
                          if c["cityPack"] and c["environment"] != "город"], [])

    def test_level_only_where_it_belongs(self):
        for c in of("наружу"):
            self.assertIn(c["level"], (1, 2, 3), c["id"])
        for c in of("совместное-внимание"):
            self.assertIn(c["age"], AGES, c["id"])

    def test_age_only_in_joint_attention(self):
        self.assertEqual([c["id"] for c in CARDS
                          if c["mode"] != "совместное-внимание" and c["age"]], [])

    def test_city_packs_known(self):
        self.assertEqual({c["cityPack"] for c in CARDS} - {None, "спб", "мск"}, set())

    def test_city_pack_cards_are_read_place(self):
        self.assertEqual([c["id"] for c in CARDS
                          if c["cityPack"] and c["mode"] != "читать-место"], [])

    def test_history_flags_not_contradictory(self):
        self.assertEqual([c["id"] for c in CARDS if c["needsHistory"] and c["noHistory"]], [])

    def test_split_diary_card_pair(self):
        by_id = {c["id"]: c for c in CARDS}
        self.assertIn("ПД-08а", by_id)
        self.assertIn("ПД-08б", by_id)
        self.assertNotIn("ПД-08", by_id)
        self.assertTrue(by_id["ПД-08а"]["noHistory"])
        self.assertTrue(by_id["ПД-08б"]["needsHistory"])

    def test_weather_exclusion_on_metal_and_wood(self):
        nar18 = next(c for c in CARDS if c["id"] == "НАР-18")
        self.assertEqual(nar18["weatherNot"], ["ясно"])
        self.assertIn("в тени", nar18["text"])

    def test_js_and_json_hold_the_same_deck(self):
        js = (ROOT / "cards.js").read_text(encoding="utf-8")
        body = js.split("window.KOLODA = ", 1)[1].rstrip().rstrip(";")
        self.assertEqual(json.loads(body), CARDS)


class Typography(unittest.TestCase):
    def test_text_ends_like_a_sentence(self):
        bad = [c["id"] for c in CARDS if c["text"][-1] not in ".?!…»)"]
        self.assertEqual(bad, [])

    def test_no_stray_whitespace(self):
        bad = []
        for c in CARDS:
            for f in ("title", "text", "back"):
                v = c[f]
                if v != v.strip() or "  " in v or "\n" in v:
                    bad.append((c["id"], f))
        self.assertEqual(bad, [])

    def test_no_straight_quotes(self):
        bad = [(c["id"], f) for c in CARDS for f in ("title", "text", "back") if '"' in c[f]]
        self.assertEqual(bad, [])

    def test_old_hint_label_is_gone(self):
        blob = json.dumps(CARDS, ensure_ascii=False)
        self.assertNotIn("Если не пошло", blob)
        self.assertNotIn("если не пошло", blob)


class Policy(unittest.TestCase):
    """Редполитика свода, части II. Проверяется по самим текстам."""

    def hits(self, pattern, fields=("text",), cards=None):
        rx = re.compile(pattern, re.IGNORECASE)
        return [(c["id"], f) for c in (cards if cards is not None else CARDS)
                for f in fields if rx.search(c[f] or "")]

    def test_no_promises_about_state(self):
        # правило 1: ни одна карта не обещает, что станет спокойнее, легче или интереснее
        self.assertEqual(self.hits(
            r"станет (спокойн|легче|лучше|интересн)|успоко[ий]|расслабит|расслабьтесь|расслабиться|снизит тревог|"
            r"избавит|перезагруз|поможет (справиться|расслабиться)", ("text", "back")), [])

    def test_never_says_distract(self):
        # правило 2: «отвлекитесь» — инструкция на избегание
        self.assertEqual(self.hits(r"отвлек|отвлеч|отвлёк", ("text",)), [])

    def test_prediction_about_the_world_not_about_oneself(self):
        # правило 5: угадать длину тени можно, угадать свою реакцию нельзя
        self.assertEqual(self.hits(
            r"предскажите,? (как|что) (вы|вам)|как вы (отреагируете|будете себя)|"
            r"что вы (почувствуете|ощутите)"), [])

    def test_criterion_does_not_depend_on_wellbeing(self):
        # правило 4
        bad = [c["id"] for c in CARDS
               if re.search(r"спокойн|легче|приятн|удовольств|получилось расслабиться",
                            c.get("criterion") or "", re.I)]
        self.assertEqual(bad, [])

    def test_no_strangers_anywhere(self):
        self.assertEqual(self.hits(
            r"незнаком|прохожи|спросите у|обратитесь к|подойдите к (человек|мужчин|женщин|продавц)"), [])

    def test_headphones_formula_is_exact(self):
        # наушники не отбираются: разрешение вернуть их напечатано на карте
        starts = [c for c in CARDS if "наушник" in c["text"]]
        self.assertGreaterEqual(len(starts), 6)
        bad = []
        for c in starts:
            t = c["text"]
            if not t.startswith("Снимите наушники на две минуты."):
                bad.append((c["id"], "зачин"))
            if not t.endswith("После этого наушники можно вернуть."):
                bad.append((c["id"], "концовка"))
        self.assertEqual(bad, [])

    def test_outside_mode_has_no_interoception(self):
        # «Наружу»: интероцепция исключена целиком
        self.assertEqual(self.hits(
            r"дыхани|пульс|сердцебиени|сердце|в груди|в животе|в теле|напряжени[ея] в",
            ("text",), of("наружу")), [])

    def test_outside_mode_sends_nowhere(self):
        self.assertEqual(self.hits(
            r"отправляйтесь|поезжайте|съездите|дойдите до|идите (в|на|к) ",
            ("text",), of("наружу")), [])

    def test_joint_attention_is_safe(self):
        self.assertEqual(self.hits(
            r"перейд(ите|и) (через )?(дорог|проезж)|отойд(ите|и) от ребёнк|отправьте ребёнка|"
            r"ребёнок (сам )?(один|пойдёт)", ("text",), of("совместное-внимание")), [])

    def test_dog_is_not_a_tool(self):
        self.assertEqual(self.hits(
            r"отпустите (с )?поводк|спустите с поводк|уведите|задержите",
            ("text",), of("с-собакой")), [])

    def test_diary_has_no_banned_verbs(self):
        # «Полевой дневник»: запрещены «почувствовали», «вспомнилось» и оценочные задания
        self.assertEqual(self.hits(
            r"почувствовал|вспомнил|напомнил|о чём подумали|как вы себя",
            ("text",), of("полевой-дневник")), [])

    def test_diary_never_suggests_rereading(self):
        self.assertEqual(self.hits(
            r"перечитайте|прошлые записи|старые записи|сравните с (прошл|собой)",
            ("text", "back"), of("полевой-дневник")), [])

    def test_every_child_card_has_a_hint_except_adult(self):
        joint = of("совместное-внимание")
        no_hint = [c["id"] for c in joint if c["age"] != "со-взрослым" and not c.get("fallback")]
        self.assertEqual(no_hint, [])

    def test_adult_tier_has_no_hint(self):
        # «если не получается» — только для родителя с маленьким ребёнком
        self.assertEqual([c["id"] for c in CARDS
                          if c["age"] == "со-взрослым" and c.get("fallback")], [])

    def test_hints_do_not_say_distract(self):
        self.assertEqual([c["id"] for c in CARDS
                          if re.search(r"отвлеч|отвлек", c.get("fallback") or "", re.I)], [])


class Environment(unittest.TestCase):
    """Выбор среды «двор или город» / «парк или лес»."""

    def nature(self):
        return [c for c in CARDS if c["environment"] == "природа"]

    def test_nature_cards_exist_in_every_mode_that_needs_them(self):
        modes = {c["mode"] for c in self.nature()}
        self.assertTrue({"наружу", "читать-место", "совместное-внимание", "с-собакой"} <= modes, modes)

    def test_nature_cards_never_mention_buildings(self):
        bad = [c["id"] for c in self.nature() if URBAN.search(c["text"] + " " + c["title"])]
        self.assertEqual(bad, [])

    def test_anywhere_cards_do_not_need_buildings(self):
        # если в тексте «везде»-карточки появилось слово про застройку — либо ей нужна
        # среда «город», либо исключение надо разобрать и записать в URBAN_WORD_BUT_ANYWHERE
        bad = [c["id"] for c in CARDS
               if c["environment"] == "везде" and URBAN.search(c["text"] + " " + c["title"])
               and c["id"] not in URBAN_WORD_BUT_ANYWHERE]
        self.assertEqual(bad, [])

    def test_exceptions_are_still_exceptions(self):
        # исключение, которое больше не нужно, надо убрать: список не должен копить мусор
        by_id = {c["id"]: c for c in CARDS}
        stale = [i for i in URBAN_WORD_BUT_ANYWHERE
                 if i not in by_id or by_id[i]["environment"] != "везде"
                 or not URBAN.search(by_id[i]["text"] + " " + by_id[i]["title"])]
        self.assertEqual(stale, [])

    def test_city_cards_mention_buildings_or_were_checked_by_hand(self):
        # городская карточка без единого «городского» слова — повод перечитать,
        # нужна ли ей застройка. Эти разобраны вручную.
        hand_checked = {"НАР-07", "НАР-17", "НАР-18", "НАР-25", "НАР-27", "НАР-50", "НАР-54",
                        "НАР-68", "ЧМ-06", "ЧМ-18", "ЧМ-23", "ЧМ-26", "ПД-09", "СВ-21", "СВ-26",
                        "СВ-35", "СВ-40", "СВ-44"}
        bad = [c["id"] for c in CARDS
               if c["environment"] == "город" and not URBAN.search(c["text"] + " " + c["title"])
               and c["id"] not in hand_checked]
        self.assertEqual(bad, [])

    def test_nature_cards_are_safe(self):
        # ничего не трогать и не пробовать, не сходить с тропы, не подходить к воде
        # и льду, не лезть на деревья: проект никуда не отправляет и ничем не рискует
        rx = re.compile(
            r"на вкус|съешьте|попробуйте (на|съесть)|сорвите|ягод|гриб|залезьте|заберитесь|"
            r"сойдите с тропы|сверните с тропы|по льду|у воды|у берега|к воде|"
            r"прыгните|костёр|разведите", re.IGNORECASE)
        bad = [(c["id"], m.group(0)) for c in CARDS
               for m in [rx.search(c["text"])] if m]
        self.assertEqual(bad, [])

    def test_dusk_and_night_nature_cards_are_done_standing_still(self):
        # в сумерках и в тёмном лесу не предлагаем ходить: такие карточки природы
        # выполняются на месте, и это сказано в самом тексте
        # «свет: неважно» тоже значит сумерки и темнота: такая карточка выпадает и в них
        rx = re.compile(r"не сходя с места|стоите|над головой", re.IGNORECASE)
        dusk_or_dark = ("темнота", "сумерки", "неважно")
        bad = [c["id"] for c in self.nature()
               if any(l in c["light"] for l in dusk_or_dark) and not rx.search(c["text"])
               and c["mode"] != "с-собакой"]
        self.assertEqual(bad, [])

    def test_dog_cards_in_the_park_are_daytime_only(self):
        # с собакой человек всё равно идёт, но тёмный лес карточкой не украшаем
        bad = [c["id"] for c in self.nature() if c["mode"] == "с-собакой"
               and any(l in c["light"] for l in ("темнота", "сумерки", "неважно"))]
        self.assertEqual(bad, [])

    def test_dusk_and_night_nature_cards_do_not_ask_to_walk(self):
        # сумерки и темнота в парке: ничего, что требует ходить
        rx = re.compile(r"идите|пройдите|дойдите|обойдите|подойдите|отойдите|выберите поворот|"
                        r"проверьте по пути|сделайте .* шаг|перейдите|спуститесь|поднимитесь",
                        re.IGNORECASE)
        bad = [c["id"] for c in self.nature()
               if ("сумерки" in c["light"] or "темнота" in c["light"]) and rx.search(c["text"])]
        self.assertEqual(bad, [])

    def test_plants_are_looked_at_not_touched(self):
        # в парках и лесах бывает борщевик, а у малышей всё идёт в рот:
        # растения не срываем и не трогаем, берём только то, что уже упало
        rx_plant = re.compile(r"растени|лист(?!в)", re.IGNORECASE)
        rx_ok = re.compile(r"не трогая|не срывая|упали|опавш|на земле", re.IGNORECASE)
        bad = [c["id"] for c in self.nature()
               if rx_plant.search(c["text"]) and not rx_ok.search(c["text"])]
        self.assertEqual(bad, [])

    def test_nothing_in_the_park_can_be_lost(self):
        # карточку нельзя проиграть: если искомого нет, она всё равно выполнена
        rx = re.compile(r"не нашли|нет .{0,30}карта выполнена|не слышно|не видно|достаточно|"
                        r"если .{0,40}далеко|не получается", re.IGNORECASE)
        risky = {"НАР-71", "НАР-77", "НАР-79", "ЧМ-32", "ЧМ-33", "ЧМ-36", "СБ-21"}
        by_id = {c["id"]: c for c in CARDS}
        bad = [i for i in risky if not rx.search(by_id[i]["text"] + " " + (by_id[i].get("fallback") or ""))]
        self.assertEqual(sorted(bad), [])

    def test_nature_cards_that_walk_stay_on_the_path(self):
        rx = re.compile(r"тропы|по пути|по тропе", re.IGNORECASE)
        bad = [c["id"] for c in self.nature()
               if re.search(r"проверьте по пути|дойдите|пройдите", c["text"], re.I)
               and not rx.search(c["text"])]
        self.assertEqual(bad, [])

    def test_each_environment_has_every_mode(self):
        for env in ENVS:
            for key in groups():
                self.assertTrue(pool(key, "день", "лето", env=env), (env, key))


class Coverage(unittest.TestCase):
    """Пул не должен пустеть там, где человек бывает чаще всего."""

    def test_every_group_has_cards(self):
        empty = [k for k, v in groups().items() if not v]
        self.assertEqual(empty, [])

    def test_adult_tier_exists(self):
        self.assertGreaterEqual(len(groups()[("совместное-внимание", "со-взрослым")]), 8)

    def test_joint_attention_age_order(self):
        order = [a for a in AGES if groups()[("совместное-внимание", a)]]
        self.assertEqual(order, AGES)   # ребёнок первый, «со взрослым» последний

    def test_outside_levels_not_lopsided(self):
        n = {lvl: len(groups()[("наружу", lvl)]) for lvl in (1, 2, 3)}
        self.assertGreaterEqual(min(n.values()), 10, n)

    def test_dark_autumn_and_winter_never_empty(self):
        # ноябрьский вечер в 18:30 — самый частый сценарий
        empty = []
        for key in groups():
            for season in ("осень", "зима"):
                if not pool(key, "темнота", season, city="спб"):
                    empty.append((key, season))
        self.assertEqual(empty, [])

    def test_daytime_never_empty(self):
        empty = []
        for key in groups():
            for season in ("зима", "весна", "лето", "осень"):
                for light in ("день", "низкое-солнце"):
                    if not pool(key, light, season, city="спб"):
                        empty.append((key, light, season))
        self.assertEqual(empty, [])

    def test_twilight_never_empty_outside_the_two_cities(self):
        # раньше у «Читать место» вне Москвы и Петербурга сумеречный пул был пуст
        empty = [(key, s) for key in groups() for s in ("осень", "весна")
                 if not pool(key, "сумерки", s, city=None)]
        self.assertEqual(empty, [])

    def test_no_pool_is_thinner_than_the_minimum(self):
        # любая ступень в любой свет и сезон, в обеих средах: от темноты до низкого
        # солнца, которое зимой в Петербурге — это весь световой день (не выше 6,6°)
        thin = []
        for env in ENVS:
            for key in groups():
                for light in ("день", "низкое-солнце", "сумерки", "темнота"):
                    for season in ("зима", "весна", "лето", "осень"):
                        n = len(pool(key, light, season, city=None, env=env))
                        if n < MIN_POOL:
                            thin.append((env, key, light, season, n))
        self.assertEqual(thin, [])

    def test_dark_evening_pools_have_room_to_vary(self):
        # ноябрьский вечер: ступени не должны сводиться к двум-трём карточкам
        small = {}
        for env in ENVS:
            for key in groups():
                n = min(len(pool(key, "темнота", s, city=None, env=env)) for s in ("осень", "зима"))
                if n < 3:
                    small[(env, key)] = n
        self.assertEqual(small, {})

    def test_city_has_no_pool_below_four(self):
        # город — основная среда: там запас больше
        thin = [(key, light, season)
                for key in groups()
                for light in ("день", "низкое-солнце", "сумерки", "темнота")
                for season in ("зима", "весна", "лето", "осень")
                if len(pool(key, light, season, city="спб", env="город")) < 4]
        self.assertEqual(thin, [])

    def test_read_place_has_its_own_material_in_the_park(self):
        # раньше у «Читать место» в парке не было ни одной карты на сумерки и темноту
        mode = ("читать-место", None)
        for light in ("день", "низкое-солнце", "сумерки", "темнота"):
            self.assertGreaterEqual(len(pool(mode, light, "осень", env="природа")), 3, light)

    def test_history_cards_do_not_starve_a_pool(self):
        # новичок не видит needsHistory; пул без них не должен пустеть
        empty = []
        for key, cards in groups().items():
            if cards and all(c["needsHistory"] for c in cards):
                empty.append(key)
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main()
