"""Гора F, этап 1 одной порцией (CITY.md §7.7, план v1 — tools/city/plan_mount_v1.py, геометрия оттуда).

Три схемы:
- mount-1-ground.json — земляные работы и подпорные стенки; Горная дорога через Горную площадь (79.0) и на
  плато (79.0 → 83.0, подъёмы по 0.5 через 4 бл., края +0.5); Горная площадь; Ледовое кольцо (дорожка 3 бл.
  из плотного льда, бортики — нижние полублоки, остров с елью и снеговиком, у дороги — стенка с оградой);
  Зимняя площадь и каток (83.0); Скальная лестница (марши 6/5/5, площадки 89 и 94, марш 2 — в расщелине под
  мостиком); вершина — смотровая «Бухта» (мощение Y 98, ходим 99.0, по краю стекло «в пол» 2 бл.); ельник,
  снег (блоки; слой снега — только вдали от света), фонари DECOR §3.2а, скамейки, урны;
- mount-1-tower.json — башня-серпантин: винтовой пандус 4 витка 64.5 → 79.0 (плита на .5, полный блок на .0,
  без подложки — просвет между витками ≥ 3), столб со светом, стена с окнами, вход с запада, выход на площадь;
- mount-1-build.json — Горный приют (city_lib.Tower, шале: ель, витражи, двускатная кровля, камин-печь,
  стойка, столик; электрощитовая 3×3 с кабельной шахтой — пустая), ротонда на вершине (кварц, фонарь в
  куполе), стеклянный балкон (пол, ограждение, навес), флагшток.
Вне 25 чанков загрузчика — только декор.

Запуск: gen_mount_1.py [--outdir schemas] [--preview docs/districts/mount-1-preview.png]
Мир — World() (после постройки — built_before('mount-1-ground.json')).
Проверки: опоры + вода + порядок (decor_lib, порядок бота), проходимость без прыжков от конца Горной дороги
до каждой клетки сети и по маршрутам (витки серпантина, площадь, кольцо, остров, плато, каток, приют и
щитовая, лестница, вершина обеих частей, ротонда, балкон, Башенная площадь холма E), перепад между
соседями, обрывы без ограждения, кольцо замкнуто для лодки, лёд только плотный, слой снега вдали от света,
свет ≤ 5 бл. (фонари) / без спавна (серпантин, расщелина), скамейки, висящие над мощением, подходы к
двери, выходы лестниц свободны, кровля каньона, ламы и лестница холма не задеты; негативные прогоны.
"""
import argparse
import math
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import (World, REPO, BUILT, built_before, Tower, save_schema, DOOR_IN, N4, dl,  # noqa: E402
                      door_approach_issues, floating_over_paving, col, CL)
from gen_park_1 import Sch, h32, rect, bench  # noqa: E402
import plan_mount_v1 as P  # noqa: E402

NAMES = ['mount-1-ground.json', 'mount-1-tower.json', 'mount-1-build.json']
LAMP = ('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
SAD, WIN, TOP, LO = P.SAD, P.WIN, P.TOP, P.LO
CX, CZ = P.HC
LOOP = (-611, -599, 1749, 1760)
RINK = (-616, -607, 1729, 1734)
LODGE = (-603, -599, 1736, 1746)
ROT = (-616, 1748)                                          # центр ротонды на вершине
FLAG = (-609, 1737)
LIGHT = {'sea_lantern', 'glowstone', 'lit_pumpkin'}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'mount-1-preview.png'))
    return p.parse_args()


class WG:
    """Мир с уже поставленными схемами (поверх — в порядке списка)."""
    def __init__(self, W, *S): self.W, self.S = W, S

    def block(self, x, y, z):
        for s in reversed(self.S):
            b = s.c.get((x, y, z))
            if b is not None: return b
        return self.W.block(x, y, z)

    def surf(self, x, z, ymax=120, ymin=20):
        for y in range(ymax, ymin, -1):
            if World.solid(self.block(x, y, z)): return y

    def water(self, x, z): return self.W.water(x, z)

    def cave_top(self, x, z): return self.W.cave_top(x, z)


def colx(S, T, x, z, h, full, slab=None, fill='stone', clear_to=None):
    """Колонна до ходовой высоты h (шаг 0.5): полный блок (h целое) или полный + нижний полублок; ниже —
    fill от настоящего грунта T (стволы каучуковых деревьев в модели — «грунт», их снимаем), выше — воздух."""
    W = S.W
    g0 = T(x, z)
    gm = W.surf(x, z)
    if h == int(h):
        top = int(h) - 1; S.put(x, top, z, full); low = top
    else:
        top = int(h); S.put(x, top - 1, z, full); S.put(x, top, z, slab); low = top - 1
    for y in range(g0 + 1, low): S.put(x, y, z, fill)
    hi = max(S.plant_top(x, z), gm, top, clear_to or 0)
    for y in range(top + 1, hi + 1): S.put(x, y, z, 'air')
    return top


def stair_col(S, T, x, z, w, mat, meta, fill='stonebrick'):
    """Ступенька: блок-ступенька на Y w−1 (верх w), под ней fill до грунта, выше — воздух."""
    g0 = T(x, z)
    S.put(x, w - 1, z, f'{mat}:{meta}')
    for y in range(g0 + 1, w - 1): S.put(x, y, z, fill)
    for y in range(w, max(S.plant_top(x, z), S.W.surf(x, z), w) + 1): S.put(x, y, z, 'air')


def spruce(S, x, y, z, trunk=6):
    """Ель: ствол log:1, хвоя leaves:5 (не опадает) ярусами — нижний ярус на 3 бл. выше основания."""
    for i in range(trunk): S.put(x, y + i, z, 'log:1')
    t = y + trunk
    for dy, r in ((-3, 2), (-2, 1), (-1, 2), (0, 1), (1, 1), (2, 0)):
        for a in range(-r, r + 1):
            for b in range(-r, r + 1):
                if abs(a) + abs(b) > r + (1 if r == 2 else 0) or (a == 0 and b == 0 and dy < 1): continue
                S.c.setdefault((x + a, t + dy, z + b), 'leaves:5')
    S.c.setdefault((x, t + 1, z), 'leaves:5')


