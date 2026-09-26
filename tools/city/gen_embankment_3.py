"""Набережная, этап 3: пирс с Т-образной головой, кафе на сваях, смягчение
южного края углубления у стенки (CITY.md §7.1).

Запуск:
    gen_embankment_3.py [--out schemas/embankment-3-pier-cafe.json]
                        [--preview docs/districts/embankment-3-preview.png]

Модель мира: рельеф docs/terrain/site.json + построенные схемы 1, 1d, 2 и
фонтан 13x13 v2 (их origin - как в BOT.md §9). Строится ПОВЕРХ них, запуск
без --prepare. Порядок слоёв (BOT.md §12): 1) дно (подсыпка/выемка),
2) сваи и балки, 3) настилы, 4) стены кафе, 5) полости (воздух), 6) детали.
Проверки: проходимость (BFS игрока 2 блока), опоры + вода + порядок постройки
(decor_lib по реальному порядку команд бота, send_order.js -> buildFillCommands).
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
         ('decor-fountain-13-med.json', (-696, 64, 1852)))
LVL = 64          # настил набережной, пирса и кафе
WATER = 62        # уровень моря


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=os.path.join(REPO, 'docs', 'terrain', 'site.json'))
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'embankment-3-pier-cafe.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'embankment-3-preview.png'))
    return p.parse_args()


def main():
    args = parse_args()
    d = json.load(open(args.site))
    W, X0, Z0 = d['w'], d['x0'], d['z0']

    def G(x, z): return d['ground'][(z - Z0) * W + x - X0]

    def WA(x, z): return d['water'][(z - Z0) * W + x - X0]

    PRE = {}
    for fn, o in BUILT:
        for e in json.load(open(os.path.join(REPO, 'schemas', fn))):
            PRE[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def world(x, y, z):
        if (x, y, z) in PRE: return PRE[(x, y, z)]
        if y <= G(x, z): return 'ground'
        if WA(x, z) is not None and y <= WA(x, z): return 'water'
        return 'air'

    def SOLID(b): return b not in ('air', 'water') and not b.startswith('flowing_water')

    def floor0(x, z):  # верх дна под водой в исходном мире
        for y in range(WATER, 30, -1):
            if SOLID(world(x, y, z)): return y

    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    # ================= 1. ДНО: смягчение южного края углубления =================
    # Углубление этапа 1: дно 57 по Z 1870..1874 с прямым краем по Z 1874 (X -700..-683).
    # Край сдвигается шумом на -2..+2 (без периодичности, затухает к концам), за краем -
    # уклон 1 блок на блок до встречи с естественным дном; затем медиана 3x3.
    SX = range(-700, -682); SZ = range(1871, 1882)

    def edge(x):
        t = (x + 700) / 17.0
        w = math.sin(math.pi * t) ** 0.7  # затухание к X -700 и -683
        n = 1.3 * math.sin(x * 0.61 + 1.7) + 0.9 * math.sin(x * 0.271 + 0.4) + 0.5 * math.sin(x * 1.37)
        return 1874 + max(-2.0, min(2.0, n * w))

    F0 = {(x, z): floor0(x, z) for x in range(-701, -681) for z in range(1870, 1883)}
    tgt = {}
    for x in SX:
        zE = edge(x)
        for z in SZ:
            t = 57 if z <= zE else 57 - 1.5 * (z - zE)
            f = F0[(x, z)]
            if z > 1874 and t > f:  # подсыпка за старым краем затухает к Z 1880 - без новых обрывов
                t = f + (t - f) * max(0.0, min(1.0, (1880 - z) / 4.0))
            tgt[(x, z)] = int(round(t)) if z <= 1874 else max(f, int(round(t)))
    sm = dict(tgt)
    for (x, z) in tgt:  # медиана 3x3 (соседи вне области - исходное дно)
        v = sorted(tgt.get((x + a, z + b), F0.get((x + a, z + b), tgt[(x, z)])) for a in (-1, 0, 1) for b in (-1, 0, 1))
        sm[(x, z)] = v[4] if z > 1871 else tgt[(x, z)]
    FL = dict(F0)
    SEA_CH = Counter()
    for (x, z), t in sm.items():
        f = F0[(x, z)]
        t = min(t, 57) if z <= 1874 else t
        if t == f: continue
        if t > f:
            for y in range(f + 1, t + 1): put(x, y, z, 'sand'); SEA_CH['подсыпка'] += 1
        else:
            put(x, t, z, 'sand')
            for y in range(t + 1, f + 1): put(x, y, z, 'water'); SEA_CH['выемка'] += 1
        FL[(x, z)] = t

    def fl(x, z): return FL.get((x, z)) or floor0(x, z)

    # ================= 2. СВАИ И БАЛКИ (stonebrick) =================
    def pile(x, z):
        for y in range(fl(x, z) + 1, LVL): put(x, y, z, 'stonebrick')

    # пирс 5x17: X -692..-688, Z 1870..1886; голова 15x5: X -697..-683, Z 1882..1886
    PX0, PX1, PZ0, PZ1 = -692, -688, 1870, 1881
    HX0, HX1, HZ0, HZ1 = -697, -683, 1882, 1886

    def on_pier(x, z): return PX0 <= x <= PX1 and PZ0 <= z <= PZ1

    def on_head(x, z): return HX0 <= x <= HX1 and HZ0 <= z <= HZ1

    LAND = [(x, z) for x in range(-692, -687) for z in (1887, 1888)]  # причал для лодок, Y 63
    GAP = range(-691, -688)  # проход с головы на причал

    def rail(x, z):  # клетка ограждения пирса/головы
        if on_pier(x, z): return x in (PX0, PX1) and z > 1869
        if on_head(x, z):
            if z == HZ0: return not (-691 <= x <= -689)
            if z == HZ1: return x not in GAP
            return x in (HX0, HX1)
        return False

    for x in range(HX0, HX1 + 1):
        for z in range(PZ0, HZ1 + 1):
            if (on_pier(x, z) or on_head(x, z)) and rail(x, z) or (on_head(x, z) and z == HZ1):
                put(x, LVL - 1, z, 'stonebrick')  # балки по краю, Y 63
    PIER_PILES = [(x, z) for x in (PX0, PX1) for z in (1874, 1878)] + \
        [(x, z) for x in (HX0, -692, -688, HX1) for z in (HZ0, HZ1)] + [(HX0, 1884), (HX1, 1884), (-692, 1888), (-688, 1888)]
    for x, z in PIER_PILES: pile(x, z)
    for x, z in LAND: put(x, LVL - 1, z, 'stonebrick')

    # кафе: X -712..-703, Z 1869..1876 (Z 1869 - стенка набережной, не трогаем); настил Z 1870..1876
    CX0, CX1, CZ0, CZ1 = -712, -703, 1870, 1876
    for x in range(CX0, CX1 + 1):
        for z in range(CZ0, CZ1 + 1):
            if x in (CX0, CX1) or z == CZ1: put(x, LVL - 1, z, 'stonebrick')
    CAFE_PILES = [(CX0, 1873), (CX0, CZ1), (-709, CZ1), (-706, CZ1), (CX1, CZ1), (CX1, 1873)]
    for x, z in CAFE_PILES: pile(x, z)

    # ================= 3. НАСТИЛЫ (Y 64) =================
    for x in range(HX0, HX1 + 1):
        for z in range(PZ0, HZ1 + 1):
            if not (on_pier(x, z) or on_head(x, z)): continue
            if rail(x, z) or (on_head(x, z) and z == HZ1): b = 'stonebrick'
            elif x == -690 or (on_head(x, z) and z == 1884): b = 'double_stone_slab:8'  # луч площади продолжается по оси пирса
            else: b = 'sandstone:2'
            put(x, LVL, z, b)
    for x in range(CX0, CX1 + 1):
        for z in range(CZ0, CZ1 + 1): put(x, LVL, z, 'planks:1')

    # ================= 4. КАФЕ: кухня-бар (белые стены, терракотовая крыша) =================
    KX0, KX1 = -712, -709  # кухня X -712..-709, Z 1870..1876, стены Y 65..68
    for x in range(KX0, KX1 + 1):
        for z in range(CZ0, CZ1 + 1):
            edge_k = x in (KX0, KX1) or z in (CZ0, CZ1)
            for y in range(LVL + 1, LVL + 5):
                if edge_k:
                    corner = x in (KX0, KX1) and z in (CZ0, CZ1)
                    put(x, y, z, 'quartz_block:2' if corner else 'concrete:0')
    for i, y in enumerate((69, 70, 71)):  # вальмовая ступенчатая крыша со свесом 1
        for x in range(KX0 - 1 + i, KX1 + 2 - i):
            for z in range(CZ0 - 1 + i, CZ1 + 2 - i): put(x, y, z, 'stained_hardened_clay:1')
    put(-711, 69, 1873, 'sea_lantern'); put(-710, 69, 1873, 'sea_lantern')  # свет в потолке

    # терраса: X -708..-703, навес из шерсти Y 68 полосами, стойки из забора
    for x in range(-708, CX1 + 1):
        for z in range(CZ0, CZ1 + 1): put(x, 68, z, 'wool:0' if x % 2 == 0 else 'wool:11')
    put(-706, 68, 1872, 'sea_lantern'); put(-705, 68, 1875, 'sea_lantern')

    # ================= 5. ПОЛОСТИ =================
    for x in range(KX0 + 1, KX1):
        for z in range(CZ0 + 1, CZ1):
            for y in range(LVL + 1, LVL + 5): put(x, y, z, 'air')
    for x in range(-708, CX1 + 1):
        for z in range(CZ0, CZ1 + 1):
            for y in range(LVL + 1, 68): put(x, y, z, 'air')
    for x in range(HX0, HX1 + 1):
        for z in range(PZ0, HZ1 + 3):
            if on_pier(x, z) or on_head(x, z) or (x, z) in LAND:
                for y in range(LVL + 1 if (x, z) not in LAND else LVL, LVL + 3):
                    if (x, y, z) not in cells: put(x, y, z, 'air')

    # ================= 6. ДЕТАЛИ =================
    LAMP = [(0, 'quartz_block:1'), (1, 'dark_oak_fence'), (2, 'dark_oak_fence'), (3, 'sea_lantern'), (4, 'stone_slab:7')]  # DECOR §3.2а
    F = LVL + 1
    LAMPS = [(PX0, 1870), (PX1, 1870), (PX0, 1878), (PX1, 1878), (HX0, HZ0), (HX1, HZ0), (HX0, HZ1), (HX1, HZ1)]
    POSTS = [(PX0, 1874), (PX1, 1874), (-692, HZ0), (-688, HZ0), (-692, HZ1), (-688, HZ1), (HX0, 1884), (HX1, 1884)]
    for x in range(HX0, HX1 + 1):
        for z in range(PZ0, HZ1 + 1):
            if rail(x, z): put(x, F, z, 'dark_oak_fence')
    for x, z in POSTS: put(x, F, z, 'quartz_block:2')
    for x, z in LAMPS:
        for dy, b in LAMP: put(x, F + dy, z, b)

    def bench_s(x0, z):  # DECOR §3.3, лицом на юг (к морю)
        for i, b in enumerate(('trapdoor:6', 'birch_stairs:3', 'birch_stairs:3', 'trapdoor:7')): put(x0 + i, F, z, b)
    bench_s(-696, 1885); bench_s(-687, 1885)
    put(-696, F, 1883, 'cauldron'); put(-684, F, 1883, 'cauldron')

    # кафе: ограждение террасы (восток, юг), стойки навеса
    for z in range(CZ0, CZ1 + 1): put(CX1, F, z, 'dark_oak_fence')
    for x in range(-708, CX1 + 1): put(x, F, CZ1, 'dark_oak_fence')
    for x, z in ((CX1, CZ0), (CX1, 1873), (CX1, CZ1), (-706, CZ1)):
        for y in (F + 1, F + 2): put(x, y, z, 'dark_oak_fence')
    # стена кухни на террасу: окно выдачи с кварцевой стойкой, дверь
    for z in (1871, 1872):
        put(KX1, F, z, 'quartz_block'); put(KX1, F + 1, z, 'air'); put(KX1, F + 2, z, 'air')
    put(KX1, F, 1874, 'wooden_door:0'); put(KX1, F + 1, 1874, 'wooden_door:8')
    for x in (-711, -710): put(x, F + 1, CZ1, 'glass_pane'); put(x, F + 2, CZ1, 'glass_pane')  # окна на море
    for z in (1872, 1873, 1874): put(KX0, F + 1, z, 'glass_pane'); put(KX0, F + 2, z, 'glass_pane')
    put(-711, F, 1871, 'furnace:5'); put(-711, F, 1872, 'cauldron'); put(-711, F, 1873, 'crafting_table')
    # столики (DECOR §2.2) и стулья (§2.3), барные табуреты у окна выдачи
    for tx, tz in ((-704, 1871), (-704, 1875), (-707, 1875)):
        put(tx, F, tz, 'fence'); put(tx, F + 1, tz, 'wooden_pressure_plate')
    for (x, z, m) in ((-705, 1871, 1), (-704, 1872, 2), (-705, 1875, 1), (-704, 1874, 3), (-708, 1875, 1), (-706, 1875, 0),
                      (-708, 1871, 0), (-708, 1872, 0)):
        put(x, F, z, f'spruce_stairs:{m}')
    # кашпо в глухой клетке проёма парапета у стены кухни (DECOR §3.5)
    put(-709, F, 1869, 'hardened_clay'); put(-709, F + 1, 1869, 'leaves:4')

    # ================= выход =================
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, 'габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'записей', len(cells))
    print('дно:', dict(SEA_CH))
    print(Counter(cells.values()).most_common(40))

    # ================= ПРОВЕРКИ =================
    def final(x, y, z): return cells.get((x, y, z)) or world(x, y, z)

    def terrain_rel(x, y, z):
        b = world(x + ox, y + oy, z + oz)
        return 'stone' if b == 'ground' else b

    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('ОПОРЫ/ВОДА/ПОРЯДОК (decor_lib, по реальному порядку бота): ошибок', len(errs) + len(se), 'предупреждений', len(wr))
    for m in (errs + se)[:15]: print('  E', m)
    for m in wr[:10]: print('  W', m)

    PASS = {'air', 'carpet', 'tripwire', 'wooden_door'}

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
                if n in seen or not (-720 <= n[0] <= -678 and 1846 <= n[2] <= 1892 and 60 <= n[1] <= 70): continue
                if dy == 1 and not free(x, y + 2, z): continue  # прыжок: над головой свободно
                if stand(*n): seen.add(n); q.append(n)
    TARGETS = {'голова пирса': (-690, 65, 1884), 'угол головы W': (-695, 65, 1883), 'угол головы E': (-684, 65, 1884),
               'причал': (-690, 64, 1888), 'терраса кафе': (-705, 65, 1873), 'кухня кафе': (-710, 65, 1872),
               'столик у юж. ограды': (-708, 65, 1874)}
    bad = {k: v for k, v in TARGETS.items() if v not in seen}
    walk = [(x, z) for x in range(HX0, HX1 + 1) for z in range(PZ0, HZ1 + 1)
            if (on_pier(x, z) or on_head(x, z)) and free(x, 65, z) and free(x, 66, z)]
    unreach = [c for c in walk if (c[0], 65, c[1]) not in seen]
    print('ПРОХОДИМОСТЬ: контрольных точек', len(TARGETS), 'недостижимо', len(bad), bad,
          '| свободных клеток пирса', len(walk), 'недостижимо', len(unreach), unreach[:6])
    def steep(M): return {(x, z) for (x, z) in sm if any(abs(M[(x, z)] - M.get((x + a, z + b), M[(x, z)])) > 2
                                                        for a, b in ((1, 0), (0, 1)))}
    s0, s1 = steep(F0), steep(FL)
    print('ДНО: перепад >2 между соседями - было', len(s0), 'стало', len(s1), 'новых', sorted(s1 - s0)[:6])

    if args.preview:
        preview(args.preview, final, SOLID, sm, FL, ox, oz)


def preview(path, final, SOLID, sm, FL, ox, oz):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf',
                           '/System/Library/Fonts/Supplemental/Arial.ttf') if os.path.exists(f)), None)
    font = ImageFont.truetype(fp, 13) if fp else ImageFont.load_default()
    COL = {'water': (70, 120, 200), 'sand': (219, 207, 163), 'ground': (150, 140, 110), 'stonebrick': (122, 122, 122),
           'sandstone': (222, 212, 170), 'double_stone_slab': (190, 190, 190), 'quartz_block': (240, 238, 232),
           'planks': (115, 85, 50), 'wool': (240, 240, 240), 'concrete': (230, 232, 233), 'stained_hardened_clay': (160, 83, 37),
           'dark_oak_fence': (60, 40, 20), 'sea_lantern': (170, 220, 220), 'leaves': (60, 130, 50), 'log': (90, 70, 40),
           'hardened_clay': (150, 90, 65), 'stone_slab': (230, 228, 222), 'birch_stairs': (200, 185, 130), 'stone': (125, 125, 125)}

    def col(b):
        n, _, m = b.partition(':')
        if n == 'wool' and m == '11': return (50, 70, 170)
        return COL.get(n, (200, 120, 200))
    X0, X1, Z0, Z1 = -720, -676, 1846, 1893
    S = 12
    top_h = (Z1 - Z0 + 1) * S
    sec_h = 26 * S
    img = Image.new('RGB', ((X1 - X0 + 1) * S + 20 + 48 * 7, 3 * 250 + 20), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 80
            while y > 30 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z); c = col(b)
            if b == 'water':
                yb = y
                while yb > 30 and final(x, yb, z) == 'water': yb -= 1
                dep = y - yb; c = tuple(int(v * (1 - min(dep, 15) / 25)) for v in c)
            else:
                k = 0.75 + 0.03 * (y - 60); c = tuple(max(0, min(255, int(v * k))) for v in c)
            dr.rectangle([(x - X0) * S, (z - Z0) * S, (x - X0 + 1) * S - 1, (z - Z0 + 1) * S - 1], fill=c)
    dr.text((4, top_h + 4), 'вид сверху: X -720..-676, Z 1846..1893 (север вверху)', fill='black', font=font)
    # разрезы справа: по оси пирса X=-690 (Z по горизонтали) и по кафе Z=1873 (X по горизонтали)
    bx = (X1 - X0 + 1) * S + 20
    S2 = 7

    def section(y0, label, cells_iter):
        for (u, y, b) in cells_iter:
            if b == 'air': continue
            yy = y0 + (76 - y) * S2
            dr.rectangle([bx + u * S2, yy, bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=col(b))
        dr.text((bx, y0 - 14), label, fill='black', font=font)
    section(20, 'разрез X=-690 (ось пирса, юг справа)',
            [(z - 1846, y, final(-690, y, z)) for z in range(1846, 1894) for y in range(46, 77)])
    section(20 + 250, 'разрез Z=1873 (кафе, восток справа)',
            [(x + 720, y, final(x, y, 1873)) for x in range(-720, -675) for y in range(46, 77)])
    section(20 + 500, 'разрез Z=1884 (голова пирса)',
            [(x + 720, y, final(x, y, 1884)) for x in range(-720, -675) for y in range(46, 77)])
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
