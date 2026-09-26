"""Мыс, этап 1: земляные работы (CITY.md §7.2) - выемка акватории марины и
фарватера под мостом, основание площади маяка (каменное ядро, береговая
стенка, временное покрытие Y 64).

Запуск:
    gen_cape_1.py [--out schemas/cape-1-earthworks.json]
                  [--preview docs/districts/cape-1-preview.png]

Модель мира: рельеф docs/terrain/site.json + построенные схемы набережной
(1, 1d, 2, 3, 4 и фонтан), кровля каньона - docs/terrain/caves.json.
Порядок слоёв (BOT.md §12): 1) массивы (ядро площади, стенка), 2) полости
(выемки - вода, воздух над площадью), 3) дно выемок (песок).
Правила естественного рельефа (CITY.md §6): край выемки - по шуму, уклон
откоса не круче 1 блока на блок, медиана 3x3. Выемки только поднимают воду
над дном, ничего не насыпают.
Проверки: проходимость (игрок по площади до мыса; лодка из марины через
фарватер в открытое море), опоры + вода + порядок постройки (decor_lib по
реальному порядку команд бота), кровля каньона не тоньше 3 блоков.
"""
import argparse
import json
import math
import os
import random
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
         ('embankment-3-pier-cafe.json', (-713, 48, 1869)),
         ('embankment-4-ferris-wheel.json', (-685, 62, 1862)))
SEA = 62
BASIN = (-758, -739, 1878, 1894, 56)     # акватория марины: X0, X1, Z0, Z1, дно
FAIR = (-778, -757, 1894, 1898, 57)      # фарватер под мостом
PLAZA = (-775, -763, 1884, 1892, 64)     # площадь маяка: X0, X1, Z0, Z1, уровень покрытия
RAMP = 6                                 # ширина откоса выемки, блоков
ROOF_MIN = 3                             # мин. толщина кровли над каньоном


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=os.path.join(REPO, 'docs', 'terrain', 'site.json'))
    p.add_argument('--caves', default=os.path.join(REPO, 'docs', 'terrain', 'caves.json'))
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'cape-1-earthworks.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'cape-1-preview.png'))
    return p.parse_args()


def _grid(i, j, layer):
    seed = (i * 73856093 ^ j * 19349663 ^ layer * 83492791 ^ 20260927) & 0xffffffff
    return random.Random(seed).uniform(-1, 1)


def vnoise(x, z, cell, layer):
    fx, fz = x / cell, z / cell; i, j = math.floor(fx), math.floor(fz); tx, tz = fx - i, fz - j
    sx = tx * tx * (3 - 2 * tx); sz = tz * tz * (3 - 2 * tz)
    a = _grid(i, j, layer); b = _grid(i + 1, j, layer); c = _grid(i, j + 1, layer); d = _grid(i + 1, j + 1, layer)
    return (a * (1 - sx) + b * sx) * (1 - sz) + (c * (1 - sx) + d * sx) * sz