# ---------------- земля: дорога, площади, кольцо, плато, лестница, вершина ----------------
def ground(W, T):
    hm = P.helix_model()
    foot, walk, flights = P.plan(T, hm)
    G = Sch(W)
    H, kind = {}, {}                                         # ходовые высоты и род клетки
    stl, _ = P.stairs_levels()
    tower = foot['helix']
    # ---- Горная дорога через площадь (79.0): середина — каменный кирпич, края — плиты, вровень
    for (x, z) in foot['proezd']:
        mid = 1768 <= z <= 1770
        colx(G, T, x, z, SAD, 'stonebrick' if mid else 'double_stone_slab', fill='stonebrick')
        H[(x, z)] = SAD; kind[(x, z)] = 'road'
    # ---- дорога на плато X −598…−594: проезжая часть −597…−595, края −598 и −594 на 0.5 выше
    for (x, z) in foot['road']:
        h = P.road_leg(z) + (0.5 if x in (-598, -594) else 0)
        if x in (-598, -594): colx(G, T, x, z, h, 'double_stone_slab', 'stone_slab', fill='stonebrick')
        else: colx(G, T, x, z, h, 'stonebrick', 'stone_slab:5', fill='stonebrick')
        H[(x, z)] = h; kind[(x, z)] = 'road'
    # ---- Горная площадь (79.0): гладкий песчаник, кварцевые полосы через 4
    for (x, z) in foot['plaza']:
        colx(G, T, x, z, SAD, 'quartz_block' if (x + 609) % 4 == 0 else 'sandstone:2', fill='stonebrick')
        H[(x, z)] = SAD; kind[(x, z)] = 'plaza'
    # ---- Ледовое кольцо: лёд 79.0 (плотный лёд на 78), бортики — нижние полублоки песчаника (79.5)
    lx0, lx1, lz0, lz1 = LOOP
    track, borders, island = set(), set(), set()
    for (x, z) in foot['loop']:
        edge = x in (lx0, lx1) or z in (lz0, lz1)
        isl = lx0 + 4 <= x <= lx1 - 4 and lz0 + 4 <= z <= lz1 - 4
        isl_b = isl and (x in (lx0 + 4, lx1 - 4) or z in (lz0 + 4, lz1 - 4))
        if edge or isl_b:
            colx(G, T, x, z, SAD + 0.5, 'sandstone:2', 'stone_slab:1', fill='stonebrick'); H[(x, z)] = SAD + 0.5
            borders.add((x, z)); kind[(x, z)] = 'border'
        elif isl:
            colx(G, T, x, z, SAD, 'snow', fill='stonebrick'); H[(x, z)] = SAD; island.add((x, z)); kind[(x, z)] = 'island'
        else:
            colx(G, T, x, z, SAD, 'packed_ice', fill='stonebrick'); H[(x, z)] = SAD; track.add((x, z)); kind[(x, z)] = 'ice'
    # у дороги (X −599) — стенка до края дороги и ограда: с дороги на кольцо не выйти
    fence_road = []
    for z in range(lz0, 1764):
        e = H[(-598, z)]
        top = math.ceil(e) - 1
        for y in range(78, top + 1): G.put(-599, y, z, 'stonebrick')
        if e != int(e): G.put(-599, int(e), z, 'stone_slab:5'); top = int(e)
        G.put(-599, top + 1, z, 'spruce_fence'); fence_road.append((-599, top + 1, z))
        H.pop((-599, z), None); borders.discard((-599, z)); kind[(-599, z)] = 'wall'
    # ---- плато 83.0: Зимняя площадь (кирпич со снежными клетками), каток (плотный лёд, бортик-полублок),
    #      газоны плато — снег блоками; подпорные стенки по краям участка (Z 1728, X −593) и к седловине (Z 1747…1748)
    for (x, z) in foot['wplaza']:
        colx(G, T, x, z, WIN, 'snow' if h32(x, z, 7) < 0.18 else 'stonebrick', fill='stonebrick')
        H[(x, z)] = WIN; kind[(x, z)] = 'wplaza'
    rx0, rx1, rz0, rz1 = RINK
    rink_ice = set()
    for (x, z) in foot['rink']:
        if x in (rx0, rx1) or z in (rz0, rz1):
            colx(G, T, x, z, WIN + 0.5, 'sandstone:2', 'stone_slab:1', fill='stonebrick'); H[(x, z)] = WIN + 0.5; kind[(x, z)] = 'border'
        else:
            colx(G, T, x, z, WIN, 'packed_ice', fill='stonebrick'); H[(x, z)] = WIN; kind[(x, z)] = 'ice'; rink_ice.add((x, z))
    plateau = rect(-616, -594, 1729, 1735) - set(H) \
        - foot['stairs'] - foot['lodge'] - foot['summit']
    for (x, z) in sorted(plateau):
        if T(x, z) + 1 < WIN - 1: continue                   # западный край плато ниже — склон как есть
        colx(G, T, x, z, WIN, 'snow', fill='stonebrick'); H[(x, z)] = WIN; kind[(x, z)] = 'snowlawn'
    # участок приюта: пол Y 82 ставит Tower; здесь — выемка под него
    for (x, z) in foot['lodge']:
        for y in range(82, max(G.plant_top(x, z), W.surf(x, z)) + 1): G.put(x, y, z, 'air')
        for y in range(T(x, z) + 1, 82): G.put(x, y, z, 'stonebrick')
    retain = []
    for z in range(1728, 1767):                             # восточная стенка X −593 (грунт выше дороги/плато)
        c = (-593, z)
        e = H.get((-594, z), WIN)
        g = T(*c)
        if g + 1 <= e: continue
        for y in range(math.ceil(e) - 1 if e == int(e) else int(e), g + 1): G.put(-593, y, z, 'stonebrick')
        G.put(-593, g + 1, z, 'spruce_fence'); retain.append(c)
    for z in range(1761, 1775):                             # парапет восточного края площади X −593 (дальше рельефа нет)
        c = (-593, z)
        g = T(*c)
        for y in range(g + 1, int(SAD)): G.put(-593, y, z, 'stonebrick')
        G.put(-593, int(SAD), z, 'sandstone:2'); G.put(-593, int(SAD) + 1, z, 'stone_slab:1')
        for y in range(int(SAD) + 2, max(G.plant_top(*c), W.surf(*c)) + 1): G.put(-593, y, z, 'air')
        retain.append(c)
    for c in [(-617, z) for z in range(1729, 1736)] + [(-610, 1772), (-609, 1773)]:   # парапеты над склоном
        g = T(*c)
        lvl = WIN if c[0] == -617 else SAD
        if g + 1 > lvl - 2: continue
        for y in range(g + 1, int(lvl)): G.put(c[0], y, c[1], 'stonebrick')
        G.put(c[0], int(lvl), c[1], 'stonebrick'); G.put(c[0], int(lvl) + 1, c[1], 'stone_slab:5')
        retain.append(c)
    for x in range(-616, -593):                              # северная стенка Z 1728
        c = (x, 1728)
        g = T(*c)
        if g + 1 <= WIN: continue
        for y in range(int(WIN) - 1, g + 1): G.put(x, y, 1728, 'stonebrick')
        G.put(x, g + 1, 1728, 'spruce_fence'); retain.append(c)
    for x in range(-606, -598):                              # к седловине: стенка Z 1748 с оградой (плато 83 → 79)
        c = (x, 1748)
        if c in H: continue
        for y in range(T(*c) + 1, int(WIN)): G.put(x, y, 1748, 'stonebrick')
        for y in range(int(WIN), max(G.plant_top(*c), W.surf(*c)) + 1): G.put(x, y, 1748, 'air')
        G.put(x, int(WIN), 1748, 'spruce_fence'); retain.append(c)
    # ---- Скальная лестница: ступени — каменный кирпич, площадки — гладкий песчаник
    up = {1: (0, 1), 2: (-1, 0), 3: (0, -1)}
    for (x, z), h in stl.items():
        if (x, z) in ((-606, 1736), (-605, 1736)) or (1743 <= z <= 1744 and x in (-606, -605, -612, -613)):
            colx(G, T, x, z, h, 'sandstone:2', fill='stonebrick', clear_to=int(h) + 3); kind[(x, z)] = 'landing'
        else:
            meta = 2 if x in (-606, -605) else 1 if z in (1743, 1744) else 3
            stair_col(G, T, x, z, int(h), 'stone_brick_stairs', meta); kind[(x, z)] = 'st'
        H[(x, z)] = h
    # парапет марша 1 и площадки 1 со стороны приюта (X −604) и юга (Z 1745)
    par1 = []
    for z in range(1737, 1746):
        n = (-604, z) if z <= 1744 else (-605, 1745)
        h = H[(-605, min(z, 1744))]
        g = T(*n)
        for y in range(g + 1, int(h) + 1): G.put(n[0], y, n[1], 'stonebrick')
        G.put(n[0], int(h) + 1, n[1], 'stone_slab:5'); par1.append(n)
        for y in range(int(h) + 2, max(G.plant_top(*n), W.surf(*n)) + 1): G.put(n[0], y, n[1], 'air')
    par1.append((-606, 1745))
    g = T(-606, 1745)
    for y in range(g + 1, 90): G.put(-606, y, 1745, 'stonebrick')
    G.put(-606, 90, 1745, 'stone_slab:5')
    # ---- вершина: мощение Y 98 (ходим 99.0), песчаник с кварцевыми кольцами вокруг ротонды; мостик над маршем 2
    summit = foot['summit'] | P.BRIDGE
    for (x, z) in sorted(summit):
        r = math.hypot(x - ROT[0], z - ROT[1])
        mat = 'quartz_block' if int(r) in (4, 8) else 'sandstone:2'
        if (x, z) in P.BRIDGE:
            G.put(x, int(TOP) - 1, z, mat)                   # мостик: плита пола на Y 98, под ним — марш 2
            for y in range(int(TOP), int(TOP) + 4): G.put(x, y, z, 'air')
            H[('b', x, z)] = TOP; kind[('b', x, z)] = 'bridge'
            continue
        colx(G, T, x, z, TOP, mat, fill='stonebrick')
        H[(x, z)] = TOP; kind[(x, z)] = 'summit'
    # стены расщелины: грунт по сторонам маршей 2–3 облицовать кирпичом (от ступени до мощения)
    cut = [c for c in stl if T(*c) + 1 > H[c] + 2]
    for (x, z) in cut:
        for a, b in N4:
            n = (x + a, z + b)
            if n in stl or n in H: continue
            top = int(TOP) - 2 if n in summit else T(*n)
            for y in range(int(H[(x, z)]) - 1, top + 1):
                if G.c.get((n[0], y, n[1])) in (None, 'air'): G.put(n[0], y, n[1], 'stonebrick')
    # свет в стенах расщелины и марша 1 (≤ 4 по длине)
    lit_cut = []
    for (x, z) in ((-607, 1742), (-609, 1742), (-611, 1745), (-614, 1743), (-614, 1740), (-611, 1741), (-607, 1738), (-607, 1745)):
        c = (x, z)
        near = [s for s in stl if abs(s[0] - x) + abs(s[1] - z) == 1]
        if not near or c in stl: continue
        y = int(min(H[s] for s in near)) + 1
        if y > int(TOP) - 1: continue                        # на вершине — только вровень с мощением или ниже
        G.put(x, y, z, 'sea_lantern'); lit_cut.append((x, y, z))
    return dict(G=G, H=H, kind=kind, foot=foot, walk=walk, hm=hm, stl=stl, summit=summit, track=track, borders=borders,
                island=island, rink_ice=rink_ice, retain=retain, par1=par1, fence_road=fence_road, lit_cut=lit_cut)


