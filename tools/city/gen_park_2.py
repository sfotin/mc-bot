"""Парк + зоопарк, этап 2 — зоопарк (CITY.md §7.5, план v1 — tools/city/plan_park_v1.py, геометрия оттуда).

Схема park-2-zoo.json:
- аллеи зоопарка (главная X −648…−646 от «зебры» Горной дороги, поперечная Z 1755…1756, к смотровой
  над ламами X −636…−634), мощение — грубая земля и андезит, шаг 0.5, подсветка — морские фонари
  в мощении; входная арка и касса (city_lib.Tower);
- вольеры: Белые медведи (снег, лёд, бассейн, иглу; парапет из каменного кирпича с решёткой),
  Волки (подзол, ели, валун; еловый забор), Тропический купол (стеклянный купол над джунглями
  с прудом — оцелоты, попугаи), Контактный зоопарк (амбар с двускатной кровлей и электрощитовой
  3×3 с кабельной шахтой — на весь зоопарк; загон с сеном и поилкой), Ламы (естественный склон
  горы F, валуны, навес; забор по рельефу — не ниже соседнего грунта);
- в каждом вольере — калитка на аллею, подсветка в полу (мобы не спавнятся); животных ставит игрок.

Запуск: gen_park_2.py [--out schemas/park-2-zoo.json] [--preview docs/districts/park-2-preview.png]
Мир — World() (после постройки — built_before('park-2-zoo.json')).
Проверки: опоры + вода + порядок, вода, перепад мощения, проходимость без прыжков от «зебры»
до каждой клетки аллей, кассы, амбара и щитовой; подходы к дверям, скамейки, висящие, кровля
каньона; вольеры — «животное» (прыжок на 1 блок) не выходит за ограду, забор не ниже соседнего
грунта; негативные прогоны.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import (World, REPO, BUILT, built_before, Tower, path_heights, save_schema, DOOR_IN, N4, dl,  # noqa: E402
                      door_approach_issues, floating_over_paving, col, CL)
from gen_park_1 import Sch, pave, item_y, bench, h32, rect  # noqa: E402
import plan_park_v1 as P  # noqa: E402

NAME = 'park-2-zoo.json'
OBJ = {k: (x0, x1, z0, z1) for k, _, x0, x1, z0, z1, st, *_ in P.OBJ if st == 2}
N8 = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', NAME))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'park-2-preview.png'))
    return p.parse_args()


def perim(cells):
    return {c for c in cells if any((c[0] + a, c[1] + b) not in cells for a, b in N4)}


def build(W):
    S = Sch(W)
    paths = set()
    for k, x0, x1, z0, z1, st in P.PATHS:
        if st == 2: paths |= rect(x0, x1, z0, z1)
    bears = rect(*OBJ['bear'])
    wolves = rect(-655, -652, 1757, 1767)
    kiosk = rect(-651, -649, 1764, 1768)
    dome_box = rect(*OBJ['dome'])
    DC, DR = (-641, 1749), 4.3
    dome = {c for c in dome_box if math.hypot(c[0] - DC[0], c[1] - DC[1]) <= DR}
    barn = rect(-645, -638, 1761, 1767)
    paddock = rect(-645, -634, 1757, 1760) | rect(-637, -634, 1761, 1767)
    llama = rect(*OBJ['llama'])
    # ---- аллеи: высоты — к краю дороги и Парковой ул. (построено), пороги дверей
    fixed = {(-648, 1766): 65.0, (-646, 1765): 65.0}
    H, anchors, bad = path_heights(W, paths | set(fixed), fixed)
    lit = 0
    for c in sorted(paths):
        full = 'stone:5' if h32(*c, 7) < 0.3 else 'dirt:1'
        if H[c] == int(H[c]) and (c[0] * 3 + c[1] * 7) % 11 == 0 and c not in fixed: full = 'sea_lantern'; lit += 1
        pave(S, c[0], c[1], H[c], full, 'stone_slab:3')
    ptop = {c: math.ceil(H[c]) - 1 for c in paths}
    lights = []                                          # подсветка в полу вольеров

    def flat(cells, top, surface):
        for (x, z) in cells:
            g = W.surf(x, z)
            for y in range(g + 1, top): S.put(x, y, z, 'stone')
            S.put(x, top, z, surface(x, z) if callable(surface) else surface)
            for y in range(top + 1, max(S.plant_top(x, z), g) + 1): S.put(x, y, z, 'air')

    # ---- Белые медведи: пол вровень с аллеей, парапет с решёткой, бассейн, иглу
    Lb = ptop[(-648, 1750)]
    pool = rect(-654, -651, 1746, 1748)
    ice = lambda x, z: 'packed_ice' if h32(x, z, 3) < 0.25 else 'snow'
    flat(bears, Lb, ice)
    for (x, z) in pool:
        S.put(x, Lb - 2, z, 'packed_ice'); S.put(x, Lb - 1, z, 'water'); S.put(x, Lb, z, 'water')
        if W.surf(x, z) < Lb - 2: [S.put(x, y, z, 'stone') for y in range(W.surf(x, z) + 1, Lb - 2)]
    bp = perim(bears)
    for (x, z) in bp:
        S.put(x, Lb, z, 'stonebrick'); S.put(x, Lb + 1, z, 'stonebrick'); S.put(x, Lb + 2, z, 'iron_bars')
    for (x, z) in rect(-653, -651, 1751, 1753):          # иглу, вход с севера
        if (x, z) != (-652, 1752):
            for y in (Lb + 1, Lb + 2): S.put(x, y, z, 'snow')
        S.put(x, Lb + 3, z, 'snow')
    S.put(-652, Lb + 1, 1751, 'air'); S.put(-652, Lb + 2, 1751, 'air')
    for (x, z) in ((-650, 1746), (-650, 1752), (-654, 1750)): S.put(x, Lb, z, 'sea_lantern'); lights.append((x, z))
    S.put(-649, Lb + 1, 1751, 'spruce_fence_gate:3'); S.put(-649, Lb + 2, 1751, 'air')     # калитка на аллею
    # ---- Волки: подзол, ели, валун; еловый забор по рельефу
    for (x, z) in wolves:
        g = W.surf(x, z)
        S.put(x, g, z, 'dirt:2')
        for y in range(g + 1, S.plant_top(x, z) + 1): S.put(x, y, z, 'air')
    for (x, z) in ((-654, 1760), (-653, 1765)):
        g = W.surf(x, z)
        for i in range(5): S.put(x, g + 1 + i, z, 'log:1')
        for dy, r in ((3, 1), (4, 1), (5, 0), (6, 0)):
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    if (x + a, z + b) in wolves and (a, b) != (0, 0) or (a, b) == (0, 0) and dy >= 5:
                        S.c.setdefault((x + a, g + dy, z + b), 'leaves:5')
        S.put(x, g + 7, z, 'leaves:5')
    for (x, z) in ((-654, 1762), (-653, 1762)): S.put(x, W.surf(x, z) + 1, z, 'mossy_cobblestone')
    for (x, z) in ((-653, 1758), (-654, 1766)): S.put(x, W.surf(x, z), z, 'sea_lantern'); lights.append((x, z))
    # ---- Тропический купол: пол вровень с аллеей, стекло, джунгли, пруд
    Ld = ptop[(-646, 1749)]
    flat(dome_box, Ld, 'grass')
    DH = 6.5
    for dy in range(1, 8):
        rr = DR * math.sqrt(max(0.0, 1 - (dy / DH) ** 2))
        ring = {c for c in dome if math.hypot(c[0] - DC[0], c[1] - DC[1]) <= rr + 0.01}
        for c in dome:
            if c in ring:
                shell = any((c[0] + a, c[1] + b) not in ring for a, b in N4) or dy == 7 or \
                    math.hypot(c[0] - DC[0], c[1] - DC[1]) > DR * math.sqrt(max(0.0, 1 - ((dy + 1) / DH) ** 2))
                b = ('sea_lantern' if c == DC else 'glass') if shell else 'air'
                if shell and (c[0] == DC[0] or c[1] == DC[1]) and b == 'glass': b = 'stained_glass:5'
                S.put(c[0], Ld + dy, c[1], b)
    for c in dome_box - dome:
        for y in range(Ld + 1, Ld + 8): S.c.setdefault((c[0], y, c[1]), 'air')
    for (x, z) in dome:
        if (x, z) in ((-643, 1751), (-640, 1747), (-639, 1751), (-643, 1747)): continue
        S.put(x, Ld, z, 'dirt:2' if h32(x, z, 5) < 0.3 else 'grass')
    for (x, z) in rect(-640, -639, 1746, 1747):
        S.put(x, Ld - 1, z, 'dirt'); S.put(x, Ld, z, 'water')
    for (x, z) in ((-643, 1751), (-643, 1747)):
        S.put(x, Ld, z, 'dirt')
        for i in range(1, 4): S.put(x, Ld + i, z, 'log:3')
        for (a, b) in [(0, 0)] + list(N4):
            S.put(x + a, Ld + 4, z + b, 'leaves:7')
        for (a, b) in N4: S.c.setdefault((x + a, Ld + 3, z + b), 'leaves:7')
    S.put(-639, Ld, 1751, 'sea_lantern'); S.put(-641, Ld, 1752, 'sea_lantern'); lights += [(-639, 1751), (-641, 1752)]
    # ---- Касса: киоск у арки (city_lib.Tower), арка над главной аллеей
    kt = Tower(W, 'Касса зоопарка', lambda x, y, z: (x, z) in kiosk, (-651, -649, 1764, 1768), 64, 69, band='concrete:0',
               lobby='quartz_block', glass_fn=lambda x, y, z: 'concrete:0' if y in (65, 68) else 'stained_glass:5')
    kt.shell(); kt.door(-649, 1766, 2)
    ya = max(H[(x, 1768)] for x in (-648, -647, -646))
    ay = int(ya) + 4
    g = W.surf(-645, 1768)
    for y in range(g + 1, ay): S.put(-645, y, 1768, 'planks:5')
    for x in range(-649, -644): S.put(x, ay, 1768, 'planks:5'); S.put(x, ay + 1, 1768, 'wooden_slab:5')
    S.put(-647, ay + 1, 1768, 'planks:5'); S.put(-647, ay + 2, 1768, 'wooden_slab:5')
    S.put(-647, ay - 1, 1768, 'sea_lantern')
    for y in range(int(ya), ay - 1): S.c.setdefault((-647, y, 1768), 'air')
    # ---- Контактный зоопарк: амбар (щитовая зоопарка), загон
    bt = Tower(W, 'Амбар', lambda x, y, z: (x, z) in barn, (-645, -638, 1761, 1767), 64, 69, band='planks:5',
               lobby='cobblestone', glass_fn=lambda x, y, z: 'planks:1' if y in (65, 68) or (x + z) % 3 else 'glass')
    bt.shell(); bt.door(-645, 1765, 0)
    bt.room('электрощитовая', (-641, -639, 1764, 1766), (-642, 1765, 0), shaft=(-639, 1766))
    for i in range(4):                                    # двускатная кровля, конёк вдоль X
        for x in range(-645, -637):
            for z, m in ((1761 + i, 2), (1767 - i, 3)):
                bt.put(x, 70 + i, z, 'wooden_slab:5' if 1761 + i == 1767 - i else f'brick_stairs:{m}')
        for x in (-645, -638):
            for z in range(1762 + i, 1767 - i): bt.put(x, 70 + i, z, 'planks:5')
    for T in (kt, bt):
        T.plan_ladders()
        for k, b in T.cells.items(): S.put(*k, b)
    for (x, z) in paddock:
        g = W.surf(x, z)
        S.put(x, g, z, 'grass')
        for y in range(g + 1, S.plant_top(x, z) + 1): S.put(x, y, z, 'air')
    pp = {c for c in paddock if any((c[0] + a, c[1] + b) not in paddock and (c[0] + a, c[1] + b) not in barn for a, b in N4)}
    for (x, z) in ((-642, 1759), (-643, 1759)): S.put(x, W.surf(x, z) + 1, z, 'hay_block')
    S.put(-636, W.surf(-636, 1764) + 1, 1764, 'cauldron:3')
    for (x, z) in ((-640, 1758), (-635, 1762), (-635, 1766)): S.put(x, W.surf(x, z), z, 'sea_lantern'); lights.append((x, z))
    # ---- Ламы: склон горы F как есть (деревья сняты), валуны, навес
    med = lambda x, z: sorted(W.surf(x + a, z + b) for a in range(-2, 3) for b in range(-2, 3))[12]
    lg = {}
    for (x, z) in rect(-634, -625, 1744, 1768):
        m = med(x, z); g = W.surf(x, z)
        if g - m > 4 and (x, z) in llama:                # крона/ствол дерева на склоне — снять
            for y in range(m + 1, g + 1): S.put(x, y, z, 'air')
            S.put(x, m, z, 'grass'); lg[(x, z)] = m
        else: lg[(x, z)] = g
    for (x, z) in ((-630, 1750), (-629, 1757), (-631, 1763)):
        S.put(x, lg[(x, z)] + 1, z, 'stone:5'); S.put(x + 1, lg[(x + 1, z)] + 1, z, 'stone:5')
    sx, sz = -628, 1747                                  # навес: столбы и крыша
    top = max(lg[(x, z)] for x in (sx, sx + 1) for z in (sz, sz + 1)) + 3
    for (x, z) in ((sx, sz), (sx + 1, sz), (sx, sz + 1), (sx + 1, sz + 1)):
        for y in range(lg[(x, z)] + 1, top): S.put(x, y, z, 'spruce_fence')
    for x in range(sx - 1, sx + 3):
        for z in range(sz - 1, sz + 3): S.put(x, top, z, 'wooden_slab:1')
    for (x, z) in ((-631, 1747), (-630, 1754), (-628, 1760), (-631, 1766), (-627, 1765)):
        S.put(x, lg[(x, z)], z, 'sea_lantern'); lights.append((x, z))
    # ---- ограды по рельефу: верх забора не ниже грунта соседних клеток (иначе перепрыгнут)
    fences = {}

    def fence_ring(cells, ground, mat):
        for (x, z) in perim(cells):
            y0 = ground(x, z) + 1
            nb = [ground(x + a, z + b) for a, b in N8]
            y1 = max([ground(x, z)] + nb) + 1
            for y in range(y0, y1 + 1): S.put(x, y, z, mat)
            fences[(x, z)] = (y0, y1)
    gw = lambda x, z: math.ceil(H[(x, z)]) - 1 if (x, z) in H else (lg.get((x, z)) or W.surf(x, z))
    fence_ring(wolves, gw, 'spruce_fence')
    S.put(-654, gw(-654, 1757) + 1, 1757, 'spruce_fence_gate:2')
    fence_ring(llama, gw, 'fence')
    S.put(-633, gw(-633, 1750) + 1, 1750, 'fence_gate:1')
    for (x, z) in pp:
        y0 = gw(x, z) + 1
        y1 = max([gw(x, z)] + [gw(x + a, z + b) for a, b in N8 if (x + a, z + b) not in barn]) + 1
        for y in range(y0, y1 + 1): S.put(x, y, z, 'fence')
        fences[(x, z)] = (y0, y1)
    S.put(-640, gw(-640, 1757) + 1, 1757, 'fence_gate:2')
    # ---- газоны и откосы 1:1 у аллей, деревья, скамейки
    zoo = rect(-655, -626, 1745, 1768)
    busy = paths | bears | wolves | kiosk | dome_box | barn | paddock | llama | {(-645, 1768)}
    lawn = {}
    for c in sorted(zoo - busy):
        x, z = c
        g = W.surf(x, z)
        lo, hi = -1e9, 1e9
        for a in range(-3, 4):
            for b in range(-3, 4):
                n = (x + a, z + b); d = max(abs(a), abs(b))
                if n in ptop: lo, hi = max(lo, ptop[n] - d), min(hi, ptop[n] + d)
        if lo == -1e9: lawn[c] = g; continue
        lvl = int(min(max(g, lo), hi) if lo <= hi else math.floor(hi))
        if lvl != g:
            for y in range(g + 1, lvl): S.put(x, y, z, 'stone')
            S.put(x, lvl, z, 'grass')
            for y in range(lvl + 1, max(S.plant_top(x, z), g) + 1): S.put(x, y, z, 'air')
        lawn[c] = lvl
    trees = []
    for c in sorted(lawn, key=lambda c: h32(*c, 21)):
        x, z = c
        if any((x + a, z + b) in busy for a in (-1, 0, 1) for b in (-1, 0, 1)): continue
        if any(abs(x - t[0]) + abs(z - t[1]) < 4 for t in trees): continue
        y = lawn[c] + 1
        for i in range(4): S.put(x, y + i, z, 'log:2')
        for dy in (2, 3):
            for a, b in N8: S.c.setdefault((x + a, y + dy, z + b), 'leaves:6')
        for a, b in [(0, 0)] + list(N4): S.c.setdefault((x + a, y + 4, z + b), 'leaves:6')
        trees.append(c)
    benches = []

    def add_bench(x, z, face):
        cells = [(x + i, z) for i in range(4)] if face in ('n', 's') else [(x, z + i) for i in range(4)]
        d = {'n': (0, -1), 's': (0, 1), 'e': (1, 0), 'w': (-1, 0)}[face]
        front = [(c[0] + d[0], c[1] + d[1]) for c in cells[1:3]]
        if any(c not in H for c in cells + front) or len({H[c] for c in cells + front}) > 1: return False
        y = item_y(S, H, *cells[0], 'stone:5')
        for c in cells[1:]: item_y(S, H, *c, 'stone:5')
        bench(S, x, y, z, face); benches.append((x, z, face)); return True
    for z in range(1749, 1755):                          # у купола — лицом к медведям
        if add_bench(-646, z, 'w'): break
    for x in range(-655, -648):                          # у волков — лицом к аллее
        if add_bench(x, 1756, 'n'): break
    for z in list(range(1745, 1752)) + list(range(1745, 1752)):   # смотровая над ламами — лицом к склону
        if add_bench(-636, z, 'e') or add_bench(-634, z, 'w'): break
    for (x, z) in ((-646, 1754), (-648, 1757)): S.put(x, item_y(S, H, x, z, 'stone:5'), z, 'cauldron')
    E = dict(bears=bears, wolves=wolves, dome=dome, paddock=paddock, llama=llama)
    return dict(S=S, H=H, paths=paths, bad=bad, towers=[kt, bt], E=E, fences=fences, lights=lights, lit=lit,
                trees=trees, benches=benches, lg=lg, Lb=Lb, Ld=Ld, gw=gw)


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAME)) if NAME in names else World()
    R = build(W)
    S, H, paths = R['S'], R['H'], R['paths']
    o, rel, order, dims = save_schema(S.c, args.out)
    print(f'{NAME}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(S.c)}')
    print(f'аллеи {len(paths)} кл., покрытие Y {min(H[c] for c in paths)}…{max(H[c] for c in paths)}, подсветка в мощении {R["lit"]}, '
          f'в вольерах {len(R["lights"])}; деревьев {len(R["trees"])}, скамеек {len(R["benches"])}; пол медведей Y {R["Lb"]}, купола Y {R["Ld"]}')
    print('== ПРОВЕРКИ ==')

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(S.c)
    terr = lambda x, y, z: (lambda b: 'stone' if b == 'ground' else ('air' if b == 'plant' else b))(W.block(x + o[0], y + o[1], z + o[2]))
    errs = dl.check_water(rel, terr)
    se, wr = dl.check_supports(rel, order, terr)
    print(f'{NAME}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
    for m in (errs + se + wr)[:6]: print('   ', m)
    be = dl.check_bench_front(rel, terr)
    print(f'{NAME}: скамейки (место для ног): ошибок {len(be)}', be[:3])
    leak = [(x + a, y, z + c) for (x, y, z), b in S.c.items() if b == 'air' for a, c in N4
            if (x + a, y, z + c) not in S.c and W.block(x + a, y, z + c) == 'water']
    print('вода рельефа, открытая в воздух схемы:', len(leak), leak[:4])
    jump = [(c, n) for c in paths for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if n in paths and abs(H[c] - H[n]) > 0.5]
    print('перепад покрытия между соседями > 0.5 —', len(jump) + len(R['bad']), (jump + R['bad'])[:3])
    fl = floating_over_paving(final, S.c, {c: H[c] for c in paths})
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:4])
    digs = {}
    for (x, y, z), b in S.c.items():
        if b in ('air', 'water') and y <= W.surf(x, z): digs[(x, z)] = min(digs.get((x, z), 999), y)
    roofs = [(y - W.cave_top(x, z) - 1, x, z) for (x, z), y in digs.items() if W.cave_top(x, z) is not None and W.cave_top(x, z) < y]
    print('кровля каньона под выемками схемы: мин.', min(roofs)[0] if roofs else '—', '(норма >= 3)')
    doors = [d for T in R['towers'] for d in T.doors]
    di = door_approach_issues(final, doors)
    print(f'подходы к наружным дверям: {len(doors)}, ошибок {len(di)}', di[:2])
    # проходимость посетителя — от «зебры», по аллеям, дороге, Парковой ул. и зданиям
    walkable = paths | rect(-660, -625, 1769, 1773) | rect(-660, -656, 1745, 1768) | \
        {c for T in R['towers'] for c in T.FP[0]} | {(-645, 1768)} - {(-645, 1768)}
    box = ((-661, -624), (1743, 1774), (58, 95))

    def walk(fin, start=(-647, 64.5, 1771), allow=walkable, bx=box, step=0.5):
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in allow else ('stone' if y < 60 else 'air')
        return dl.walk_reachable(f2, start, *bx, max_step=step)
    seen = walk(final)
    occ = {(x, z) for (x, y, z), b in S.c.items() if (x, z) in paths and b != 'air' and y >= math.ceil(H[(x, z)])}
    miss = [c for c in paths if c not in occ and not dl.reached(seen, c[0], H[c], c[1])]
    print(f'ПРОХОДИМОСТЬ без прыжков от «зебры» (−647,1771): клеток аллей {len(paths) - len(occ)}, недостижимо {len(miss)}', miss[:6])
    targets = {}
    for T in R['towers']:
        targets.update(T.level_targets()); targets.update({f'{T.name}: {k}': v for k, v in T.targets.items()})
        for (x, y, z, m) in T.doors:
            a, b = DOOR_IN[m]; targets[f'{T.name}: перед дверью ({x},{z})'] = (x - a, y, z - b)
    targets['смотровая над ламами (−635,1745)'] = (-635, H[(-635, 1745)], 1745)
    targets['у волков, запад поперечной (−655,1755)'] = (-655, H[(-655, 1755)], 1755)
    bad_t = 0
    for k, (x, y, z) in targets.items():
        ok = dl.reached(seen, x, y, z); bad_t += 0 if ok else 1
        print(f'  маршрут → {k}: {ok}')
    print('ИТОГО недостижимых точек:', len(miss) + bad_t)
    # вольеры: «животное» прыгает на 1 блок, от середины вольера — не выходит за его клетки
    starts = {'bears': (-651, R['Lb'] + 1.0, 1750), 'wolves': (-654, None, 1763), 'dome': (-641, R['Ld'] + 1.0, 1750),
              'paddock': (-641, None, 1758), 'llama': (-629, None, 1752)}

    def escape(fin, k, ret=False):
        cells = R['E'][k]
        xs = [c[0] for c in cells]; zs = [c[1] for c in cells]
        bx = ((min(xs) - 2, max(xs) + 2), (min(zs) - 2, max(zs) + 2), (55, 110))
        s = set()
        pts = [starts[k]] + [(x, None, z) for (x, z) in sorted(cells - perim(cells)) if (x + 2 * z) % 3 == 0] if k in ('llama', 'paddock') else [starts[k]]
        for x, y, z in pts:
            if any(a == x and b == z for a, b, h in s): continue
            if y is None: y = R['gw'](x, z) + 1.0
            s |= dl.walk_reachable(fin, (x, y, z), *bx, max_step=1.0)
        n, out = len(s), sum(1 for (a, b, h) in s if (a, b) not in cells)
        return (n, out, s) if ret else (n, out)
    esc = 0
    for k in starts:
        n, out = escape(final, k); esc += out
        print(f'  вольер {k}: стоянок внутри {n}, снаружи {out}')
    low = [c for c, (y0, y1) in R['fences'].items()
           if y1 < max(R['gw'](c[0] + a, c[1] + b) for a, b in N8) + 1]
    print('вольеры: выход животного за ограду —', esc, '| забор ниже соседнего грунта:', len(low), low[:3])
    if esc + len(low): print('ИТОГО недостижимых точек:', esc + len(low))
    # негатив 1: без звена забора ламы уходят (звено у достижимой ламами клетки, наружу — не круче 1 блока)
    _, _, sl = escape(final, 'llama', True)
    reach = {(a, b) for a, b, h in sl}
    gw = R['gw']
    c = next(c for c in sorted(R['fences']) if c in perim(R['E']['llama']) and any(
        (c[0] + a, c[1] + b) in reach for a, b in N4) and any((c[0] + a, c[1] + b) not in R['E']['llama'] and
        abs(gw(c[0] + a, c[1] + b) - gw(*c)) <= 1 for a, b in N4))
    negc = dict(S.c)
    y0, y1 = R['fences'][c]
    for y in range(y0, y1 + 1): negc[(c[0], y, c[1])] = 'air'
    print('НЕГАТИВ: без звена забора ламы выходят:', escape(fin_of(negc), 'llama')[1] > 0)
    # негатив 2: калитка медведей открыта (проход вместо ограды) — медведи выходят
    negc = dict(S.c); negc[(-649, R['Lb'] + 1, 1751)] = 'air'
    print('НЕГАТИВ: проход в парапете — медведи выходят:', escape(fin_of(negc), 'bears')[1] > 0)
    # негатив 3: ступень 1 блок поперёк главной аллеи — амбар недостижим
    negc = dict(S.c)
    for d in (0, 1):
        for x in (-648, -647, -646): negc[(x, int(H[(x, 1767)]) + d, 1767)] = 'stonebrick'
        for z in (1755, 1756): negc[(-654, int(H[(-654, z)]) + d, z)] = 'stonebrick'
    print('НЕГАТИВ: стенки поперёк главной и поперечной аллей — дверь амбара недостижима:',
          not dl.reached(walk(fin_of(negc)), -646, 65.0, 1765))
    # негатив 4: газон перед дверью кассы — ошибка подхода
    negc = dict(S.c); negc[(-648, 64, 1766)] = 'grass'
    print('НЕГАТИВ: газон перед дверью кассы — ошибка подхода найдена:', len(door_approach_issues(fin_of(negc), doors)) > 0)
    if args.preview: preview(args.preview, final, R, W)


def preview(path, final, R, W):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CX = dict(CL); CX.update({'dirt:1': (130, 95, 65), 'stone:5': (130, 130, 130), 'snow': (245, 250, 250), 'packed_ice': (160, 190, 240),
                              'water': (70, 130, 215), 'grass': (95, 150, 60), 'dirt:2': (90, 65, 40), 'glass': (200, 230, 240),
                              'stained_glass:5': (130, 200, 80), 'leaves:5': (40, 80, 50), 'leaves:6': (110, 150, 60),
                              'leaves:7': (60, 140, 40), 'brick_stairs': (150, 70, 60), 'hay_block': (210, 180, 60),
                              'fence': (150, 120, 80), 'spruce_fence': (90, 65, 40), 'iron_bars': (120, 120, 120),
                              'concrete:0': (235, 235, 235), 'stained_glass:5 ': (130, 200, 80), 'sea_lantern': (200, 230, 230),
                              'planks:5': (70, 50, 30), 'wooden_slab:5': (80, 58, 35), 'wooden_slab:1': (110, 80, 50)})
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    X0, X1, Z0, Z1 = -660, -622, 1742, 1775
    S = 14
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 40, mh + 60 + 260), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 110
            while y > 40 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'stone':
                k = (max(60, min(y, 90)) - 60) / 30; c = (int(200 - 70 * k), int(210 - 40 * k), int(140 - 60 * k))
            else: c = cc(b)
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
    for x in range(-660, X1 + 1, 10): dr.text((20 + (x - X0) * S - 8, 16), str(x), fill='black', font=F(10))
    for z in range(1750, Z1 + 1, 10): dr.text((0, 30 + (z - Z0) * S - 5), str(z), fill='black', font=F(9))
    dr.text((20, 2), 'Зоопарк, этап 2 (park-2-zoo) — вид сверху', fill='black', font=F(12))
    y0 = mh + 60; S2 = 6
    dr.text((20, y0 - 16), 'разрез Z=1750: Парковая ул. — медведи — аллея — купол — смотровая — ламы (Y 60…95)', fill='black', font=F(11))
    for u, x in enumerate(range(-658, -622)):
        for y in range(60, 96):
            b = final(x, y, 1750)
            if b == 'air': continue
            c = (150, 140, 110) if b == 'stone' else cc(b)
            dr.rectangle([20 + u * 14, y0 + (95 - y) * S2, 20 + u * 14 + 13, y0 + (95 - y) * S2 + S2 - 1], fill=c)
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
