"""
Рисует карту подземных пустот по JSON от terrain_caves.py: цвет колонны по
количеству воздуха в полосе Y 10..(ground-4) (см. terrain_caves.py), базовый
фон - суша/вода из site.json, поверх - опорные точки города A-F и линии
метро/коллектора из генплана v1 (для сверки, где трассы пересекают пустоты).

Запуск:
    terrain_caves_render.py <caves.json> <site.json> <выход.png>
"""
import argparse
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

K = 5
ML, MT = 60, 45

PTS = {'A': (-762, 1910), 'B': (-748, 1819), 'C': (-667, 1816),
       'D': (-688, 1817), 'E': (-622, 1790), 'F': (-617, 1747)}

# Линии метро/коллектора из генплана v1 (см. CITY.md §2.4) - черновые
# координаты для наложения на карту пустот, не геометрия схем.
METRO_COLOR = (130, 0, 170)
COLLECTOR_COLOR = (0, 110, 200)
METRO_LINES = [((-790, 1826), (-600, 1826)), ((-694, 1740), (-694, 1860))]
COLLECTOR_LINES = [((-640, 1818), (-800, 1818)), ((-686, 1818), (-686, 1740)), ((-745, 1818), (-745, 1780))]


def _find_font_path(bold=False):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf' if bold
        else '/System/Library/Fonts/Supplemental/Arial.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _load_font(size, bold=False):
    path = _find_font_path(bold)
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def cave_color(count, base):
    if count >= 20: return (200, 30, 30)
    if count >= 10: return (240, 120, 40)
    if count >= 4: return (245, 200, 90)
    return base


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('caves', help='caves.json от terrain_caves.py')
    p.add_argument('site', help='site.json от terrain_from_region.py (для суши/воды)')
    p.add_argument('out', help='выходной PNG')
    return p.parse_args()


def main():
    args = parse_args()
    cav_d = json.load(open(args.caves, encoding='utf-8'))
    site_d = json.load(open(args.site, encoding='utf-8'))
    X0, Z0, W, H = cav_d['x0'], cav_d['z0'], cav_d['w'], cav_d['h']

    air = np.array([v if v is not None else 0 for v in cav_d['air']], int).reshape(H, W)

    # вода берётся из site.json - если бокс отличается, просто считаем сушей
    sx0, sz0, sw, sh = site_d['x0'], site_d['z0'], site_d['w'], site_d['h']
    is_water = np.zeros((H, W), bool)
    for z in range(H):
        for x in range(W):
            sx, sz = X0 + x - sx0, Z0 + z - sz0
            if 0 <= sx < sw and 0 <= sz < sh:
                is_water[z, x] = site_d['water'][sz * sw + sx] is not None

    f10, f12, f14, f20 = _load_font(10), _load_font(12), _load_font(14, bold=True), _load_font(20, bold=True)

    rgb = np.zeros((H, W, 3))
    for z in range(H):
        for x in range(W):
            base = (175, 200, 235) if is_water[z, x] else (235, 232, 222)
            rgb[z, x] = cave_color(air[z, x], base)
    img = Image.fromarray(rgb.astype('uint8')).resize((W * K, H * K), Image.NEAREST)

    LEG = 320
    out = Image.new('RGB', (ML + W * K + LEG, MT + H * K + 45), (250, 250, 247))
    out.paste(img, (ML, MT))
    dr = ImageDraw.Draw(out)

    nx, nz = W // 16, H // 16
    cx_label0, cz_label0 = X0 // 16, Z0 // 16
    for i in range(nx + 1):
        dr.line([(ML + i * 80, MT), (ML + i * 80, MT + H * K)], fill=(120, 120, 120))
    for i in range(nz + 1):
        dr.line([(ML, MT + i * 80), (ML + W * K, MT + i * 80)], fill=(120, 120, 120))
    for i in range(nx):
        dr.text((ML + i * 80 + 40, MT - 12), str(cx_label0 + i), font=f10, fill=(80, 80, 80), anchor='mm')
    for i in range(nz):
        dr.text((ML - 22, MT + i * 80 + 40), str(cz_label0 + i), font=f10, fill=(80, 80, 80), anchor='mm')

    def to_px(x, z):
        return ML + (x - X0) * K + 2, MT + (z - Z0) * K + 2

    def dash(a, b, col, width):
        (ax, ay), (bx, by) = to_px(*a), to_px(*b)
        length = math.hypot(bx - ax, by - ay)
        n = max(1, int(length // 8))
        for i in range(0, n, 2):
            x1 = ax + (bx - ax) * i / n
            y1 = ay + (by - ay) * i / n
            x2 = ax + (bx - ax) * min(1, (i + 1) / n)
            y2 = ay + (by - ay) * min(1, (i + 1) / n)
            dr.line([(x1, y1), (x2, y2)], fill=col, width=width)

    for a, b in METRO_LINES:
        dash(a, b, METRO_COLOR, 4)
    for a, b in COLLECTOR_LINES:
        dash(a, b, COLLECTOR_COLOR, 3)

    for k, (x, z) in PTS.items():
        if not (X0 <= x < X0 + W and Z0 <= z < Z0 + H):
            continue
        px, py = to_px(x, z)
        dr.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(0, 70, 200))
        dr.text((px + 6, py - 16), k, font=f14, fill=(0, 50, 160), stroke_width=3, stroke_fill='white')

    dr.text((ML, MT + H * K + 10),
            f'Пустоты под землёй: число блоков воздуха в колонне от Y 10 до (грунт − 4). '
            f'X {X0} … {X0 + W - 1}, Z {Z0} … {Z0 + H - 1}.',
            font=f12, fill=(50, 50, 50))

    lx, y = ML + W * K + 20, MT
    dr.text((lx, y), 'ПОДЗЕМНЫЕ ПУСТОТЫ', font=f20, fill=(0, 0, 0)); y += 34
    for col, t in (((200, 30, 30), '≥ 20 блоков (каньон)'), ((240, 120, 40), '10-19'),
                   ((245, 200, 90), '4-9 (пещеры)'), ((235, 232, 222), '< 4, суша'),
                   ((175, 200, 235), '< 4, под водой')):
        dr.rectangle([lx, y, lx + 26, y + 16], fill=col, outline=(0, 0, 0))
        dr.text((lx + 34, y), t, font=f12, fill=(0, 0, 0)); y += 22
    y += 10
    for col, t in ((METRO_COLOR, 'метро (генплан v1)'), (COLLECTOR_COLOR, 'коллектор (генплан v1)')):
        for i in range(0, 26, 8):
            dr.line([(lx + i, y + 8), (lx + i + 4, y + 8)], fill=col, width=4)
        dr.text((lx + 34, y), t, font=f12, fill=(0, 0, 0)); y += 22

    out.save(args.out)
    print(out.size)


if __name__ == '__main__':
    main()