def decor(W, T, R):
    """Ограждения вершины и балкона, фонари, ели, снег, скамейки, урны, остров кольца."""
    G, H, kind, foot = R['G'], R['H'], R['kind'], R['foot']
    WGd = WG(W, G)
    summit = R['summit']
    net = {c for c in H if isinstance(c[0], int)}
    # ---- стекло «в пол» (2 бл.) по краю вершины: клетка вершины, у которой сосед (не вершина, не балкон,
    #      не мостик) ниже хода на 2 и больше
    top_of = {}
    for c, h in H.items():
        if isinstance(c[0], int): top_of[c] = max(top_of.get(c, -1), h)
    bal = foot['balcony']
    rails = set()
    for c in sorted(summit - P.BRIDGE):
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n in summit or n in bal: continue
            nt = top_of.get(n, T(*n) + 1)
            if nt <= TOP - 2: rails.add(c)
    exit3 = {(-612, 1737)}                                  # выход марша 3 — свободен (западная клетка — ограждение)
    rails -= exit3
    for (x, z) in P.BRIDGE:                                   # мостик: по краям X −610 и −607 — стекло
        if x in (-610, -607): G.put(x, int(TOP), z, 'glass_pane'); G.put(x, int(TOP) + 1, z, 'glass_pane'); rails.add(('b', x, z))
    for c in rails:
        if c[0] == 'b': continue
        G.put(c[0], int(TOP), c[1], 'glass_pane'); G.put(c[0], int(TOP) + 1, c[1], 'glass_pane')
    busy = set(rails) | exit3 | {(x, z) for x in (-613, -612) for z in (1736,)}
    # ---- ротонда: 8 колонн кварца r≈2.2, купол — кольцо кварца и плиты, фонарь в центре (в build)
    rot_cells = {(ROT[0] + a, ROT[1] + b) for a in range(-3, 4) for b in range(-3, 4) if math.hypot(a, b) <= 2.9}
    busy |= rot_cells
    # ---- скамейки: вершина — лицом на запад/юг к бухте (перед сиденьем свободно, дальше — стекло)
    benches, urns = [], []

    def free(cells, lvl, walkset):
        return all(c in walkset and c not in busy and H.get(c) == lvl for c in cells)
    smt = summit - P.BRIDGE
    for (x0, z0, face) in ((-619, 1750, 'w'), (-619, 1744, 'w'), (-613, 1753, 's'), (-609, 1747, 's'), (-611, 1736, 'n')):
        cells = [(x0 + i, z0) for i in range(4)] if face in ('n', 's') else [(x0, z0 + i) for i in range(4)]
        d = {'n': (0, -1), 's': (0, 1), 'e': (1, 0), 'w': (-1, 0)}[face]
        fr = [(c[0] + d[0], c[1] + d[1]) for c in cells[1:3]]
        if free(cells, TOP, smt) and free(fr, TOP, smt):
            bench(G, x0, int(TOP), z0, face); benches.append((x0, z0, face)); busy |= set(cells) | set(fr)
    # площадь: две скамейки лицом к кольцу (север), урны
    for (x0, z0) in ((-608, 1764), (-603, 1764)):
        cells = [(x0 + i, z0) for i in range(4)]
        fr = [(x0 + i, z0 - 1) for i in range(1, 3)]
        if free(cells, SAD, foot['plaza']) and free(fr, SAD, foot['plaza']):
            bench(G, x0, int(SAD), z0, 'n'); benches.append((x0, z0, 'n')); busy |= set(cells) | set(fr)
    # у катка — лицом ко льду (на север), на снегу плато
    busy |= {(-601, 1735), (-601, 1734), (-602, 1735), (-600, 1735)}          # перед дверью приюта
    for u in ((-609, 1764), (-604, 1765), (-609, 1735)):
        if u in H and u not in busy and H[u] == int(H[u]):
            G.put(u[0], int(H[u]), u[1], 'cauldron'); urns.append(u); busy.add(u)
    # ---- остров кольца: ель в центре, снеговик (светящаяся тыква — свет над льдом)
    isl = sorted(R['island'])
    ex, ez = isl[2]                                          # центр острова; хвоя — только над островом, с 82
    for i in range(6): G.put(ex, int(SAD) + i, ez, 'log:1')
    for y in range(82, 86):
        for a, b in N4: G.put(ex + a, y, ez + b, 'leaves:5')
    G.put(ex, 85, ez, 'leaves:5'); G.put(ex, 86, ez, 'leaves:5')
    sx, sz = isl[-1]
    G.put(sx, int(SAD), sz, 'snow'); G.put(sx, int(SAD) + 1, sz, 'snow'); G.put(sx, int(SAD) + 2, sz, 'lit_pumpkin:2')
    busy |= set(isl)
    # ---- фонари: чтобы вся сеть была в пределах 5 бл. от фонаря (по горизонтали)
    lamps = []

    def lamp_on(x, z, y):
        for i, b in enumerate(LAMP): G.put(x, y + i, z, b)
        lamps.append((x, z, y))
    # у дороги на плато — фонари на восточной стенке X −593; у кольца с запада — на грунте склона
    for z in (1763, 1758, 1753, 1748, 1743, 1738):
        e = H[(-594, z)]
        yl = math.ceil(e) + 1
        if T(-593, z) >= yl + 1 or G.c.get((-593, yl, z)) == 'stonebrick':
            G.put(-593, yl, z, 'sea_lantern'); lamps.append((-593, z, yl))          # фонарь в подпорной стенке
        else:
            y0 = max(T(-593, z), math.ceil(e) - 1)
            for y in range(T(-593, z) + 1, y0 + 1): G.put(-593, y, z, 'stonebrick')
            for i, b in enumerate(LAMP[1:]): G.put(-593, y0 + 1 + i, z, b)
            lamps.append((-593, z, y0 + 1))
    for x in (-609, -604, -600):                             # фонари в стенке Z 1748 над кольцом
        G.put(x, 80, 1748, 'sea_lantern'); lamps.append((x, 1748, 80))
    for x in (-614, -609, -603, -597):                       # в северной стенке у катка
        if G.c.get((x, 84, 1728)) == 'stonebrick': G.put(x, 84, 1728, 'sea_lantern'); lamps.append((x, 1728, 84))
    for (x, z) in ((-619, 1754), (-620, 1745), (-612, 1754)):   # в мощении вершины (вровень)
        if (x, z) in R['summit'] and (x, z) not in rails: G.put(x, 98, z, 'sea_lantern'); lamps.append((x, z, 98))
    for (x, z) in ((-612, 1751), (-612, 1758)):
        y0 = T(x, z)
        for y in range(y0 + 1, max(G.plant_top(x, z), W.surf(x, z)) + 1): G.put(x, y, z, 'air')
        for i, b in enumerate(LAMP): G.put(x, y0 + 1 + i, z, b)
        lamps.append((x, z, y0 + 1))
    exits = set()
    for c in list(R['stl']):                                  # выходы лестниц и серпантина на площадки — свободны на 2
        exits.add(c)
    exits |= {(x, z) for x in range(-610, -606) for z in range(1766, 1773)}
    near_exit = lambda c: any(max(abs(c[0] - e[0]), abs(c[1] - e[1])) <= 2 for e in exits)
    lit_pts = [(x, z) for (x, y, z) in R['lit_cut']] + [(sx, sz)]
    lit = lambda c: any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) <= 5 for l in [(a, b) for a, b, _ in lamps] + lit_pts)
    need = {c for c in net if kind.get(c) not in ('wall',)}
    lampable = {c for c in net if kind.get(c) in ('plaza', 'summit', 'wplaza', 'snowlawn') and H[c] == int(H[c])}
    cand = sorted((c for c in lampable if c not in busy and not near_exit(c)
                   and any((c[0] + a, c[1] + b) in busy or (c[0] + a, c[1] + b) not in net for a, b in N4)),
                  key=lambda c: h32(*c, 3))
    for c in cand:
        if all(lit(p) for p in need): break
        if all(lit(p) for p in need if max(abs(p[0] - c[0]), abs(p[1] - c[1])) <= 5): continue
        if any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) < 6 for l in lamps): continue
        lamp_on(c[0], c[1], int(H[c])); busy.add(c)
    # в кольце (кроме острова) фонарь на острове даёт свет; добавить на площадке у острова не нужно
    # ---- ели и снег: западный склон, край плато, у Зимней площади; не ближе 2 к сети и фонарям
    trees = []
    area_busy = set(net) | foot['helix'] | foot['lodge'] | set(R['retain']) | set(R['par1']) | foot['balcony'] | rails_xy(rails)
    lamp_xy = {(x, z) for x, z, _ in lamps}
    for c in sorted(rect(-621, -596, 1731, 1759), key=lambda c: h32(*c, 21)):
        x, z = c
        if c in area_busy or any((x + a, z + b) in area_busy or (x + a, z + b) in lamp_xy for a in range(-2, 3) for b in range(-2, 3)): continue
        if any(abs(x - t[0]) + abs(z - t[1]) < 4 for t in trees): continue
        if W._d['groundBlock'][W._i(x, z)] >= 256 or any((x, y, z) in W.pre for y in range(55, 110)): continue
        g = T(x, z)
        if W.block(x, g, z) != 'ground' or g < 68: continue
        if abs(T(x + 1, z) - g) > 2 or abs(T(x, z + 1) - g) > 2: continue   # не на обрыве
        for y in range(g + 1, max(G.plant_top(x, z), W.surf(x, z)) + 1): G.put(x, y, z, 'air')
        spruce(G, x, g + 1, z, 5 + int(h32(x, z, 2) * 3)); G.put(x, g, z, 'dirt:2'); trees.append(c)
    # слой снега на склоне (не ближе 4 бл. к источнику света, только на траве, без растений)
    lights = [(x, y, z) for (x, y, z), b in G.c.items() if b in LIGHT]
    snow = 0
    for c in rect(-624, -594, 1728, 1759):
        x, z = c
        if c in area_busy or c in trees or (x, z) in lamp_xy: continue
        if any((x, y, z) in W.pre for y in range(55, 110)) or W._d['groundBlock'][W._i(x, z)] != 2: continue
        g = T(x, z)
        if W.block(x, g, z) != 'ground' or (x, g, z) in G.c or (x, g + 1, z) in G.c: continue
        if W._d['top'][W._i(x, z)] is not None and W._d['top'][W._i(x, z)] > g: continue
        if any(abs(x - a) + abs(g + 1 - b) + abs(z - d) < 5 for a, b, d in lights): continue
        G.put(x, g + 1, z, 'snow_layer'); snow += 1
    R.update(rails=rails, benches=benches, urns=urns, lamps=lamps, trees=trees, snow=snow, busy=busy, exits=exits, rot_cells=rot_cells)
    return R


