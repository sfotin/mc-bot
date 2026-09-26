"""Набережная, этап 2: мостовая, аллея, площадь, уличная мебель, сходы и зонты на пляже.
Все элементы - из docs/DECOR.md (§3 уличная мебель). Фонтан НЕ входит в эту
схему - он отдельная схема schemas/decor-fountain-13-med.json (v2, построен
на сервере и доработан вручную, см. DECOR.md §5.2); этот генератор читает
его только как часть мира (для проверок), не ставит и не трогает мостовую
под ним.

Запуск:
    gen_embankment_2.py [--site docs/terrain/site.json]
                         [--stage1 schemas/embankment-1-earthworks.json]
                         [--stage1-origin -776 56 1847]
                         [--stage1d schemas/embankment-1d-beach-rebuild.json]
                         [--stage1d-origin -756 47 1860]
                         [--fountain schemas/decor-fountain-13-med.json]
                         [--out schemas/embankment-2-promenade.json]

Читает этапы 1 и 1d как исходное состояние (опору) - строится ПОВЕРХ них.
Опоры/вода/порядок постройки проверяются decor_lib (tools/decor/) по
реальному порядку отправки команд ботом (send_order.js -> buildFillCommands).
"""
import argparse
import json
import os
import sys
from collections import Counter, deque

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

DEFAULT_SITE = os.path.join(REPO, 'docs', 'terrain', 'site.json')
DEFAULT_STAGE1 = os.path.join(REPO, 'schemas', 'embankment-1-earthworks.json')
DEFAULT_STAGE1_ORIGIN = (-776, 56, 1847)
DEFAULT_STAGE1D = os.path.join(REPO, 'schemas', 'embankment-1d-beach-rebuild.json')
DEFAULT_STAGE1D_ORIGIN = (-756, 47, 1860)
DEFAULT_FOUNTAIN = os.path.join(REPO, 'schemas', 'decor-fountain-13-med.json')
DEFAULT_OUT = os.path.join(REPO, 'schemas', 'embankment-2-promenade.json')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=DEFAULT_SITE)
    p.add_argument('--stage1', default=DEFAULT_STAGE1)
    p.add_argument('--stage1-origin', nargs=3, type=int, default=list(DEFAULT_STAGE1_ORIGIN), metavar=('X', 'Y', 'Z'))
    p.add_argument('--stage1d', default=DEFAULT_STAGE1D)
    p.add_argument('--stage1d-origin', nargs=3, type=int, default=list(DEFAULT_STAGE1D_ORIGIN), metavar=('X', 'Y', 'Z'))
    p.add_argument('--fountain', default=DEFAULT_FOUNTAIN)
    p.add_argument('--out', default=DEFAULT_OUT)
    return p.parse_args()