def main():
    args = parse_args()
    d = json.load(open(args.site))
    W, X0, Z0 = d['w'], d['x0'], d['z0']
    cv = json.load(open(args.caves))

    def G(x, z): return d['ground'][(z - Z0) * W + x - X0]

    def WA(x, z): return d['water'][(z - Z0) * W + x - X0]

    def T(x, z): return d['top'][(z - Z0) * W + x - X0]

    def cave_top(x, z):  # верхняя оценка кровли каньона: minAir + air - 1 (если пустота сплошная)
        i = (z - cv['z0']) * cv['w'] + x - cv['x0']
        a, m = cv['air'][i] or 0, cv['minAir'][i]
        return m + a - 1 if a and m is not None else None

    PRE = {}
    for fn, o in BUILT:
        for e in json.load(open(os.path.join(REPO, 'schemas', fn))):
            PRE[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def world(x, y, z):
        if (x, y, z) in PRE: return PRE[(x, y, z)]
        if y <= G(x, z): return 'ground'
        if WA(x, z) is not None and y <= WA(x, z): return 'water'
        if T(x, z) is not None and G(x, z) < y <= T(x, z): return 'plant'
        return 'air'

    def SOLID(b): return b not in ('air', 'water', 'plant') and not b.startswith('flowing_water')

    def floor(x, z, fin=None):
        f = fin or world
        for y in range(90, 20, -1):
            if SOLID(f(x, y, z)): return y

    def is_sea(x, z): return world(x, SEA, z) == 'water'

    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    # ================= маски выемок с шумовым краем =================
    def in_basin(x, z):
        x0, x1, z0, z1, _ = BASIN
        return (x0 + 1.5 * vnoise(0, z, 5, 1) <= x <= x1 + 1.5 * vnoise(0, z, 5, 2) and
                z0 + 1.0 * vnoise(x, 0, 5, 3) <= z <= z1 + 1.5 * vnoise(x, 0, 5, 4))

    def in_fair(x, z):
        x0, x1, z0, z1, _ = FAIR
        return (x0 + 2.0 * vnoise(0, z, 4, 5) <= x <= x1 and z0 + 0.6 * vnoise(x, 0, 6, 6) <= z <= z1 + 0.6 * vnoise(x, 0, 6, 7))

    AREA = [(x, z) for x in range(-785, -732) for z in range(1872, 1903)]
    inside = {(x, z): (BASIN[4] if in_basin(x, z) else FAIR[4] if in_fair(x, z) else None) for x, z in AREA}
    core = [k for k, v in inside.items() if v is not None]
    # откос: цель = дно + (RAMP - расстояние до ядра), т.е. не круче 1 блока на блок
    tgt = {}
    for (x, z) in AREA:
        best = None
        for (cx, cz) in core:
            dd = max(abs(cx - x), abs(cz - z))
            if dd <= RAMP:
                v = inside[(cx, cz)] + dd
                best = v if best is None else min(best, v)
        if best is not None: tgt[(x, z)] = best
    F0 = {(x, z): floor(x, z) for (x, z) in AREA}
    # у естественного берега (не у стенки площади) откос тоже не круче 1 на 1: дно >= 62 - расстояние до суши
    px0_, px1_, pz0_, pz1_, _ = PLAZA
    LAND = [(x, z) for (x, z) in AREA if not is_sea(x, z) and not (px0_ <= x <= px1_ and pz0_ <= z <= pz1_)]
    for (x, z) in list(tgt):
        dl_ = min((max(abs(x - a), abs(z - b)) for a, b in LAND if abs(x - a) <= 6 and abs(z - b) <= 6), default=99)
        tgt[(x, z)] = max(tgt[(x, z)], SEA - dl_)
    new = {}
    for (x, z), t in tgt.items():
        if not is_sea(x, z): continue           # сушу не трогаем
        if not (PLAZA[0] - 1 <= x <= PLAZA[1] + 1 and PLAZA[2] - 1 <= z <= PLAZA[3] + 1):
            new[(x, z)] = min(F0[(x, z)], t)
    sm = {}
    for (x, z), v in new.items():  # медиана 3x3 - только вглубь, не выше исходного дна
        ring = sorted(new.get((x + a, z + b), F0.get((x + a, z + b), v)) for a in (-1, 0, 1) for b in (-1, 0, 1))
        sm[(x, z)] = min(F0[(x, z)], max(ring[4], min(v, ring[4] + 1)))
    ROOF_LIM = 0
    for (x, z), t in list(sm.items()):
        ct = cave_top(x, z)
        if ct is not None and t - ct - 1 < ROOF_MIN:
            sm[(x, z)] = min(F0[(x, z)], ct + 1 + ROOF_MIN); ROOF_LIM += 1

    # ================= 1. МАССИВЫ: площадь маяка =================
    px0, px1, pz0, pz1, PL = PLAZA

    def in_plaza(x, z): return px0 <= x <= px1 and pz0 <= z <= pz1

    WALL = set()
    for x in range(px0, px1 + 1):
        for z in range(pz0, pz1 + 1):
            f = F0.get((x, z)) or floor(x, z)
            edge = any(not in_plaza(x + a, z + b) and is_sea(x + a, z + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if edge:
                WALL.add((x, z))
                for y in range(min(f, 60), PL + 1): put(x, y, z, 'stonebrick')  # береговая стенка от дна
            else:
                for y in range(f + 1, PL): put(x, y, z, 'stone')
                put(x, PL, z, 'sandstone:2')  # временное покрытие (этап 2 заменит)
    # ================= 2. ПОЛОСТИ =================
    for x in range(px0, px1 + 1):
        for z in range(pz0, pz1 + 1):
            top = max(T(x, z) or 0, G(x, z) or 0)
            for y in range(PL + 1, max(top, PL) + 3): put(x, y, z, 'air')
    DUG = 0
    for (x, z), t in sm.items():
        f = F0[(x, z)]
        if t >= f: continue
        for y in range(t + 1, f + 1): put(x, y, z, 'water'); DUG += 1
    # ================= 3. ДНО ВЫЕМОК =================
    for (x, z), t in sm.items():
        if t < F0[(x, z)]: put(x, t, z, 'sand')

    # ================= выход =================
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, 'габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'записей', len(cells))
    print('выемка воды', DUG, '| колонн выемки', sum(1 for k, t in sm.items() if t < F0[k]),
          '| ограничено кровлей каньона', ROOF_LIM, '| клеток стенки площади', len(WALL))
    print(Counter(cells.values()).most_common(12))

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

    # игрок: по площади до мыса
    def free(x, y, z): return final(x, y, z) == 'air'

    def stand(x, y, z): return SOLID(final(x, y - 1, z)) and free(x, y, z) and free(x, y + 1, z)
    start = (-769, PL + 1, 1888); seen = {start}; q = deque([start])
    while q:
        x, y, z = q.popleft()
        for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, -1, 1):
                n = (x + a, y + dy, z + c)
                if n in seen or not (-780 <= n[0] <= -755 and 1872 <= n[2] <= 1893): continue
                if dy == 1 and not free(x, y + 2, z): continue
                if stand(*n): seen.add(n); q.append(n)
    pl_cells = [(x, z) for x in range(px0, px1 + 1) for z in range(pz0, pz1 + 1)]
    pl_bad = [c for c in pl_cells if (c[0], PL + 1, c[1]) not in seen]
    cape_ok = any((x, y, 1878) in seen for x in range(-772, -765) for y in range(63, 70))
    print('ПРОХОДИМОСТЬ (игрок): клеток площади', len(pl_cells), 'недостижимо', len(pl_bad), pl_bad[:5], '| выход на мыс (Z 1878):', cape_ok)

    # лодка: по воде глубиной >= 3 (дно <= 59) от середины марины
    def deep(x, z):
        if final(x, SEA, z) != 'water' or final(x, SEA + 1, z) != 'air': return False
        return floor(x, z, final) <= SEA - 3
    bs = (-748, 1886); bseen = {bs}; q = deque([bs])
    while q:
        x, z = q.popleft()
        for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + a, z + c)
            if n in bseen or not (-800 <= n[0] <= -730 and 1870 <= n[1] <= 1935): continue
            if deep(*n): bseen.add(n); q.append(n)
    west = any((x, z) in bseen for x in range(-800, -785) for z in range(1880, 1930))
    under_bridge = all((x, z) in bseen for x in (-768, -767, -766) for z in (1896,))
    print('ПРОХОДИМОСТЬ (лодка, глубина >=3): марина -> под мостом', under_bridge, '-> открытое море на западе', west)
    roof = [floor(x, z, final) - cave_top(x, z) - 1 for (x, z) in sm if cave_top(x, z) is not None and sm[(x, z)] < F0[(x, z)]]
    print('КРОВЛЯ КАНЬОНА под выемками: мин.', min(roof) if roof else '-', 'блоков (норма >=', ROOF_MIN, ')')

    def steep(M): return {k for k in M if any(abs(M[k] - M.get((k[0] + a, k[1] + b), M[k])) > 2 for a, b in ((1, 0), (0, 1)))}
    FIN = {k: floor(k[0], k[1], final) for k in AREA}
    near_pl = lambda k: px0 - 1 <= k[0] <= px1 + 1 and pz0 - 1 <= k[1] <= pz1 + 1  # береговая стенка площади - задумана вертикальной
    s0 = {k for k in steep(F0) if not near_pl(k)}; s1 = {k for k in steep(FIN) if not near_pl(k)}
    print('ДНО (вне стенки площади): перепад >2 между соседями - было', len(s0), 'стало', len(s1), 'новых', len(s1 - s0), sorted(s1 - s0)[:12])

    if args.preview:
        preview(args.preview, final, floor, SOLID)


def preview(path, final, floor, SOLID):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    font = ImageFont.truetype(fp, 13) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1 = -800, -730, 1860, 1912
    S = 9
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 20 + 560, max(mh + 40, 700)), 'white')
    dr = ImageDraw.Draw(img)
    COL = {'stonebrick': (122, 122, 122), 'sandstone': (222, 212, 170), 'stone': (125, 125, 125), 'quartz_block': (240, 238, 232)}
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 100
            while y > 30 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'water':
                f = floor(x, z, final); dep = min(y - f, 16)
                c = (int(150 - 7 * dep), int(195 - 7 * dep), int(235 - 3 * dep))
            else:
                n = b.split(':')[0]
                c = COL.get(n)
                if c is None:
                    k = (max(58, min(y, 72)) - 58) / 14; c = (int(215 - 45 * k), int(205 - 40 * k), int(150 - 45 * k))
            dr.rectangle([(x - X0) * S, 20 + (z - Z0) * S, (x - X0 + 1) * S - 1, 20 + (z - Z0 + 1) * S - 1], fill=c)
    dr.text((4, 2), 'вид сверху после этапа 1 (глубина — оттенком), X −800…−730, Z 1860…1912', fill='black', font=font)
    bx = mw + 20; S2 = 7

    def section(y0, label, pts):
        dr.text((bx, y0 - 16), label, fill='black', font=font)
        for u, (x, z) in enumerate(pts):
            for y in range(44, 70):
                b = final(x, y, z)
                if b == 'air': continue
                c = (70, 120, 200) if b == 'water' else (219, 207, 163) if b == 'sand' else COL.get(b.split(':')[0], (150, 140, 110))
                yy = y0 + (69 - y) * S2
                dr.rectangle([bx + u * S2, yy, bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
    section(40, 'разрез Z=1896 (фарватер под мостом), X −800…−730', [(x, -0 + 1896) for x in range(-800, -730)])
    section(40 + 220, 'разрез Z=1886 (марина и площадь маяка)', [(x, 1886) for x in range(-800, -730)])
    section(40 + 440, 'разрез X=−748 (марина, Z 1866…1912)', [(-748, z) for z in range(1866, 1913)])
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