def rails_xy(rails): return {(c[1], c[2]) if c[0] == 'b' else c for c in rails}


# ---------------- башня-серпантин ----------------
def tower(W, T, R):
    hm = R['hm']
    G = R['G']
    WGd = WG(W, G)
    S = Sch(WGd)
    decks, wall, core = hm['decks'], hm['wall'], hm['core']
    appr, ex = hm['approach'], hm['exit']
    levels = {}
    for c, lv in decks.items(): levels[c] = list(lv)
    for c, h in appr.items(): levels.setdefault(c, []).append(h)
    for c, h in ex.items(): levels.setdefault(c, []).append(h)
    TOPW = 81                                                # верх стены и столба
    ring_all = set(decks) | wall | core
    # полотно: .0 — полный блок на h−1, .5 — нижний полублок на floor(h) без подложки (просвет ≥ 3)
    occ = {}
    for c, lv in levels.items():
        for h in lv:
            if h == int(h): occ[(c[0], int(h) - 1, c[1])] = 'stonebrick'
            else: occ[(c[0], int(h), c[1])] = 'stone_slab:5'
    base = {}
    for c, lv in levels.items():
        low = min(lv)
        b = int(low) - 1 if low == int(low) else int(low)    # блок самого нижнего хода
        base[c] = b
    # колонны кольца и подхода: воздух всюду внутри башни, кроме полотна; снизу — камень до грунта
    cols = set(levels) | wall | core
    for c in cols:
        x, z = c
        g = T(x, z)
        gm = WGd.surf(x, z)
        hi = max(gm, S.plant_top(x, z), TOPW + 2 if c in ring_all else int(max(levels.get(c, [0]))) + 2)
        lo = base.get(c, None)
        if c in core or c in wall:
            nb = [base[n] for n in ((x + a, z + b) for a in range(-1, 2) for b in range(-1, 2)) if n in base]
            lo = min(nb) if nb else g
            lo = min(lo, g + 1)
        for y in range(min(lo, g + 1), hi + 1):
            k = (x, y, z)
            if c in core:
                S.put(x, y, z, 'stonebrick' if y <= TOPW else 'air')
            elif c in wall:
                S.put(x, y, z, 'stonebrick' if y <= TOPW else 'air')
            else:
                if k in occ: S.put(*k, occ[k])
                elif y < lo: S.put(*k, 'stone')
                else: S.put(*k, 'air')
        if c in levels and c not in ring_all:                 # подход вне башни: грунт под ним и выше
            for y in range(g + 1, base[c]): S.put(x, y, z, 'stone')
    # фундамент стены и столба — не ниже грунта
    for c in wall | core:
        g = T(*c)
        y0 = min(y for (x, y, z) in S.c if (x, z) == c)
        for y in range(g + 1, y0): S.put(c[0], y, c[1], 'stonebrick')
    # зубцы наверху стены, маяк на столбе
    wl = sorted(wall, key=lambda c: math.atan2(c[0] - CX, c[1] - CZ))
    for i, c in enumerate(wl):
        if i % 2 == 0: S.put(c[0], TOPW + 1, c[1], 'stonebrick')
    S.put(CX, TOPW + 1, CZ, 'sea_lantern'); S.put(CX, TOPW + 2, CZ, 'stone_slab:5')
    # порталы: вход (подход в стене) и выход (выход в стене) — проём 2 бл. над ходом
    for c in wall:
        if c in appr or c in ex:
            h = (appr.get(c) or ex.get(c))
            b = int(h) - 1 if h == int(h) else int(h)
            S.put(c[0], b, c[1], occ.get((c[0], b, c[1]), 'stonebrick'))
            if h != int(h): S.put(c[0], b, c[1], 'stone_slab:5')
            y1 = b + 1
            for y in range(y1, y1 + 2 + (1 if h != int(h) else 0)): S.put(c[0], y, c[1], 'air')
            for y in range(int(h) - 1 if h == int(h) else int(h) - 1, T(*c) + 1):
                if y < b: S.put(c[0], y, c[1], 'stonebrick')
    # свет в столбе: морские фонари в наружных клетках столба на высоте головы каждого витка (через одну)
    cb = sorted([c for c in core if math.hypot(c[0] - CX, c[1] - CZ) >= 1.5], key=lambda c: math.atan2(c[0] - CX, c[1] - CZ))
    lights = []
    for i, c in enumerate(cb):
        if i % 2: continue
        th = math.atan2(c[0] - CX, c[1] - CZ) % (2 * math.pi)
        for t in range(P.TURNS):
            s = P.RC * (th + 2 * math.pi * t)
            h = LO + 0.5 * min(hm['n'], math.floor(s / hm['L'] + 1e-9))
            y = math.ceil(h) + 1
            S.put(c[0], y, c[1], 'sea_lantern'); lights.append((c[0], y, c[1]))
    # окна: стекло-панели в стене напротив каждого витка, где снаружи не грунт (через 3 клетки)
    windows = 0
    for i, c in enumerate(wl):
        if c in appr or c in ex or i % 3: continue
        th = math.atan2(c[0] - CX, c[1] - CZ) % (2 * math.pi)
        for t in range(P.TURNS):
            s = P.RC * (th + 2 * math.pi * t)
            h = LO + 0.5 * min(hm['n'], math.floor(s / hm['L'] + 1e-9))
            y = math.ceil(h)
            out_g = min(T(c[0] + a, c[1] + b) for a, b in N4 if (c[0] + a, c[1] + b) not in ring_all)
            if y > out_g + 1 and y + 1 <= TOPW - 1:
                S.put(c[0], y, c[1], 'glass_pane'); S.put(c[0], y + 1, c[1], 'glass_pane'); windows += 1
    for (x, y, z) in ((-610, 80, 1766), (-624, 66, 1767)):  # свет у выхода на площадь и у входа
        if (x, z) in wall: S.put(x, y, z, 'sea_lantern'); lights.append((x, y, z))
    # выход: ограждение по северному краю полосы выхода (Z 1768) — ниже, на Z 1767, верхний виток
    rail_exit = []
    zn = min(z for (x, z) in ex)
    for (x, z) in ex:
        if z == zn and (x, z) in decks:
            S.put(x, 79, z, 'glass_pane'); S.put(x, 80, z, 'glass_pane'); rail_exit.append((x, z))
    return dict(S=S, lights=lights, windows=windows, rail_exit=rail_exit, occ=occ, levels=levels)


