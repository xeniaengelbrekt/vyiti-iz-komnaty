# -*- coding: utf-8 -*-
"""Разбор свода колоды в cards.json и cards.js по схеме сайта.

Источников может быть несколько: свод и дополнения к нему собираются в одну колоду.

Запуск:  python tools/parse_deck.py [источник.md ...] [-o cards.json]
"""
import json, re, sys, io, os, collections

DEFAULT_SOURCES = ["koloda-svod.md", "koloda-dopolnenie.md"]

args = sys.argv[1:]
DST = "cards.json"
if "-o" in args:
    i = args.index("-o")
    DST = args[i + 1]
    args = args[:i] + args[i + 2:]
SOURCES = args or DEFAULT_SOURCES

MODE_BY_PREFIX = {
    "НАР": "наружу",
    "ЧМ": "читать-место",
    "СПб": "читать-место",
    "МСК": "читать-место",
    "СВ": "совместное-внимание",
    "СБ": "с-собакой",
    "ПД": "полевой-дневник",
}
CITY_BY_PREFIX = {"СПб": "спб", "МСК": "мск"}
MODALITIES = {"зрение", "слух", "обоняние", "температура", "кросс"}
ENTRY_TYPES = {"свободная", "с ограничением"}
AGE_BY_SECTION = [
    ("2–3", "2-3"), ("4–5", "4-5"), ("6–8", "6-8"), ("9–12", "9-12"),
]
# карты, которым нужна память о месте (часть VIII свода) + ПД-12: она
# прямо требует более ранней записи о том же месте
NEEDS_HISTORY = {"НАР-36", "НАР-43", "НАР-48", "ПД-12", "ПД-08б"}
# обратное условие: карточка только для тех, кто здесь ещё не был
NO_HISTORY = {"ПД-08а"}

# у разделённых карточек к номеру добавлена буква: ПД-08а, ПД-08б
CARD_RE = re.compile(r"^\*\*([A-Za-zА-Яа-яЁё]+-\d+[А-Яа-яA-Za-z]?)\s*·\s*(.+?)\*\*(.*)$")
HEAD_RE = re.compile(r"^#{1,6}\s")
TOKEN_RE = re.compile(r"`([^`]+)`")

blocks = []
for src in SOURCES:
    text = io.open(src, encoding="utf-8").read().replace("\r\n", "\n")
    cur, section = None, ""
    for ln in text.split("\n"):
        m = CARD_RE.match(ln)
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(),
                   "raw": [m.group(3)], "section": section, "source": src}
            blocks.append(cur)
            continue
        if HEAD_RE.match(ln):
            section, cur = ln.lstrip("#").strip(), None
            continue
        if cur is not None:
            cur["raw"].append(ln)


def split_list(value):
    return [p.strip() for p in value.split(",") if p.strip()]


cards, problems = [], []
for b in blocks:
    raw = "\n".join(b["raw"])
    prefix = b["id"].split("-")[0]
    card = {
        "id": b["id"],
        "mode": MODE_BY_PREFIX[prefix],
        "title": b["title"],
        "text": "",
        "back": "",
        "level": None,
        "age": None,
        "light": [],
        "seasons": ["любой"],
        "weather": ["неважно"],
        "weatherNot": [],
        "modality": None,
        "criterion": None,
        "needsHistory": b["id"] in NEEDS_HISTORY,
        "noHistory": b["id"] in NO_HISTORY,
        "cityPack": CITY_BY_PREFIX.get(prefix),
        "buildingType": None,
        "layer": None,
        "entryType": None,
        "fallback": None,
    }

    # текст задания — строки цитаты
    quote = [l[1:].strip() for l in raw.split("\n") if l.startswith(">")]
    card["text"] = " ".join(x for x in quote if x)

    # оборот и «если не пошло»
    m = re.search(r"\*Оборот\.\*\s*(.+)", raw)
    if m:
        card["back"] = m.group(1).strip()
    m = re.search(r"\*Если не получается:\*\s*(.+)", raw)
    if m:
        card["fallback"] = m.group(1).strip()

    # критерий
    m = re.search(r"критерий:\s*([^\n]+)", raw)
    if m:
        card["criterion"] = m.group(1).strip().rstrip(".")

    # теги в обратных кавычках
    for tok in TOKEN_RE.findall(raw):
        tok = tok.strip()
        if tok in MODALITIES:
            card["modality"] = tok
        elif tok in ENTRY_TYPES:
            card["entryType"] = tok
        elif tok.startswith("ур. "):
            card["level"] = int(tok[4:])
        elif tok.startswith("шаг "):
            card["level"] = int(tok[4:])
        elif ":" in tok:
            key, value = tok.split(":", 1)
            key, value = key.strip(), value.strip()
            if key == "свет":
                card["light"] = split_list(value)
            elif key == "сезон":
                card["seasons"] = split_list(value)
            elif key == "погода":
                card["weather"] = split_list(value)
            elif key == "погода кроме":
                card["weatherNot"] = split_list(value)
            elif key == "слой":
                card["layer"] = value
            elif key == "застройка":
                card["buildingType"] = None if value == "любая" else value
            else:
                problems.append("%s: неизвестный ключ %s" % (card["id"], key))
        else:
            problems.append("%s: неизвестный тег %s" % (card["id"], tok))

    if card["mode"] == "совместное-внимание":
        for marker, value in AGE_BY_SECTION:
            if b["section"].startswith(marker):
                card["age"] = value
        if not card["age"]:
            problems.append("%s: не определён возраст (%s)" % (card["id"], b["section"]))

    if not card["light"]:
        problems.append("%s: нет тега света" % card["id"])
    if not card["text"]:
        problems.append("%s: пустой текст задания" % card["id"])
    if not card["back"]:
        problems.append("%s: пустой оборот" % card["id"])
    cards.append(card)

ids = [c["id"] for c in cards]
dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
if dupes:
    problems.append("дубликаты id: %s" % ", ".join(dupes))

io.open(DST, "w", encoding="utf-8").write(
    json.dumps(cards, ensure_ascii=False, indent=1) + "\n")

# то же самое обычным скриптом: страница открывается и с file://, и без сети
js_dst = os.path.join(os.path.dirname(DST) or ".", "cards.js")
io.open(js_dst, "w", encoding="utf-8").write(
    "/* Сгенерировано tools/parse_deck.py из " + ", ".join(SOURCES) +
    ". Руками не править. */" + chr(10) +
    "window.KOLODA = " + json.dumps(cards, ensure_ascii=False, indent=1) + ";" + chr(10))

by_mode = collections.Counter(c["mode"] for c in cards)
print("всего карт:", len(cards))
for k, v in sorted(by_mode.items()):
    print("  %-22s %d" % (k, v))
print("нужна история места:", sum(1 for c in cards if c["needsHistory"]))
print("городские наборы: спб %d, мск %d" % (
    sum(1 for c in cards if c["cityPack"] == "спб"),
    sum(1 for c in cards if c["cityPack"] == "мск")))
print("возрасты:", dict(collections.Counter(
    c["age"] for c in cards if c["mode"] == "совместное-внимание")))
print("уровни «наружу»:", dict(collections.Counter(
    c["level"] for c in cards if c["mode"] == "наружу")))
print("шаги «читать место»:", dict(collections.Counter(
    c["level"] for c in cards if c["mode"] == "читать-место")))
print("проблем:", len(problems))
for p in problems:
    print("  ", p)
