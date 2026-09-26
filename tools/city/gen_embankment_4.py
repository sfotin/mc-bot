"""Набережная, этап 4: колесо обозрения на мысе (CITY.md §7.1), статичное,
с 12 кабинками, в которые можно сесть.

Запуск:
    gen_embankment_4.py [--out schemas/embankment-4-ferris-wheel.json]
                        [--preview docs/districts/embankment-4-preview.png]

Колесо в плоскости X-Y (видно с моря и с улицы), ось вдоль Z: центр X -672,
Y 84, диаметр 25 (R 12). Два обода в плоскостях Z 1870 и Z 1876, кабинки
3x5 между ними (Z 1871..1875) висят на тягах. А-образные опоры в плоскостях
Z 1869 и Z 1877. Посадка - с платформы Y 68 к нижней кабинке; подход с
площади по лестнице в подпорной стенке (X -679..-677, Z 1862..1864) и
дорожке по мысу.

Модель мира: рельеф docs/terrain/site.json + построенные схемы 1, 1d, 2, 3 и
фонтан 13x13 v2. Строится ПОВЕРХ них, запуск без --prepare. Порядок слоёв
(BOT.md §12): 1) массивы (фундаменты, опоры, обод, ступица), 2) полости,
3) детали. Проверки: проходимость (BFS игрока 2 блока), опоры + вода +
порядок постройки (decor_lib по реальному порядку команд бота).
"""
import argparse
import json
import math
import os
import sys
from collections import Counter, deque

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

BUILT = (('embankment-1-earthworks.json', (-776, 56, 1847)),
         ('embankment-1d-beach-rebuild.json', (-756, 47, 1860)),
         ('embankment-2-promenade.json', (-775, 63, 1848)),
         ('decor-fountain-13-med.json', (-696, 64, 1852)),
         ('embankment-3-pier-cafe.json', (-713, 48, 1869)))
XC, YC, R = -672, 84, 12
ZR = (1870, 1876)          # плоскости ободов
ZA = (1869, 1877)          # плоскости А-образных опор
ZK = range(1871, 1876)     # кабинки
N_CAB = 12
COLORS = [0, 3, 1, 4, 11, 14, 0, 3, 1, 4, 11, 14]  # белый, голубой, оранжевый, жёлтый, синий, красный


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=os.path.join(REPO, 'docs', 'terrain', 'site.json'))
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'embankment-4-ferris-wheel.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'embankment-4-preview.png'))
    return p.parse_args()


def line(a, b):
    """4-связная линия между (x,y) точками - без щелей по диагонали."""
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0)) * 4 + 1
    pts = []
    for i in range(n + 1):
        t = i / n
        p = (round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t))
        if pts and p != pts[-1] and p[0] != pts[-1][0] and p[1] != pts[-1][1]:
            pts.append((p[0], pts[-1][1]))  # ступенька вместо касания углом
        if not pts or p != pts[-1]: pts.append(p)
    return pts