# ---------------- здания: приют, ротонда, балкон, флаг ----------------
def build(W, T, R, Q):
    G, H, foot = R['G'], R['H'], R['foot']
    WGd = WG(W, G, Q['S'])
    B = Sch(WGd)
    x0, x1, z0, z1 = LODGE
    occ = lambda x, y, z: x0 <= x <= x1 and z0 <= z <= z1
    glass = lambda x, y, z: 'stained_glass_pane:0' if y in (84, 85) and (x + z) % 3 == 1 and x in (x0, x1) else \
        ('stained_glass_pane:3' if y in (84, 85) and z == z1 and x in (x0 + 1, x1 - 1) else 'planks:1')   # у двери (север) — без стекла
    L = Tower(WGd, 'Горный приют', occ, (x0, x1, z0, z1), 82, 87, band='planks:1', floor='planks:1', lobby='planks:1', glass_fn=glass)
    L.shell()
    L.door(-601, z0, 1, kind='spruce_door')
    L.room('Электрощитовая', (x0 + 1, x1 - 1, z1 - 2, z1), (-601, z1 - 3, 1), shaft=(x1 - 1, z1))
    for k, b in list(L.cells.items()):                      # деревянный пол — деревянные плиты у дверей
        if b == 'stone_pressure_plate': L.cells[k] = 'wooden_pressure_plate'
    # двускатная кровля из еловых ступенек вдоль Z (с навесом 1 бл.), конёк — доски
    for z in range(z0 - 1, z1 + 2):
        for i in range(3):
            y = 88 + i
            for x, meta in ((x0 - 1 + i, 0), (x1 + 1 - i, 1)):
                if x0 - 1 + i <= x1 + 1 - i and (x0 - 1 + i != x1 + 1 - i):
                    L.put(x, y, z, f'spruce_stairs:{meta}')
            if x0 - 1 + i == x1 + 1 - i - 2: L.put(x0 + 1 + i, y, z, 'planks:1')
        for x in range(x0, x1 + 1):
            if (x, 87, z) in L.cells and L.cells[(x, 87, z)] == 'stone_slab:7': L.cells[(x, 87, z)] = 'planks:1'
    for x in range(x0, x1 + 1):                              # фронтоны: доски под скатами
        for z in (z0 - 1, z1 + 1):
            pass
    for z in (z0, z1):
        for i, y in enumerate((88, 89)):
            for x in range(x0 + 1 + i, x1 - i):
                L.put(x, y, z, 'planks:1')
    # внутри: камин (печь в кирпичном портале), стойка с котлом-какао, столик и стулья
    hall = [(x, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1 - 3)]
    L.put(x1 - 1, 83, z1 - 4, 'furnace:4'); L.put(x1 - 1, 84, z1 - 4, 'stonebrick'); L.put(x1 - 1, 85, z1 - 4, 'stonebrick')
    L.put(x0 + 1, 83, z1 - 4, 'cauldron')
    L.put(x0 + 2, 83, z0 + 3, 'spruce_fence'); L.put(x0 + 2, 84, z0 + 3, 'wooden_pressure_plate')
    L.put(x0 + 1, 83, z0 + 3, 'spruce_stairs:0'); L.put(x0 + 3, 83, z0 + 3, 'spruce_stairs:1')
    for k, b in L.cells.items(): B.put(*k, b)
    # ---- ротонда: колонны кварца, кольцо и купол, фонарь в центре
    rx, rz = ROT
    for a in range(-3, 4):
        for b in range(-3, 4):
            r = math.hypot(a, b)
            x, z = rx + a, rz + b
            if (a, b) in ((2, 1), (-2, 1), (2, -1), (-2, -1), (1, 2), (-1, 2), (1, -2), (-1, -2)):
                for y in range(99, 102): B.put(x, y, z, 'quartz_block:2')
            if r <= 2.3: B.put(x, 102, z, 'quartz_block' if r > 1.2 else 'sea_lantern')
            if r <= 1.5: B.put(x, 103, z, 'stone_slab:7')
    # ---- стеклянный балкон: пол Y 98, ограждение 2 бл., навес Y 101
    bal = foot['balcony']
    summit = R['summit']
    for (x, z) in bal:
        B.put(x, 98, z, 'glass')
        edge = any((x + a, z + b) not in bal and (x + a, z + b) not in summit for a, b in N4)
        if edge: B.put(x, 99, z, 'glass_pane'); B.put(x, 100, z, 'glass_pane')
        B.put(x, 101, z, 'glass')
        for y in range(T(x, z) + 1, 98):
            if WGd.block(x, y, z) not in ('air', 'plant'): B.put(x, y, z, 'air')
    # у стыка с вершиной снять ограждение вершины (проход на балкон)
    opened = []
    for (x, z) in summit:
        nb = [(x + a, z + b) for a, b in N4 if (x + a, z + b) not in summit]
        if nb and all(n in bal for n in nb) and G.c.get((x, 99, z)) == 'glass_pane':
            B.put(x, 99, z, 'air'); B.put(x, 100, z, 'air'); opened.append((x, z))
    # консоли под балконом (перевёрнутые ступеньки кирпича у стыка)
    for (x, z) in bal:
        if (x + 1, z) in summit: B.put(x, 97, z, 'stone_brick_stairs:5')
    # ---- флагшток: забор 6 бл., флаг — красная шерсть
    fx, fz = FLAG
    for y in range(99, 105): B.put(fx, y, fz, 'spruce_fence')
    B.put(fx + 1, 104, fz, 'wool:14'); B.put(fx + 2, 104, fz, 'wool:14'); B.put(fx + 1, 103, fz, 'wool:0'); B.put(fx + 2, 103, fz, 'wool:0')
    return dict(B=B, L=L, opened=opened)


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0])) if NAMES[0] in names else World()
    T = P.Terrain(W)
    R = ground(W, T)
    R = decor(W, T, R)
    Q = tower(W, T, R)
    Bd = build(W, T, R, Q)
    G, S, B = R['G'], Q['S'], Bd['B']
    H, kind = R['H'], R['kind']
    print(f'сеть: клеток {sum(1 for c in H if isinstance(c[0], int))} | лёд кольца {len(R["track"])}, бортиков {len(R["borders"])}, '
          f'остров {len(R["island"])} | лёд катка {len(R["rink_ice"])} | подпорные стенки {len(R["retain"])} кл. | ограждение вершины '
          f'{len(R["rails"])} | фонарей {len(R["lamps"])} | елей {len(R["trees"])} | слой снега {R["snow"]} | скамеек {len(R["benches"])} | урн {len(R["urns"])}')
    print(f'серпантин: свет в столбе {len(Q["lights"])}, окон {Q["windows"]}, ограждение выхода {len(Q["rail_exit"])} | приют: дверей '
          f'{len(Bd["L"].doors)}, щитовая {Bd["L"].rooms} | проход на балкон {len(Bd["opened"])} кл.')
    outs = {}
    for nm, Sx in zip(NAMES, (G, S, B)):
        o, rel, order, dims = save_schema(Sx.c, os.path.join(args.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(Sx.c)}')
    checks(W, T, R, Q, Bd, outs, args)


def checks(W, T, R, Q, Bd, outs, args):
    G, S, B = R['G'], Q['S'], Bd['B']
    H, kind, foot = R['H'], R['kind'], R['foot']
    print('== ПРОВЕРКИ ==')
    prevs = {NAMES[0]: {}, NAMES[1]: dict(G.c), NAMES[2]: {**G.c, **S.c}}
    for nm, Sx in zip(NAMES, (G, S, B)):
        o, rel, order = outs[nm]
        prev = prevs[nm]

        def terr(x, y, z, o=o, prev=prev):
            k = (x + o[0], y + o[1], z + o[2])
            b = prev.get(k) or W.block(*k)
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:6]: print('   ', m)
        be = dl.check_bench_front(rel, terr)
        print(f'{nm}: скамейки (место для ног): ошибок {len(be)}', be[:3])
    ALL = dict(G.c); ALL.update(S.c); ALL.update(B.c)

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    leak = [(x + a, y, z + c) for (x, y, z), b in ALL.items() if b == 'air' for a, c in N4
            if (x + a, y, z + c) not in ALL and W.block(x + a, y, z + c) == 'water']
    print('вода рельефа, открытая в воздух схемы:', len(leak))
    net = {c for c in H if isinstance(c[0], int)}
    ice_of = lambda cells: [k for k, b in cells.items() if b.split(':')[0] == 'ice']
    ice = ice_of(ALL)
    print('клеток обычного льда (тает от света > 11, нужен плотный):', len(ice))
    lights = [k for k, b in ALL.items() if b.split(':')[0] in LIGHT]

    def melt(cells):
        ls = [k for k, b in cells.items() if b.split(':')[0] in LIGHT]
        return [k for k, b in cells.items() if b == 'snow_layer' and any(abs(k[0] - a) + abs(k[1] - b_) + abs(k[2] - c) < 5 for a, b_, c in ls)]
    sl = melt(ALL)
    print('слой снега ближе 4 бл. к свету (растает):', len(sl), sl[:3])
    hill = [k for k in ALL if (k[0], k[2]) in rect(-623, -607, 1774, 1774) | rect(-624, -610, 1773, 1773) or
            (k[0] <= -607 and k[2] in (1775, 1776)) or (P.LLAMA[0] <= k[0] <= P.LLAMA[1] and P.LLAMA[2] <= k[2] <= P.LLAMA[3])]
    print('задеты Северная лестница холма E (марши, парапет, основание) или вольер лам:', len(hill), hill[:3])
    out = [k for k in ALL if not (P.DX0 <= k[0] <= P.DX1 and P.DZ0 <= k[2] <= P.DZ1)]
    print('блоки вне района X −624…−593, Z 1728…1775:', len(out), out[:3])
    # кольцо: лодка не выходит — сосед каждой клетки льда: лёд, бортик-полублок или стенка
    tr = R['track']

    def boat_leaks(fin):
        bad = []
        for (x, z) in tr:
            for a, b in N4:
                n = (x + a, z + b)
                if n in tr: continue
                t = fin(n[0], 78, n[1]); u = fin(n[0], 79, n[1])
                if u == 'air' and t in ('packed_ice', 'ice', 'snow', 'sandstone:2', 'stone', 'stonebrick', 'air'): bad.append(n)
        return bad
    bl = boat_leaks(final)
    ring_ok = len(tr) > 0 and all(sum((x + a, z + b) in tr for a, b in N4) >= 2 for (x, z) in tr)
    print(f'Ледовое кольцо: {len(tr)} кл. льда, разрывов дорожки {0 if ring_ok else 1}, выходов для лодки (сосед без бортика): {len(bl)}', bl[:3])
    # перепады по сети (кроме ступеней и бортиков) > 0.5
    jump = [(c, n) for c in net for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1))
            if n in net and kind[c] not in ('st', 'wall') and kind[n] not in ('st', 'wall') and abs(H[c] - H[n]) > 0.5
            and not ({kind[c], kind[n]} <= {'summit', 'landing', 'bridge'} and False)
            and not (kind[c] in ('road',) and kind[n] in ('border',)) and not (kind[n] in ('road',) and kind[c] in ('border',))]
    jump = [j for j in jump if not (H[j[0]] >= 99 or H[j[1]] >= 99) or abs(H[j[0]] - H[j[1]]) > 0.5 and min(H[j[0]], H[j[1]]) >= 99]
    print('перепад покрытия между соседями (кроме ступеней) > 0.5 —', len(jump), jump[:3])
    # обрывы без ограждения: ходовая клетка, сосед вне сети ниже на 2+ и без ограды/стекла
    def drops(fin):
        out = []
        for c in net:
            if kind.get(c) in ('wall',): continue
            h = H[c]
            if fin(c[0], math.ceil(h), c[1]) != 'air' and fin(c[0], math.ceil(h), c[1]).split(':')[0] in ('glass_pane', 'spruce_fence', 'dark_oak_fence'):
                continue
            for a, b in N4:
                n = (c[0] + a, c[1] + b)
                if n in net and abs(H[n] - h) < 2: continue
                y = math.ceil(h) + 1
                blk = fin(n[0], math.ceil(h), n[1])
                if blk != 'air' and blk.split(':')[0] not in ('red_flower', 'snow_layer', 'tallgrass'): continue
                while y > 40 and fin(n[0], y, n[1]) in ('air', 'snow_layer') or fin(n[0], y, n[1]).split(':')[0] in ('leaves', 'tallgrass', 'red_flower'):
                    y -= 1
                if y + 1 <= h - 2: out.append((c, n, y + 1))
        return out
    dr_ = drops(final)
    print('обрыв ≥ 2 у края сети без ограждения —', len(dr_), dr_[:8])
    fl = floating_over_paving(final, ALL, {c: h for c, h in H.items() if isinstance(c[0], int) and kind[c] not in ('st',)})
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:4])
    ex_items = [(x, z, b) for (x, y, z), b in ALL.items() if (x, z) in net and (x, z) not in R['stl'] and kind.get((x, z)) != 'wall'
                and y == math.ceil(H[(x, z)]) and b not in ('air', 'snow_layer') and b.split(':')[0] not in ('stone_pressure_plate', 'wooden_pressure_plate', 'glass_pane')
                and any(max(abs(x - e[0]), abs(z - e[1])) <= 2 and abs(H[(x, z)] - e[2]) < 1
                        for e in {(-606, 1735, WIN), (-605, 1735, WIN), (-613, 1737, TOP), (-612, 1737, TOP), (-609, 1768, SAD), (-609, 1771, SAD)})]
    print('предметы у выходов лестницы и серпантина (≤ 2 бл.):', len(ex_items), ex_items[:3])
    # подходы к двери приюта
    L = Bd['L']
    doors = list(L.doors)

    def door_front(fin, ds):
        out = []
        for (x, y, z, m) in ds:
            a, b = DOOR_IN[m]
            for k in (1, 2):
                n = (x - k * a, z - k * b)
                t = fin(n[0], y - 1, n[1])
                if t in ('grass', 'dirt', 'air', 'stone') or fin(n[0], y, n[1]) != 'air' or fin(n[0], y + 1, n[1]) != 'air':
                    out.append(((x, z), k, t))
        return out
    di = door_approach_issues(final, doors) + door_front(final, doors)

    def door_gaps(fin):
        out = []
        for (x, y, z, m) in doors:
            side = [(x - 1, z), (x + 1, z)] if m in (1, 3) else [(x, z - 1), (x, z + 1)]
            for (sx, sz) in side + [(x, z)]:
                for yy in ((y, y + 1, y + 2) if (sx, sz) != (x, z) else (y + 2,)):
                    if fin(sx, yy, sz).split(':')[0] in ('glass_pane', 'stained_glass_pane'): out.append((sx, yy, sz))
        return out
    print('двери рядом со стеклом-панелью (щели): ошибок', len(door_gaps(final)))
    negc = dict(ALL); d = doors[0]; negc[(d[0] - 1, d[1], d[2])] = 'stained_glass_pane:0'
    print('НЕГАТИВ: панель у двери приюта — щель найдена:', len(door_gaps(fin_of(negc))) > 0)
    print(f'подходы к наружным дверям: {len(doors)}, ошибок {len(di)}', di[:2])
    # свет: сеть в пределах 5 бл. (по горизонтали, |dy| ≤ 6) от источника; серпантин и расщелина — манхэттен ≤ 7
    lset = lights

    def dark(cells):
        out = []
        for (x, z, h) in cells:
            if not any(max(abs(x - a), abs(z - c)) <= 5 and abs(h - b) <= 7 for a, b, c in lset): out.append((x, z, h))
        return out
    dnet = dark([(c[0], c[1], H[c]) for c in net if kind.get(c) not in ('wall',)] +
                [(x, z, h) for (x, z), lv in Q['levels'].items() for h in lv])
    print('клетки сети и витков без света ≤ 5 бл.:', len(dnet), dnet[:12])
    # кровля каньона под выемками; карманы заделать
    cv = W._cv
    digs = {}
    for (x, y, z), b in ALL.items():
        if b == 'air' and y <= T(x, z): digs[(x, z)] = min(digs.get((x, z), 999), y)
    plugged, roofs = 0, []
    for (x, z), y in digs.items():
        ct = W.cave_top(x, z)
        if ct is None or ct >= T(x, z): continue
        i = (z - cv['z0']) * cv['w'] + x - cv['x0']
        air = [yy for yy in range(cv['minAir'][i], min(ct, y - 1) + 1) if final(x, yy, z) == 'air']
        if air: roofs.append((y - max(air) - 1, x, z))
    kr = [(y - W.cave_top(x, z) - 1, x, z) for (x, z), y in digs.items() if W.cave_top(x, z) is not None and W.cave_top(x, z) < T(x, z)]
    print(f'кровля каньона под выемками схем: мин. {min(kr)[0] if kr else "—"} (норма ≥ 3), открытых карманов под выемками: {len(roofs)}')
    negk = [(y - 3 - W.cave_top(x, z) - 1) for (x, z), y in digs.items() if W.cave_top(x, z) is not None and W.cave_top(x, z) < T(x, z)]
    print('НЕГАТИВ: выемки на 3 бл. глубже — кровля < 3 найдена:', bool(negk) and min(negk) < 3)

    # ---- проходимость без прыжков: только по клеткам сети (газон и склоны не в счёт)
    walkable = net | {(x, z) for (x, z) in Q['levels']} | P.BRIDGE | foot['balcony'] | foot['lodge'] | \
        {(-630 + i, z) for i in range(6) for z in range(1769, 1774)} | {(x, z) for x in range(-610, -600) for z in range(1775, 1779)}
    box = ((-632, -593), (1728, 1780), (60, 106))
    start = (-630, 64.5, 1771)

    def walk(fin):
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in walkable else ('stone' if y < 60 else 'air')
        return dl.walk_reachable(f2, start, *box)
    seen = walk(final)
    occ = {(x, z) for (x, y, z), b in ALL.items() if (x, z) in net and b not in ('air', 'snow_layer') and math.ceil(H[(x, z)]) <= y <= math.ceil(H[(x, z)]) + 1
           and b.split(':')[0] not in ('stone_pressure_plate', 'wooden_pressure_plate')}
    miss = [c for c in net if c not in occ and kind.get(c) != 'wall' and not dl.reached(seen, c[0], H[c], c[1])]
    print(f'ПРОХОДИМОСТЬ без прыжков от конца Горной дороги (−630,1771): клеток сети {len(net) - len(occ)}, недостижимо {len(miss)}', miss[:6])
    hm = R['hm']
    lv_miss = [(x, z, h) for (x, z), lv in Q['levels'].items() for h in lv
               if (x, z) not in Q['rail_exit'] or h != SAD
               if not dl.reached(seen, x, h, z)]
    print(f'  витки серпантина: ходовых уровней {sum(len(v) for v in Q["levels"].values())}, недостижимо {len(lv_miss)}', lv_miss[:4])
    L = Bd['L']
    tg = {'серпантин, виток 2 (север)': (CX, LO + 0.5 * math.floor(P.RC * (3 * math.pi) / hm['L']), CZ - 4),
          'выход серпантина (−610,1770)': (-610, SAD, 1770), 'Горная площадь (−604,1762)': (-604, SAD, 1762),
          'Ледовое кольцо, лёд (−610,1755)': (-610, SAD, 1755), 'остров кольца (−605,1755)': (-605, SAD, 1755),
          'дорога на плато, середина (−596,1750)': (-596, P.road_leg(1750), 1750), 'Зимняя площадь (−598,1731)': (-598, WIN, 1731),
          'каток, лёд (−612,1731)': (-612, WIN, 1731), 'площадка 1 (−605,1743)': (-605, 89.0, 1743),
          'площадка 2 (−612,1744)': (-612, 94.0, 1744), 'вершина, север (−609,1739)': (-609, TOP, 1739),
          'мостик (−609,1743)': (-609, TOP, 1743), 'вершина, юг (−618,1751)': (-618, TOP, 1751),
          'в ротонде (−616,1748)': (ROT[0], TOP, ROT[1]), 'стеклянный балкон (−623,1746)': (-623, TOP, 1746),
          'Башенная площадь холма E (−606,1777)': (-606, SAD, 1777)}
    for (x, y, z, m) in L.doors:
        a, b = DOOR_IN[m]; tg[f'{L.name}: за дверью ({x},{z})'] = (x + a, y, z + b)
    tg.update({f'{L.name}: {k}': v for k, v in L.targets.items()})
    bad_t = 0
    for k, (x, y, z) in tg.items():
        ok = dl.reached(seen, x, y, z); bad_t += 0 if ok else 1
        print(f'  маршрут → {k}: {ok}')
    print('ИТОГО недостижимых точек:', len(miss) + len(lv_miss) + bad_t)
    # ---- негативные прогоны
    # 1: на витке 2 поперёк полотна — полный блок на +1 (прыжок): выход серпантина недостижим с дороги
    negc = dict(ALL)
    for (x, z), lv in hm['decks'].items():
        th = math.atan2(x - CX, z - CZ) % (2 * math.pi)
        if abs(th - math.pi) < 0.35:
            h = lv[1]
            negc[(x, math.ceil(h), z)] = 'stonebrick'
    s_ = walk(fin_of(negc))
    print('НЕГАТИВ: поперёк 2-го витка — блок на +1 (прыжок) — выход серпантина недостижим (холм E не в счёт):',
          not dl.reached(s_, -612, SAD, 1770) or dl.reached(s_, -606, SAD, 1777) and not dl.reached(s_, CX + 3, lv_at(hm, 2, 0.1), CZ + 4))
    # 2: ступенька марша 1 — полный блок: вершина недостижима
    negc = dict(ALL)
    for x in (-606, -605): negc[(x, 86, 1739)] = 'stonebrick'
    print('НЕГАТИВ: ступенька марша 1 заменена полным блоком — вершина недостижима:', not dl.reached(walk(fin_of(negc)), -609, TOP, 1739))
    # 3: без мостика — южная часть вершины (ротонда, балкон) недостижима
    negc = dict(ALL)
    for (x, z) in P.BRIDGE:
        for y in range(97, 101): negc[(x, y, z)] = 'air'
    s_ = walk(fin_of(negc))
    print('НЕГАТИВ: без мостика ротонда и балкон недостижимы:', not dl.reached(s_, ROT[0], TOP, ROT[1]) and not dl.reached(s_, -623, TOP, 1746))
    # 4: бортик кольца полным блоком — лёд с площади недостижим
    negc = dict(ALL)
    for x in range(LOOP[0], LOOP[1] + 1): negc[(x, 79, LOOP[3])] = 'sandstone:2'
    print('НЕГАТИВ: южный бортик кольца полным блоком — лёд недостижим:', not dl.reached(walk(fin_of(negc)), -610, SAD, 1755))
    # 5: снят бортик — лодка выходит
    negc = dict(ALL); c0 = (LOOP[0] + 5, LOOP[3]); negc[(c0[0], 79, c0[1])] = 'air'; negc[(c0[0], 78, c0[1])] = 'packed_ice'
    print('НЕГАТИВ: снят бортик кольца — выход для лодки найден:', len(boat_leaks(fin_of(negc))) > 0)
    # 6: снято стекло у края вершины — обрыв найден
    rl = sorted(c for c in R['rails'] if c[0] != 'b')[0]
    negc = dict(ALL); negc[(rl[0], 99, rl[1])] = 'air'; negc[(rl[0], 100, rl[1])] = 'air'
    print('НЕГАТИВ: снято стекло у края вершины — обрыв найден:', len(drops(fin_of(negc))) > len(dr_))
    # 7: газон перед дверью приюта — ошибка подхода
    negc = dict(ALL); d = doors[0]; a, b = DOOR_IN[d[3]]; negc[(d[0] - a, d[1] - 1, d[2] - b)] = 'grass'
    print('НЕГАТИВ: газон перед дверью приюта — ошибка подхода найдена:', len(door_front(fin_of(negc), doors)) > 0)
    # 8: обычный лёд и слой снега у фонаря
    negc = dict(ALL); t0 = sorted(R['track'])[0]; negc[(t0[0], 78, t0[1])] = 'ice'
    print('НЕГАТИВ: клетка кольца из обычного льда — найдена:', len(ice_of(negc)) > 0)
    sn = next(k for k, b in sorted(ALL.items()) if b == 'snow_layer')
    negc = dict(ALL); negc[(sn[0], sn[1] + 2, sn[2] + 1)] = 'sea_lantern'
    print('НЕГАТИВ: фонарь у слоя снега — таяние найдено:', len(melt(negc)) > 0)
    # 9: кашпо перед скамейкой — ошибка места для ног
    o, rel, order = outs[NAMES[0]]
    negr = dict(rel)
    bx_, bz_, face = R['benches'][0]
    dx_, dz_ = {'n': (0, -1), 's': (0, 1), 'e': (1, 0), 'w': (-1, 0)}[face]
    fx_, fz_ = (bx_ + 1 + dx_, bz_ + dz_) if face in ('n', 's') else (bx_ + dx_, bz_ + 1 + dz_)
    by_ = int(TOP) if (bx_, bz_) in R['summit'] else int(H[(bx_, bz_)])
    negr[(fx_ - o[0], by_ - o[1], fz_ - o[2])] = 'leaves:4'
    terr0 = lambda x, y, z: (lambda b: 'stone' if b == 'ground' else ('air' if b == 'plant' else b))(W.block(x + o[0], y + o[1], z + o[2]))
    print('НЕГАТИВ: кашпо перед скамейкой: ошибок', len(dl.check_bench_front(negr, terr0)), '(ждём > 0)')
    if args.preview: preview(args.preview, final, R, Q)


