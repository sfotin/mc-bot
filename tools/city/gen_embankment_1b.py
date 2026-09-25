"""
Генератор схемы 1b района «Набережная» (см. CITY.md - Районы - Набережная):
расширение пляжа на запад от готовой стенки (этап 1). Строит рельеф по
данным съёмки региона (docs/terrain/site.json, см. tools/terrain/), выводит
результаты обоих обязательных валидаторов - проходимости и опор (см.
BOT.md §12) - и картинку-превью с разрезом до/после по X = -735.

Запуск:
    gen_embankment_1b.py [--site docs/terrain/site.json]
                          [--out schemas/embankment-1b-beach.json]
                          [--preview docs/districts/embankment-1b-preview.png]

Порядок слоёв (см. BOT.md §12): 1) массивы, 2) полости, 3) восстановление
(здесь не требуется), 4) детали/декор (здесь не требуется) - соблюдён ниже
в этом же порядке.
"""
import argparse
import json
import os
from collections import Counter, deque

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SITE = 'docs/terrain/site.json'
DEFAULT_OUT = 'schemas/embankment-1b-beach.json'
DEFAULT_PREVIEW = 'docs/districts/embankment-1b-preview.png'

X1, X2 = -752, -717  # пляж между естественным склоном на западе и возвратной стенкой x=-716


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


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=DEFAULT_SITE,
                    help='site.json от terrain_from_region.py (по умолчанию %(default)s)')
    p.add_argument('--out', default=DEFAULT_OUT,
                    help='выходная схема (по умолчанию %(default)s)')
    p.add_argument('--preview', default=DEFAULT_PREVIEW,
                    help='превью PNG (по умолчанию %(default)s)')
    return p.parse_args()


def target(z):
    if z <= 1864: return 63          # сухой пляж, на 1 ниже аллеи (Y 64)
    if z <= 1866: return 62          # кромка воды
    return 61 - (z - 1867) // 3      # под водой уклон 1 блок на 3 блока