def main():
    args = parse_args()
    d = json.load(open(args.site))
    W, X0, Z0 = d['w'], d['x0'], d['z0']

    def G(x, z): return d['ground'][(z - Z0) * W + x - X0]

    def WA(x, z): return d['water'][(z - Z0) * W + x - X0]

    def T(x, z): return d['top'][(z - Z0) * W + x - X0]

    PRE = {}
    for fn, o in BUILT:
        for e in json.load(open(os.path.join(REPO, 'schemas', fn))):
            PRE[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def world(x, y, z):
        if (x, y, z) in PRE: return PRE[(x, y, z)]
        if y <= G(x, z): return 'ground'
        if WA(x, z) is not None and y <= WA(x, z): return 'water'
        if T(x, z) is not None and G(x, z) < y <= T(x, z): return 'plant'  # трава/цветы над грунтом
        return 'air'

    def SOLID(b): return b not in ('air', 'water', 'plant') and not b.startswith('flowing_water')

    def surf(x, z):
        for y in range(100, 30, -1):
            if SOLID(world(x, y, z)): return y

    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    # ================= 1. МАССИВЫ =================
    # обод: кольцо R 12 в двух плоскостях; точки подвеса кабинок - на ободе
    ring = []
    for i in range(3600):
        a = math.radians(i / 10)
        p = (round(R * math.sin(a)), round(-R * math.cos(a)))
        if not ring or p != ring[-1]: ring.append(p)
    ring = list(dict.fromkeys(ring))
    cab = [(round(R * math.sin(math.radians(30 * k))), round(-R * math.cos(math.radians(30 * k)))) for k in range(N_CAB)]
    lights = [(round(R * math.sin(math.radians(30 * k + 15))), round(-R * math.cos(math.radians(30 * k + 15)))) for k in range(N_CAB)]
    for z in ZR:
        for (dx, dy) in ring: put(XC + dx, YC + dy, z, 'quartz_block')
        for (dx, dy) in cab: put(XC + dx, YC + dy, z, 'quartz_block')
        for (dx, dy) in cab:  # спицы - железные решётки от ступицы к точкам подвеса
            for (sx, sy) in line((0, 0), (dx, dy))[2:-1]:
                if (XC + sx, YC + sy, z) not in cells: put(XC + sx, YC + sy, z, 'iron_bars')
        for a in (-1, 0, 1):  # ступица 3x3
            for b in (-1, 0, 1): put(XC + a, YC + b, z, 'quartz_block')
        put(XC, YC, z, 'sea_lantern')
        for (dx, dy) in lights: put(XC + dx, YC + dy, z, 'sea_lantern')  # подсветка обода между кабинками
    for z in range(ZA[0], ZA[1] + 1):  # ось вдоль Z
        if z not in ZR: put(XC, YC, z, 'quartz_block')
    # А-образные опоры: две ноги в каждой плоскости ZA, от фундамента к ступице
    LEG_FEET = (XC - 7, XC + 7)
    for z in ZA:
        for fx in LEG_FEET:
            g = surf(fx, z)
            for y in range(G(fx, z) - 1, g + 1):  # фундамент: столб до грунта и чуть ниже
                if not SOLID(world(fx, y, z)) or y == g: put(fx, y, z, 'stonebrick')
            for (lx, ly) in line((fx, g + 1), (XC + (1 if fx > XC else -1), YC - 1)): put(lx, ly, z, 'quartz_block')
        for a in (-1, 0, 1):
            for b in (-1, 0, 1): put(XC + a, YC + b, z, 'quartz_block')
        # распорка между ногами на Y 74
        xs = sorted(x for (x, y, zz) in cells if zz == z and y == 74 and cells[(x, y, zz)] == 'quartz_block')
        for x in range(xs[0] + 1, xs[-1]): put(x, 74, z, 'iron_bars')

    # подход: лестница в подпорной стенке площади и дорожка по мысу (грунт Y 67)
    STAIR_Z = range(1862, 1865)
    for z in STAIR_Z:
        for i, x in enumerate((-679, -678, -677)):
            y = 65 + i
            put(x, y, z, 'sandstone_stairs:0')  # подъём на восток
            for yy in range(y + 1, y + 4): put(x, yy, z, 'air')
    PATH = [(x, z) for x in range(-676, -673) for z in range(1862, 1870)]
    for x, z in PATH:
        for y in range(surf(x, z) + 1, 67): put(x, y, z, 'stonebrick')
        put(x, 67, z, 'double_stone_slab:9' if z % 3 else 'sandstone:2')
    # посадочная платформа Y 68: X -676..-674, Z 1871..1875; ступени на Z 1870
    PLAT = [(x, z) for x in range(-676, -673) for z in ZK]
    for x, z in PLAT:
        for y in range(surf(x, z) + 1, 68): put(x, y, z, 'stonebrick')
        put(x, 68, z, 'double_stone_slab:9')
    for x in range(-676, -673):
        for y in range(surf(x, 1870) + 1, 68): put(x, y, 1870, 'stonebrick')
        put(x, 68, 1870, 'sandstone_stairs:2')  # подъём на юг

    # ================= 2. ПОЛОСТИ =================
    for x, z in PATH + PLAT + [(x, 1870) for x in range(-676, -673)]:
        for y in range(68 if (x, z) in PATH else 69, 72):
            if (x, y, z) not in cells: put(x, y, z, 'air')

    # ================= 3. ДЕТАЛИ: кабинки =================
    CABS = []
    for k, (dx, dy) in enumerate(cab):
        xi, yi = XC + dx, YC + dy
        c = COLORS[k]
        CABS.append((xi, yi))
        for z in ZK: put(xi, yi, z, 'dark_oak_fence')  # тяга между ободами
        for x in (xi - 1, xi, xi + 1):
            for z in ZK:
                put(x, yi - 1, z, f'wool:{c}')          # крыша
                put(x, yi - 4, z, 'quartz_block')       # пол
        for x in (xi - 1, xi, xi + 1):  # торцы - стёкла
            for z in (ZK[0], ZK[-1]):
                put(x, yi - 3, z, f'stained_glass_pane:{c}'); put(x, yi - 2, z, f'stained_glass_pane:{c}')
            put(x, yi - 3, 1872, 'spruce_stairs:3'); put(x, yi - 3, 1874, 'spruce_stairs:2')  # скамьи лицом друг к другу
        for z in (1872, 1874):
            put(xi - 1, yi - 2, z, f'stained_glass_pane:{c}'); put(xi + 1, yi - 2, z, f'stained_glass_pane:{c}')
            put(xi, yi - 2, z, 'air')
        put(xi - 1, yi - 3, 1873, 'air'); put(xi - 1, yi - 2, 1873, 'air')  # вход с запада
        put(xi, yi - 3, 1873, 'air'); put(xi, yi - 2, 1873, 'air')
        put(xi + 1, yi - 3, 1873, f'stained_glass_pane:{c}'); put(xi + 1, yi - 2, 1873, f'stained_glass_pane:{c}')

    # платформа: фонари по западным углам, ограждение с запада и юга
    LAMP = [(0, 'quartz_block:1'), (1, 'dark_oak_fence'), (2, 'dark_oak_fence'), (3, 'sea_lantern'), (4, 'stone_slab:7')]
    for z in ZK: put(-676, 69, z, 'dark_oak_fence')
    for x in (-675, -674): put(x, 69, 1875, 'dark_oak_fence')
    for z in (1871, 1875):
        for dy, b in LAMP: put(-676, 69 + dy, z, b)
    for dy, b in LAMP: put(-673, 68 + dy, 1865, b)  # фонарь у дорожки (грунт Y 67)

    # ================= выход =================
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, 'габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'записей', len(cells))
    print(Counter(cells.values()).most_common(40))

    # пересечения: кабинки не должны задевать друг друга, обод, спицы и опоры
    own = {}
    for i, (xi, yi) in enumerate(CABS):
        for x in (xi - 1, xi, xi + 1):
            for y in range(yi - 4, yi):
                for z in ZK: own.setdefault((x, y, z), []).append(i)
    clash = [k for k, v in own.items() if len(v) > 1]
    print('ПЕРЕСЕЧЕНИЯ кабинок между собой:', len(clash), clash[:5])

    # ================= ПРОВЕРКИ =================
    def final(x, y, z):
        b = cells.get((x, y, z)) or world(x, y, z)
        return 'air' if b == 'plant' else b

    def terrain_rel(x, y, z):
        b = world(x + ox, y + oy, z + oz)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)

    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('ОПОРЫ/ВОДА/ПОРЯДОК (decor_lib, по реальному порядку бота): ошибок', len(errs) + len(se), 'предупреждений', len(wr))
    for m in (errs + se)[:15]: print('  E', m)
    for m in wr[:10]: print('  W', m)

    PASS = {'air', 'carpet', 'tripwire'}

    def free(x, y, z): return final(x, y, z).split(':')[0] in PASS

    def stand(x, y, z):
        below = final(x, y - 1, z)
        return SOLID(below) and below.split(':')[0] not in PASS and free(x, y, z) and free(x, y + 1, z)

    start = (-690, 65, 1860); seen = {start}; q = deque([start])
    while q:
        x, y, z = q.popleft()
        for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, -1, 1):
                n = (x + a, y + dy, z + c)
                if n in seen or not (-700 <= n[0] <= -655 and 1846 <= n[2] <= 1880 and 60 <= n[1] <= 75): continue
                if dy == 1 and not free(x, y + 2, z): continue
                if stand(*n): seen.add(n); q.append(n)
    TARGETS = {'лестница с площади (верх)': (-676, 68, 1863), 'дорожка у опоры': (-675, 68, 1869),
               'платформа': (-675, 69, 1873), 'нижняя кабинка, вход': (-673, 69, 1873), 'нижняя кабинка, проход': (-672, 69, 1873)}
    bad = {k: v for k, v in TARGETS.items() if v not in seen}
    print('ПРОХОДИМОСТЬ: контрольных точек', len(TARGETS), 'недостижимо', len(bad), bad)
    # в каждой кабинке: две скамьи по 3 места, проход 2 блока высотой, вход открыт
    cab_ok = sum(1 for (xi, yi) in CABS if free(xi, yi - 3, 1873) and free(xi, yi - 2, 1873) and free(xi - 1, yi - 3, 1873)
                 and free(xi - 1, yi - 2, 1873) and all(free(x, yi - 2, z) for x in (xi,) for z in (1872, 1874)))
    print('КАБИНКИ: с проходом и местом над скамьями', cab_ok, 'из', len(CABS), '| мест для сидения', 6 * len(CABS))

    if args.preview:
        preview(args.preview, final, ox, oz)