def lv_at(hm, t, frac):
    s = P.RC * 2 * math.pi * (t + frac)
    return LO + 0.5 * min(hm['n'], math.floor(s / hm['L'] + 1e-9))


def preview(path, final, R, Q):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    C = dict(CL); C.update({'sandstone:2': (225, 212, 160), 'stone_slab:1': (215, 202, 150), 'quartz_block': (240, 238, 232),
                            'stone_slab:7': (236, 234, 228), 'quartz_block:2': (240, 238, 232), 'packed_ice': (150, 185, 240),
                            'snow': (248, 250, 252), 'snow_layer': (240, 244, 248), 'stonebrick': (130, 130, 130),
                            'stone_slab:5': (140, 140, 140), 'double_stone_slab': (170, 170, 170), 'stone_slab': (165, 165, 165),
                            'glass': (170, 215, 240), 'glass_pane': (150, 200, 230), 'sea_lantern': (200, 230, 230),
                            'leaves:5': (40, 90, 60), 'log:1': (90, 60, 35), 'planks:1': (120, 85, 50), 'spruce_stairs': (110, 80, 45),
                            'stone_brick_stairs': (135, 135, 135), 'spruce_fence': (100, 70, 40), 'dark_oak_fence': (70, 50, 30),
                            'quartz_block:1': (235, 232, 225), 'stained_glass_pane:0': (230, 235, 240), 'stained_glass_pane:3': (120, 180, 230),
                            'wool:14': (180, 40, 40), 'lit_pumpkin': (230, 150, 40), 'grass': (95, 150, 60), 'dirt:2': (95, 75, 50)})
    cc = lambda b: C.get(b) or C.get(b.split(':')[0]) or col(b)
    X0, X1, Z0, Z1 = -626, -593, 1728, 1778
    S = 11
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    E = 5
    img = Image.new('RGB', (mw + 60 + (X1 - X0 + 1) * E + 80, mh + 60), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 110
            while y > 40 and final(x, y, z) in ('air',): y -= 1
            b = final(x, y, z)
            if b == 'stone':
                k = (max(60, min(y, 100)) - 60) / 40; c = (int(200 - 70 * k), int(210 - 40 * k), int(140 - 60 * k))
            else: c = cc(b)
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
            h = R['H'].get((x, z))
            if h is not None and h != int(h):
                dr.line([20 + (x - X0) * S + 1, 30 + (z - Z0) * S + S - 2, 20 + (x - X0) * S + S - 2, 30 + (z - Z0) * S + 1], fill=(90, 90, 90))
    for x in range(-620, X1 + 1, 10): dr.text((20 + (x - X0) * S - 8, 16), str(x), fill='black', font=F(10))
    for z in range(1730, Z1 + 1, 10): dr.text((0, 30 + (z - Z0) * S - 5), str(z), fill='black', font=F(9))
    dr.text((20, 2), 'Гора F, этап 1: вид сверху (серпантин — верхний виток), / — полублок', fill='black', font=F(12))
    # разрез Z 1765 через серпантин (запад → восток)
    bx = mw + 60
    ZC = 1765
    dr.text((bx, 16), f'Разрез Z {ZC}: серпантин, площадь', fill='black', font=F(11))
    base = 30 + mh
    sy = lambda y: base - (y - 58) * E
    for yy in range(60, 106, 5):
        dr.line([bx, sy(yy), bx + (X1 - X0 + 1) * E, sy(yy)], fill=(230, 230, 230)); dr.text((bx + (X1 - X0 + 1) * E + 3, sy(yy) - 5), str(yy), fill='black', font=F(8))
    for x in range(X0, X1 + 1):
        for y in range(58, 106):
            b = final(x, y, ZC)
            if b == 'air': continue
            c = (150, 140, 110) if b == 'stone' else cc(b)
            dr.rectangle([bx + (x - X0) * E, sy(y + 1), bx + (x - X0 + 1) * E - 1, sy(y) - 1], fill=c)
    img.save(path)
    print('превью', path, img.size)


if __name__ == '__main__':
    main()
