# -*- coding: utf-8 -*-
"""Иконки для домашнего экрана: тёмный квадрат и тёплое окно.

Никаких библиотек: PNG собирается вручную, благо в рисунке одни прямоугольники.
Запуск:  python tools/make_icons.py
"""
import io, os, struct, zlib

BG = (0x14, 0x1C, 0x26)
LIGHT = (0xD9, 0x94, 0x4A)

OUT = "icons"
SIZES = [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)]


def draw(size):
    """Полотно как список строк из пикселей."""
    px = [[BG] * size for _ in range(size)]

    # окно занимает середину: снаружи остаётся поле под обрезку маской
    w = int(size * 0.34)
    h = int(size * 0.58)
    x0 = (size - w) // 2
    y0 = int(size * 0.19)

    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            px[y][x] = LIGHT

    # переплёт: две полосы цвета фона делят окно на четыре части
    bar = max(2, int(size * 0.035))
    cx = x0 + w // 2 - bar // 2
    cy = y0 + int(h * 0.34) - bar // 2
    for y in range(y0, y0 + h):
        for x in range(cx, cx + bar):
            px[y][x] = BG
    for y in range(cy, cy + bar):
        for x in range(x0, x0 + w):
            px[y][x] = BG

    return px


def png(px):
    size = len(px)
    raw = bytearray()
    for row in px:
        raw.append(0)                      # фильтр: без фильтра
        for r, g, b in row:
            raw += bytes((r, g, b))

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            chunk(b"IEND", b""))


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#141C26"/>
  <rect x="169" y="97" width="174" height="297" fill="#D9944A"/>
  <rect x="247" y="97" width="18" height="297" fill="#141C26"/>
  <rect x="169" y="192" width="174" height="18" fill="#141C26"/>
</svg>
"""

if not os.path.isdir(OUT):
    os.mkdir(OUT)

for name, size in SIZES:
    data = png(draw(size))
    open(os.path.join(OUT, name), "wb").write(data)
    print("%-22s %d×%d, %d байт" % (name, size, size, len(data)))

io.open(os.path.join(OUT, "icon.svg"), "w", encoding="utf-8").write(SVG)
print("icon.svg")