def main():
    args = parse_args()

    # ---------- модель мира: рельеф + этап 1 + этап 1d ----------
    d = json.load(open(args.site))
    W = d['w']; X0 = d['x0']; Z0 = d['z0']

    def G(x, z): return d['ground'][(z - Z0) * W + x - X0]

    def WA(x, z): return d['water'][(z - Z0) * W + x - X0]

    PRE = {}
    for fn, o in ((args.stage1, tuple(args.stage1_origin)), (args.stage1d, tuple(args.stage1d_origin))):
        for e in json.load(open(fn)):
            PRE[(e['x'] + o[0], e['y'] + o[1], e['z'] + o[2])] = e['block']

    def world(x, y, z):
        if (x, y, z) in PRE: return PRE[(x, y, z)]
        if y <= G(x, z): return 'ground'
        if WA(x, z) is not None and y <= WA(x, z): return 'water'
        return 'air'

    SOLID = lambda b: b not in ('air', 'water')

    def surf(x, z):
        for y in range(80, 40, -1):
            if SOLID(world(x, y, z)): return y

    # ---------- зоны покрытия (как в этапе 1) ----------
    LVL = 64

    def street(x, z): return -775 <= x <= -662 and 1850 <= z <= 1854

    def alley(x, z): return -775 <= x <= -662 and 1855 <= z <= 1859

    def plaza(x, z): return -700 <= x <= -680 and 1848 <= z <= 1868

    def deck(x, z): return -715 <= x <= -701 and 1860 <= z <= 1868

    def FP(x, z): return street(x, z) or alley(x, z) or plaza(x, z) or deck(x, z)

    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    def place(items, ox, oy, oz):
        for (x, y, z, b) in items: put(ox + x, oy + y, oz + z, b)

    def J(s): return [(e['x'], e['y'], e['z'], e['block']) for e in json.loads(s)]

    # ---------- 1. мостовая (Y 64) ----------
    FX, FZ = -690, 1858  # центр площади и фонтана
    for x in range(-776, -660):
        for z in range(1846, 1870):
            if not FP(x, z): continue
            if plaza(x, z):
                dx, dz = abs(x - FX), abs(z - FZ)
                if x in (-700, -680) or z in (1848, 1868): b = 'stonebrick'  # бортик площади
                elif max(dx, dz) == 8: b = 'double_stone_slab:8'  # кольцо вокруг фонтана
                elif dx == 0 or dz == 0: b = 'double_stone_slab:8'  # лучи от фонтана
                else: b = 'double_stone_slab:9'
            elif street(x, z):
                b = 'double_stone_slab:8'  # проезжая часть - гладкий камень
            elif alley(x, z):
                if z == 1855: b = 'stonebrick'  # бордюр улица/аллея
                elif (x + 772) % 8 == 0: b = 'double_stone_slab:8'  # поперечная полоса под фонарём
                else: b = 'sandstone:2'
            else:  # настил у стенки
                if z == 1868: b = 'stonebrick'
                elif (x + 772) % 4 == 0: b = 'double_stone_slab:8'
                else: b = 'sandstone:2'
            put(x, LVL, z, b)

    # ---------- 2. фонтан 13x13 v2 (DECOR §5.2) - отдельная схема schemas/decor-fountain-13-med.json,
    # построен на сервере и доработан вручную; этап 2 его НЕ ставит и не трогает мостовую под ним ----------
    FOUNT = set()
    for e in json.load(open(args.fountain)):
        k = (-696 + e['x'], LVL + e['y'], 1852 + e['z']); FOUNT.add(k); PRE[k] = e['block']  # фонтан - часть мира для проверок
    for k in list(cells):
        if k in FOUNT: del cells[k]

    # ---------- 3. уличная мебель (DECOR §3) ----------
    LAMP = J('[{"x":0,"y":0,"z":0,"block":"quartz_block:1"},{"x":0,"y":1,"z":0,"block":"dark_oak_fence"},{"x":0,"y":2,"z":0,"block":"dark_oak_fence"},{"x":0,"y":3,"z":0,"block":"sea_lantern"},{"x":0,"y":4,"z":0,"block":"stone_slab:7"}]')
    LAMP2 = J('[{"x":1,"y":0,"z":0,"block":"quartz_block:1"},{"x":1,"y":1,"z":0,"block":"dark_oak_fence"},{"x":1,"y":2,"z":0,"block":"dark_oak_fence"},{"x":1,"y":3,"z":0,"block":"dark_oak_fence"},{"x":0,"y":3,"z":0,"block":"dark_oak_fence"},{"x":2,"y":3,"z":0,"block":"dark_oak_fence"},{"x":1,"y":4,"z":0,"block":"stone_slab:7"},{"x":0,"y":2,"z":0,"block":"sea_lantern"},{"x":2,"y":2,"z":0,"block":"sea_lantern"}]')

    def bench_x(face):  # скамейка вдоль X; face 'S' или 'N' (DECOR §3.3)
        st = {'S': 3, 'N': 2}[face]
        return [(0, 0, 0, 'trapdoor:6'), (1, 0, 0, f'birch_stairs:{st}'), (2, 0, 0, f'birch_stairs:{st}'), (3, 0, 0, 'trapdoor:7')]

    def bench_z(face):  # скамейка вдоль Z; face 'E' или 'W'
        st = {'E': 1, 'W': 0}[face]
        return [(0, 0, 0, 'trapdoor:4'), (0, 0, 1, f'birch_stairs:{st}'), (0, 0, 2, f'birch_stairs:{st}'), (0, 0, 3, 'trapdoor:5')]

    URN = [(0, 0, 0, 'cauldron')]
    BUSH = [(0, 0, 0, 'hardened_clay'), (0, 1, 0, 'leaves:4')]

    def kadka(c):
        r = [(x, 0, z, 'hardened_clay') for x in range(c - 1, c + 2) for z in range(c - 1, c + 2)]
        r = [t for t in r if not (t[0] == c and t[2] == c)] + [(c, 0, c, 'dirt:2')]
        return r

    PALM_M = kadka(3) + [(3, y, 3, 'log:3') for y in range(1, 6)] + [(3, 6, 3, 'leaves:7'), (4, 5, 3, 'leaves:7'), (5, 5, 3, 'leaves:7'), (6, 4, 3, 'leaves:7'), (2, 5, 3, 'leaves:7'), (1, 5, 3, 'leaves:7'), (0, 4, 3, 'leaves:7'), (3, 5, 4, 'leaves:7'), (3, 5, 5, 'leaves:7'), (3, 4, 6, 'leaves:7'), (3, 5, 2, 'leaves:7'), (3, 5, 1, 'leaves:7'), (3, 4, 0, 'leaves:7'), (4, 5, 4, 'leaves:7'), (4, 5, 2, 'leaves:7'), (2, 5, 4, 'leaves:7'), (2, 5, 2, 'leaves:7')]
    PALM_T = kadka(3) + [(3, y, 3, 'log:3') for y in range(1, 8)] + [(3, 8, 3, 'leaves:7'), (4, 7, 3, 'leaves:7'), (5, 7, 3, 'leaves:7'), (6, 6, 3, 'leaves:7'), (2, 7, 3, 'leaves:7'), (1, 7, 3, 'leaves:7'), (0, 6, 3, 'leaves:7'), (3, 7, 4, 'leaves:7'), (3, 7, 5, 'leaves:7'), (3, 6, 6, 'leaves:7'), (3, 7, 2, 'leaves:7'), (3, 7, 1, 'leaves:7'), (3, 6, 0, 'leaves:7'), (4, 7, 4, 'leaves:7'), (4, 7, 2, 'leaves:7'), (2, 7, 4, 'leaves:7'), (2, 7, 2, 'leaves:7'), (3, 6, 2, 'cocoa:8'), (3, 6, 4, 'cocoa:10')]
    UMB = lambda a, b: [(1, 0, 1, 'birch_fence'), (1, 1, 1, 'birch_fence')] + [(x, 1, z, 'tripwire') for x in range(3) for z in range(3) if (x, z) != (1, 1)] + \
        [(x, 2, z, f'carpet:{a if (x + z) % 2 == 0 else b}') for x in range(3) for z in range(3)]

    F = LVL + 1  # y=0 мебели - первый блок над мостовой
    LAMPS = [x for x in range(-772, -660, 8) if not (-701 <= x <= -679)]
    STEPS = [(-746, -742), (-730, -726)]  # сходы на пляж: отрезки аллеи без скамеек
    USED = []
    for i, L in enumerate(LAMPS):
        place(LAMP, L, F, 1859)
        nxt = L + 8
        if nxt > -662 or (-701 <= nxt <= -679 and not (-701 <= L <= -679)) and nxt in range(-701, -679): pass
        b0 = L + 2
        if any(a <= b0 + 3 and b0 <= b for a, b in STEPS): continue
        if -701 <= b0 + 3 and b0 <= -679: continue  # площадь
        if b0 + 3 > -662: continue
        face = 'N' if (b0 < -751 or b0 > -680) else 'S'  # у подпорной стенки (запад, восток) - лицом к улице, иначе к морю
        place(bench_x(face), b0, F, 1859); USED.append(b0)
        if len(USED) % 2 == 0: place(URN, b0 + 4, F, 1859)
        place(BUSH, L + 4, F, 1855)  # кашпо у бордюра напротив скамейки

    # сходы на пляж: ступени из песчаника на первой клетке пляжа (Y 64, подъём на север)
    for a, b in STEPS:
        for x in range(a, b + 1):
            if surf(x, 1860) == 63: put(x, 64, 1860, 'sandstone_stairs:3')

    # пальмы: на пляже (кадка на песке, Y 64) и на настиле (Y 65); только средние/высокие - ветки выше головы
    PALMS = [(PALM_T, -748, 1862), (PALM_M, -736, 1862), (PALM_T, -721, 1862), (PALM_M, -712, 1864), (PALM_M, -704, 1864)]
    for P, cx, cz in PALMS:
        base = surf(cx, cz) + 1
        place(P, cx - 3, base, cz - 3)
        for x in range(cx - 1, cx + 2):  # кадка не должна висеть: подсыпаем песок под край до уровня base-1
            for z in range(cz - 1, cz + 2):
                for y in range(surf(x, z) + 1, base): put(x, y, z, 'sand')

    # площадь: двойные фонари по углам, скамейки лицом к фонтану, урны, кашпо
    for x, z in ((-699, 1849), (-683, 1849), (-699, 1867), (-683, 1867)): place(LAMP2, x, F, z)
    place(bench_x('N'), -698, F, 1866); place(bench_x('N'), -685, F, 1866)  # проход к пирсу X -694...-686 свободен
    place(bench_z('E'), -698, F, 1856); place(bench_z('W'), -682, F, 1856)
    for x, z in ((-694, 1866), (-686, 1866)): place(URN, x, F, z)
    for x, z in ((-699, 1851), (-681, 1851), (-699, 1865), (-681, 1865)): place(BUSH, x, F, z)

    # зонты с полотенцами на пляже (центр на сухом песке Y 63)
    UMBS = []
    for cx, cz, a, b in ((-745, 1864, 1, 4), (-740, 1862, 11, 0), (-730, 1864, 14, 0)):
        ok = all(surf(x, z) == 63 and world(x, 63, z) == 'sand' for x in range(cx - 1, cx + 2) for z in range(cz - 1, cz + 2))
        if ok:
            place(UMB(a, b), cx - 1, 64, cz - 1); UMBS.append((cx, cz))
            for dz in (0, 1):
                if surf(cx + 2, cz + dz) == 63: put(cx + 2, 64, cz + dz, 'carpet:6' if a != 11 else 'carpet:9')

    # ---------- выход ----------
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, 'габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'записей', len(cells))
    print('зонтов', len(UMBS), UMBS, 'скамеек на аллее', len(USED))
    print(Counter(cells.values()).most_common(30))

    # ---------- проверки ----------
    def final(x, y, z): return cells.get((x, y, z)) or world(x, y, z)

    def terrain_rel(x, y, z):
        b = world(x + ox, y + oy, z + oz)
        return 'stone' if b == 'ground' else b

    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('ОПОРЫ/ВОДА/ПОРЯДОК (decor_lib, по реальному порядку бота): ошибок', len(errs) + len(se), 'предупреждений', len(wr))
    for m in (errs + se)[:15]: print('  E', m)
    for m in wr[:10]: print('  W', m)

    # проходимость: ноги на Y65 над покрытием; клетка свободна, если y65 и y66 - воздух/проходимое
    PASS = {'air', 'carpet', 'tripwire', 'water'}

    def free(x, y, z): return final(x, y, z).split(':')[0] in PASS

    def stand(x, y, z):
        below = final(x, y - 1, z).split(':')[0]
        return SOLID(final(x, y - 1, z)) and below not in ('carpet', 'tripwire', 'water') and free(x, y, z) and free(x, y + 1, z) or \
            (final(x, y, z).startswith('sandstone_stairs') and free(x, y + 1, z) and free(x, y + 2, z))

    start = (-690, 65, 1850); seen = {start}; q = deque([start])
    while q:
        x, y, z = q.popleft()
        for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for dy in (0, 1, -1):
                n = (x + a, y + dy, z + c)
                if n in seen or not (-778 <= n[0] <= -658 and 1846 <= n[2] <= 1872): continue
                if stand(*n): seen.add(n); q.append(n)
    walk = [(x, z) for x in range(-776, -660) for z in range(1846, 1870) if FP(x, z) and free(x, 65, z) and free(x, 66, z)]
    unreach = [(x, z) for x, z in walk if (x, 65, z) not in seen]
    beach = [(x, z) for x in range(-750, -717) for z in range(1861, 1866) if surf(x, z) == 63 and (x, 64, z) in seen]
    print('ПРОХОДИМОСТЬ: свободных клеток покрытия', len(walk), 'недостижимо', len(unreach), unreach[:8], '| клеток пляжа, достижимых по сходам', len(beach))


if __name__ == '__main__':
    main()