def main():
    args = parse_args()

    with open(args.site, encoding='utf-8') as f:
        d = json.load(f)
    SX0, SZ0, SW = d['x0'], d['z0'], d['w']

    def G(x, z): return d['ground'][(z - SZ0) * SW + (x - SX0)]

    def T(x, z): return d['top'][(z - SZ0) * SW + (x - SX0)]

    def WA(x, z): return d['water'][(z - SZ0) * SW + (x - SX0)]

    cells = {}  # (x,y,z)->block ; later writes win

    def put(x, y, z, b):
        cells[(x, y, z)] = b

    # ---------- 1. МАССИВЫ + 2. ПОЛОСТИ (по колонке, зависят друг от друга) ----------
    for x in range(X1, X2 + 1):
        for z in range(1860, 1890):
            t = target(z); g = G(x, z)
            if t < 55: break
            if x <= -750 and WA(x, z) is None and g > t:  # западный край: не срезаем естественный склон
                continue
            # массив: каменное ядро + 2 слоя песка
            for y in range(min(g, t) - 1, t - 1): put(x, y, z, 'stone')
            put(x, t - 1, z, 'sand'); put(x, t, z, 'sand')
            # полости: срезаем лишнее над целевым уровнем
            top = max(g, T(x, z) or g)
            for y in range(t + 1, top + 2):
                if y <= 62 and t < 62:
                    continue  # вода и так стоит (естественная)
                if y > 62 or WA(x, z) is None:
                    put(x, y, z, 'air')
            # под водой: если срезали грунт выше целевого ниже уровня моря - нужна вода
            if t < 62 and g > t:
                for y in range(t + 1, min(g, 62) + 1): put(x, y, z, 'water')

    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    out = [{'x': x - ox, 'y': y - oy, 'z': z - oz, 'block': b} for (x, y, z), b in cells.items()]
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
    print('origin', ox, oy, oz, 'size', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'entries', len(out))
    print(Counter(cells.values()))

    # ================= ВАЛИДАТОРЫ (обязательны перед отправкой схемы, см. BOT.md §12) =================
    def final(x, y, z):
        if (x, y, z) in cells: return cells[(x, y, z)]
        g = G(x, z); wa = WA(x, z)
        if y <= g: return 'ground'
        if wa is not None and y <= wa: return 'water'
        return 'air'

    SOLID = lambda b: b not in ('air', 'water')
    hang = [k for k, b in cells.items() if b == 'sand' and not SOLID(final(k[0], k[1] - 1, k[2]))]
    leak = [k for k, b in cells.items() if b == 'water'
            and any(final(k[0] + dx, k[1], k[2] + dz) == 'air' for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    inflow = [k for k, b in cells.items() if b == 'air'
              and any(((k[0] + dx, k[1], k[2] + dz) not in cells) and final(k[0] + dx, k[1], k[2] + dz) == 'water'
                      for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))]

    # проходимость: от аллеи (-735,65,1859 - ноги на Y65 над настилом 64) вниз по пляжу до кромки воды
    def stand(x, y, z): return SOLID(final(x, y - 1, z)) and final(x, y, z) == 'air' and final(x, y + 1, z) == 'air'

    start = (-735, 65, 1859); seen = {start}; q = deque([start])
    while q:
        x, y, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, -1, 1):
                n = (x + dx, y + dy, z + dz)
                if n in seen or not (X1 <= n[0] <= X2 or n[0] == -735) or not (1855 <= n[2] <= 1866): continue
                if stand(*n): seen.add(n); q.append(n)
    dry = [(x, z) for x in range(X1, X2 + 1) for z in range(1860, 1867) if (x, target(z) + 1, z) in seen]
    allcols = [(x, z) for x in range(X1, X2 + 1) for z in range(1860, 1867)
               if not (x <= -750 and WA(x, z) is None and G(x, z) > target(z))]
    print('ВАЛИДАТОР ПРОХОДИМОСТИ: клеток сухого пляжа', len(allcols), 'достижимо с аллеи', len(dry))
    print('ВАЛИДАТОР ОПОР: висящий песок', len(hang), hang[:5],
          '| утечка воды', len(set(leak)), list(set(leak))[:5],
          '| вода втекает в расчистку', len(set(inflow)), sorted(set(inflow))[:5])

    # ================= ПРЕВЬЮ =================
    f11, f13 = _load_font(12), _load_font(14, bold=True)
    COL = {'sand': (240, 220, 150), 'stone': (140, 140, 140), 'ground': (120, 170, 90),
           'water': (70, 120, 200), 'air': (235, 242, 250)}

    def orig(x, y, z):
        g = G(x, z); wa = WA(x, z)
        if y <= g: return 'ground'
        if wa is not None and y <= wa: return 'water'
        return 'air'

    S = 12; zs = range(1852, 1890); ys = range(50, 68)
    img = Image.new('RGB', (len(zs) * S + 120, 2 * (len(ys) * S + 60) + 20), (250, 250, 247))
    dr = ImageDraw.Draw(img)
    for k, (fn, title) in enumerate((
            (orig, 'До стройки (по съёмке): разрез по X = -735, юг справа'),
            (final, 'После схемы 1b: пляж шире, уклон 1 блок на 3'))):
        oy_ = 20 + k * (len(ys) * S + 60)
        dr.text((10, oy_ - 18), title, font=f13, fill=(0, 0, 0))
        for i, z in enumerate(zs):
            for j, y in enumerate(ys):
                b = fn(-735, y, z)
                if (-735, y, z) not in cells and b == 'ground' and z < 1860 and y == 64: b = 'sand'
                c = COL.get(b, (236, 226, 190))
                if z <= 1859 and y == 64: c = (236, 226, 190)
                if z <= 1859 and 60 <= y < 64: c = (140, 140, 140)
                dr.rectangle([10 + i * S, oy_ + (len(ys) - 1 - j) * S,
                              10 + i * S + S - 1, oy_ + (len(ys) - 1 - j) * S + S - 1], fill=c)
        for i, z in enumerate(zs):
            if z % 4 == 0: dr.text((10 + i * S, oy_ + len(ys) * S + 4), str(z), font=f11, fill=(60, 60, 60))
        for y in (52, 56, 60, 62, 64):
            dr.text((len(zs) * S + 20, oy_ + (len(ys) - 1 - (y - 50)) * S), f'Y{y}', font=f11, fill=(60, 60, 60))
    img.save(args.preview)
    print('preview', img.size)


if __name__ == '__main__':
    main()
