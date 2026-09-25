"""
Генератор схемы 1 района «Набережная» (см. CITY.md - Районы - Набережная):
земляные работы, стенка набережной, пляж. Строит рельеф по данным съёмки
региона (docs/terrain/site.json, см. tools/terrain/), выводит результаты
обоих обязательных валидаторов - проходимости и опор (см. BOT.md §12) -
и картинку-превью с видом сверху и двумя разрезами.

Запуск:
    gen_embankment_1.py [--site docs/terrain/site.json]
                         [--out schemas/embankment-1-earthworks.json]
                         [--preview docs/districts/embankment-1-preview.png]

Порядок слоёв (см. BOT.md §12): 1) массивы, 2) полости, 3) восстановление
(здесь не требуется), 4) детали/декор - соблюдён ниже в этом же порядке.
"""
import argparse
import json
import os
from collections import Counter, deque

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SITE = 'docs/terrain/site.json'
DEFAULT_OUT = 'schemas/embankment-1-earthworks.json'
DEFAULT_PREVIEW = 'docs/districts/embankment-1-preview.png'

LVL = 64


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


def main():
    args = parse_args()

    with open(args.site, encoding='utf-8') as f:
        d = json.load(f)
    SX0, SZ0, SW = d['x0'], d['z0'], d['w']

    def G(x, z): return d['ground'][(z - SZ0) * SW + (x - SX0)]

    def T(x, z): return d['top'][(z - SZ0) * SW + (x - SX0)]

    def WA(x, z): return d['water'][(z - SZ0) * SW + (x - SX0)]

    def in_street(x, z): return -775 <= x <= -662 and 1850 <= z <= 1859

    def in_plaza(x, z): return -700 <= x <= -680 and 1848 <= z <= 1868

    def in_deck(x, z): return -715 <= x <= -683 and 1860 <= z <= 1868

    def FP(x, z): return in_street(x, z) or in_plaza(x, z) or in_deck(x, z)

    cells = {}  # (x,y,z)->block ; later writes win

    def put(x, y, z, b):
        cells[(x, y, z)] = b

    XS = range(-776, -660)
    ZS = range(1846, 1880)

    # ---------- 1. МАССИВЫ ----------
    for x in XS:
        for z in ZS:
            if FP(x, z):
                for y in range(60, LVL): put(x, y, z, 'stone')          # основание 60..63
                put(x, LVL, z, 'sandstone:2')                           # временное покрытие (гладкий песчаник)
    # подпорные стенки: колонны вне следа, соседние со следом, где грунт выше 64
    RET = set()
    for x in XS:
        for z in ZS:
            if FP(x, z): continue
            if any(FP(x + dx, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                g = G(x, z)
                if g is not None and g > LVL and WA(x, z) is None:
                    for y in range(60, g + 1): put(x, y, z, 'stonebrick')
                    RET.add((x, z))
    # стенка набережной z=1869, X -715..-683, и возврат по x=-716 (z 1860..1869)
    WALL = [(x, 1869) for x in range(-716, -682)] + [(-716, z) for z in range(1860, 1869)]
    for x, z in WALL:
        bot = min(G(x, z), 57) - 1
        for y in range(bot, LVL + 1): put(x, y, z, 'stonebrick')

    # ---------- 2. ПОЛОСТИ ----------
    MAXT = 0
    for x in XS:
        for z in ZS:
            if FP(x, z) or (x, z) in WALL:
                t = max(T(x, z) or 0, G(x, z) or 0); MAXT = max(MAXT, t)
                for y in range(LVL + 1, max(t, LVL) + 3): put(x, y, z, 'air')
    # углубление у стенки: z 1870..1874, X -715..-683 -> дно 57, вода 58..62
    DREDGE = 0
    for x in range(-715, -682):
        for z in range(1870, 1875):
            g = G(x, z)
            if g >= 58:
                put(x, 57, z, 'sand')
                for y in range(58, 63):
                    if not (WA(x, z) is not None and y <= WA(x, z) and y > g): put(x, y, z, 'water'); DREDGE += 1
                for y in range(63, max(g, T(x, z) or 0) + 2): put(x, y, z, 'air')
    # ---------- 3. (восстановление — не требуется) ----------
    # ---------- 4. ДЕТАЛИ ----------
    # парапет: кварц на Y 65 по стенке, проёмы: пирс x -692..-688, кафе x -709..-706; на возврате — только z 1864..1869
    for x, z in WALL:
        if z == 1869 and (-692 <= x <= -688 or -709 <= x <= -706): continue
        if x == -716 and z < 1864: continue
        put(x, LVL + 1, z, 'quartz_block')
    # пляж: X -750..-717, от z 1860 до берега +4 под водой: верхний слой -> песок
    BEACH = 0
    for x in range(-750, -716):
        for z in range(1860, 1880):
            g = G(x, z); wa = WA(x, z)
            if wa is None:
                if g > LVL: continue
                put(x, g - 3, z, 'stone'); put(x, g - 2, z, 'stone'); put(x, g, z, 'sand'); put(x, g - 1, z, 'sand'); BEACH += 1
                for y in range(g + 1, (T(x, z) or g) + 2): put(x, y, z, 'air')
            elif wa - g <= 4:
                put(x, g - 1, z, 'stone'); put(x, g, z, 'sand'); BEACH += 1

    # пруд у восточного конца улицы (вода на Y 65): каменный борт по краю, чтобы вода не текла на улицу
    for _ in range(3):
        add = []
        for (x, y, z), b in list(cells.items()):
            if b != 'air': continue
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if (nx, y, nz) in cells: continue
                wa = WA(nx, nz)
                if wa is not None and G(nx, nz) < y <= wa: add.append((nx, nz))
        for nx, nz in set(add):
            for y in range(G(nx, nz) + 1, WA(nx, nz) + 1): put(nx, y, nz, 'stonebrick')
            put(nx, WA(nx, nz) + 1, nz, 'stone_slab:5')

    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    out = [{'x': x - ox, 'y': y - oy, 'z': z - oz, 'block': b} for (x, y, z), b in cells.items()]
    # порядок: всё, кроме воды, затем вода (вода и так идёт поздним проходом бота)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'))
    print('origin', ox, oy, oz, 'size', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'entries', len(out))
    print(Counter(b for b in cells.values()))
    print('maxTop', MAXT, 'retaining cols', len(RET), 'dredge water', DREDGE, 'beach cols', BEACH)

    # ================= ВАЛИДАТОРЫ (обязательны перед отправкой схемы, см. BOT.md §12) =================
    def final(x, y, z):
        if (x, y, z) in cells: return cells[(x, y, z)]
        g = G(x, z); wa = WA(x, z)
        if y <= g: return 'ground'
        if wa is not None and y <= wa: return 'water'
        return 'air'

    SOLID = lambda b: b not in ('air', 'water')
    # проходимость: по следу, ноги на Y 65
    start = (-690, 1858); seen = {start}; q = deque([start])
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n in seen or not FP(*n): continue
            if SOLID(final(n[0], 64, n[1])) and final(n[0], 65, n[1]) == 'air' and final(n[0], 66, n[1]) == 'air':
                seen.add(n); q.append(n)
    fp = [(x, z) for x in XS for z in ZS if FP(x, z)]
    unreach = [c for c in fp if c not in seen]
    print('ВАЛИДАТОР ПРОХОДИМОСТИ: клеток следа', len(fp), 'достижимо', len(seen), 'недостижимо', len(unreach), unreach[:5])
    # опоры: песок не висит; вода не утекает
    hang = [k for k, b in cells.items() if b == 'sand' and not SOLID(final(k[0], k[1] - 1, k[2]))]
    leak = []
    for (x, y, z), b in cells.items():
        if b != 'water': continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            f = final(x + dx, y, z + dz)
            if f == 'air': leak.append((x, y, z))
        if final(x, y - 1, z) == 'air': leak.append((x, y, z))
    print('ВАЛИДАТОР ОПОР: висящий песок', len(hang), hang[:5], '| вода с утечкой', len(set(leak)), list(set(leak))[:5])

    # ================= ПРЕВЬЮ =================
    f11, f13, f16 = _load_font(11), _load_font(13), _load_font(16, bold=True)
    COL = {'sandstone:2': (236, 226, 190), 'stonebrick': (120, 120, 120), 'quartz_block': (250, 250, 250),
           'sand': (240, 220, 150), 'stone': (140, 140, 140), 'ground': (120, 170, 90), 'water': (70, 120, 200)}
    X1, X2, Z1, Z2 = -790, -655, 1840, 1890; K = 7; ML, MT = 50, 50
    w, h = (X2 - X1 + 1) * K, (Z2 - Z1 + 1) * K
    img = Image.new('RGB', (ML + w + 20, MT + h + 330), (250, 250, 247)); dr = ImageDraw.Draw(img)
    dr.text((ML, 12), 'Схема 1 «Земляные работы, стенка, пляж» — результат сверху (цвет = верхний блок, светлее = выше)', font=f16, fill=(0, 0, 0))
    for x in range(X1, X2 + 1):
        for z in range(Z1, Z2 + 1):
            y = 90; b = 'air'
            while y > 30:
                b = final(x, y, z)
                if b != 'air': break
                y -= 1
            c = COL.get(b, (200, 0, 200)); k = 1 + (y - 64) * 0.04
            c = tuple(max(0, min(255, int(v * k))) for v in c)
            px, py = ML + (x - X1) * K, MT + (z - Z1) * K; dr.rectangle([px, py, px + K - 1, py + K - 1], fill=c)
    for x in range(X1, X2 + 1, 10): dr.text((ML + (x - X1) * K, MT - 10), str(x), font=f11, fill=(60, 60, 60), anchor='mm')
    for z in range(Z1, Z2 + 1, 10): dr.text((ML - 22, MT + (z - Z1) * K), str(z), font=f11, fill=(60, 60, 60), anchor='mm')

    # разрезы
    def section(x, y0, label):
        S = 5; zs = range(1844, 1886); ys = range(52, 72)
        ox_, oy_ = ML, y0
        dr.text((ox_, oy_ - 18), label, font=f13, fill=(0, 0, 0))
        for i, z in enumerate(zs):
            for j, y in enumerate(ys):
                b = final(x, y, z); c = COL.get(b, (245, 245, 245)) if b != 'air' else (235, 242, 250)
                px, py = ox_ + i * S * 2, oy_ + (len(ys) - 1 - j) * S; dr.rectangle([px, py, px + S * 2 - 1, py + S - 1], fill=c)
        for i, z in enumerate(zs):
            if z % 5 == 0: dr.text((ox_ + i * S * 2, oy_ + len(ys) * S + 6), str(z), font=f11, fill=(60, 60, 60), anchor='mm')
        for y in (56, 62, 64, 70): dr.text((ox_ + len(zs) * S * 2 + 18, oy_ + (len(ys) - 1 - (y - 52)) * S + 2), f'Y{y}', font=f11, fill=(60, 60, 60), anchor='mm')

    section(-700, MT + h + 50, 'Разрез по X = −700 (центр: площадь → стенка → углубление), вид с запада, юг справа')
    section(-740, MT + h + 200, 'Разрез по X = −740 (запад: улица/аллея → пляж)')
    lx = ML + 470; ly = MT + h + 50
    for b, t in [('sandstone:2', 'покрытие Y 64'), ('stonebrick', 'стенки'), ('quartz_block', 'парапет'), ('sand', 'пляж/дно'), ('stone', 'основание'), ('ground', 'грунт'), ('water', 'вода')]:
        dr.rectangle([lx, ly, lx + 16, ly + 12], fill=COL[b], outline=(0, 0, 0)); dr.text((lx + 24, ly - 1), t, font=f11, fill=(0, 0, 0)); ly += 17
    img.save(args.preview); print('preview', img.size)

    inflow = set()
    for (x, y, z), b in cells.items():
        if b != 'air': continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y, z + dz)
            if n in cells: continue
            if final(*n) == 'water': inflow.add((x, y, z))
        n = (x, y + 1, z)
        if n not in cells and final(*n) == 'water': inflow.add((x, y, z))
    print('ВОДА ВТЕКАЕТ в расчищенный объём:', len(inflow), sorted(inflow)[:10])


if __name__ == '__main__':
    main()