def preview(path, final, ox, oz):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf',
                           '/System/Library/Fonts/Supplemental/Arial.ttf') if os.path.exists(f)), None)
    font = ImageFont.truetype(fp, 13) if fp else ImageFont.load_default()
    WOOL = {0: (235, 235, 235), 1: (230, 125, 45), 3: (105, 160, 215), 4: (230, 205, 50), 11: (50, 70, 170), 14: (170, 45, 40)}
    COL = {'water': (70, 120, 200), 'sand': (219, 207, 163), 'ground': (110, 150, 70), 'plant': (110, 150, 70), 'stonebrick': (122, 122, 122),
           'sandstone': (222, 212, 170), 'double_stone_slab': (215, 205, 165), 'quartz_block': (240, 238, 232),
           'iron_bars': (90, 90, 95), 'dark_oak_fence': (60, 40, 20), 'sea_lantern': (170, 225, 225), 'planks': (115, 85, 50),
           'stained_hardened_clay': (160, 83, 37), 'concrete': (230, 232, 233), 'leaves': (60, 130, 50), 'log': (90, 70, 40),
           'spruce_stairs': (110, 80, 50), 'sandstone_stairs': (222, 212, 170), 'stone_slab': (230, 228, 222), 'stone': (125, 125, 125)}

    def col(b):
        n, _, m = b.partition(':')
        if n in ('wool', 'stained_glass_pane'):
            c = WOOL.get(int(m or 0), (200, 200, 200))
            return c if n == 'wool' else tuple(int(v * 0.6 + 255 * 0.4) for v in c)
        return COL.get(n, (200, 120, 200))
    S = 10
    X0, X1 = -700, -652
    SKY = (200, 225, 245)
    FW = (X1 - X0 + 1) * S
    img = Image.new('RGB', (FW * 2 + 23 * S + 80, 50 * S + 40), 'white')
    dr = ImageDraw.Draw(img)

    def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)

    def elev(x0p, cols, depth, label):  # cols: список u -> (x,z)-генератор вглубь
        dr.rectangle([x0p, 20, x0p + len(cols) * S - 1, 20 + 49 * S - 1], fill=SKY)
        for u, ray in enumerate(cols):
            for y in range(52, 101):
                for i2, (x, z) in enumerate(ray):
                    b = final(x, y, z)
                    if b != 'air':
                        yy = (100 - y) * S + 20
                        dr.rectangle([x0p + u * S, yy, x0p + (u + 1) * S - 1, yy + S - 1],
                                     fill=shade(col(b), 1 - min(i2, depth) / (depth * 2.2)))
                        break
        dr.text((x0p + 4, 2), label, fill='black', font=font)
    elev(0, [[(x, z) for z in range(1885, 1845, -1)] for x in range(X0, X1 + 1)], 12,
         'фасад с моря (вид с юга), X -700..-652, Y 52..100')
    elev(FW + 20, [[(x, z) for x in range(-652, -700, -1)] for z in range(1885, 1862, -1)], 20,
         'вид с востока (юг слева)')
    bx = FW + 20 + 23 * S + 40
    for x in range(X0, X1 + 1):
        for z in range(1846, 1886):
            y = 101
            while y > 30 and final(x, y, z) == 'air': y -= 1
            c = shade(col(final(x, y, z)), 0.7 + 0.012 * (y - 60))
            dr.rectangle([bx + (x - X0) * S, 20 + (z - 1846) * S, bx + (x - X0 + 1) * S - 1, 20 + (z - 1846 + 1) * S - 1], fill=c)
    dr.text((bx + 4, 2), 'вид сверху, Z 1846..1885', fill='black', font=font)
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
