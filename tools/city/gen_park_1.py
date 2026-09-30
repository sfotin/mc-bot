"""Парк + зоопарк, этап 1 — парк (CITY.md §7.5, план v1 — tools/city/plan_park_v1.py, геометрия оттуда).

Две схемы:
- park-1-ground.json — земля и улицы: продолжение главного проспекта до X −625 (сечение как у
  Старого города на X −661), Парковая ул. X −660…−656, Горная дорога Z 1769…1773 с «зеброй»,
  озеро в новом контуре (вода Y 63, берег вровень, дно — песок Y 60, глубина 3, подсветка дна),
  засыпка старой воды вне контура, остров, кольцевая аллея и дорожки (песчаник, шаг 0.5),
  газоны и откосы (1:1), фонари DECOR §3.2а, деревья;
- park-1-build.json — объекты: Парковые ворота, Лодочная станция и причал на нижних полублоках,
  мостик и ротонда на острове, Кафе «Озеро» (city_lib.Tower; электрощитовая 3×3 с кабельной шахтой —
  на весь парк), Детская площадка, Розарий, Зелёный театр (сцена на воде с аркой, 8 дуговых рядов
  на склоне холма E, подпорная стенка), скамейки, урны.
Место вестибюля метро «Парк» замощено и свободно (строится со схемой тоннеля).

Запуск: gen_park_1.py [--outdir schemas] [--preview docs/districts/park-1-preview.png]
Мир — World() (район строится впервые; после постройки — built_before('park-1-ground.json')).
Проверки: опоры + вода + порядок (decor_lib, порядок бота), вода рельефа не открыта, перепад
покрытия, проходимость без прыжков от проспекта до каждой клетки мощения и до каждого объекта
(маршруты по отдельности), подходы к дверям, скамейки, висящие над мощением, резерв трасс,
кровля каньона, негативные прогоны.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import (World, REPO, BUILT, built_before, Tower, path_heights, save_schema, DOOR_IN, N4, dl,  # noqa: E402
                      door_approach_issues, floating_over_paving, col, CL)
import plan_park_v1 as P  # noqa: E402

NAMES = ['park-1-ground.json', 'park-1-build.json']
LAMP = ('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
RES = lambda x, z: 1812 <= z <= 1820                      # резерв трасс под проспектом (§7.5)
WY = P.WATER_Y                                            # вода озера Y 63, берег — верхний блок Y 63
MAT = {'ring': ('sandstone:2', 'stone_slab:1'), 'walk': ('sandstone:2', 'stone_slab:1'), 'orch': ('quartz_block', 'stone_slab:7'),
       'rose': ('double_stone_slab:9', 'stone_slab:1'), 'play': ('stained_hardened_clay:14', 'stone_slab:1'),
       'vest': ('double_stone_slab', 'stone_slab')}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'park-1-preview.png'))
    return p.parse_args()


def rect(x0, x1, z0, z1): return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def h32(x, z, k=0):
    v = (x * 73856093 ^ z * 19349663 ^ k * 83492791 ^ 0x5C17) & 0xffffffff
    v = (v ^ (v >> 13)) * 0x5bd1e995 & 0xffffffff
    return (v ^ (v >> 15)) / 0xffffffff


class Sch:
    def __init__(self, W): self.W = W; self.c = {}

    def put(self, x, y, z, b): self.c[(x, y, z)] = b

    def plant_top(self, x, z):
        y = self.W.surf(x, z) + 1
        while self.W.block(x, y, z) in ('plant',): y += 1
        return y - 1


def pave(S, x, z, h, full, slab, extra_clear=0):
    """Покрытие колонны до высоты h (шаг 0.5); ниже — камень до грунта; выше — расчистка (и воды тоже)."""
    W = S.W
    g = W.surf(x, z)
    if h == int(h):
        top = int(h) - 1; S.put(x, top, z, full); low = top
    else:
        top = int(h); S.put(x, top - 1, z, full); S.put(x, top, z, slab); low = top - 1
    for y in range(g + 1, low): S.put(x, y, z, 'stone')
    hi = max(S.plant_top(x, z), g, W.water(x, z) or 0, top + extra_clear)
    for y in range(top + 1, hi + 1): S.put(x, y, z, 'air')
    return top


def item_y(S, H, x, z, full='sandstone:2'):
    """Y предмета на мощении: на полублоке полублок меняется на полный блок (висящие, BOT.md §12)."""
    h = H[(x, z)]
    if h == int(h): return int(h)
    S.put(x, int(h), z, full)
    return int(h) + 1


def tree(S, x, y, z, kind='oak', trunk=4):
    log, lv = {'birch': ('log:2', 'leaves:6'), 'oak': ('log', 'leaves:4')}[kind]
    for i in range(trunk): S.put(x, y + i, z, log)
    t = y + trunk
    for dy in (-2, -1):
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                if (a, b) != (0, 0) and not (abs(a) == 1 and abs(b) == 1 and dy == -2 and h32(x + a, z + b, 5) < 0.5):
                    S.c.setdefault((x + a, t + dy, z + b), lv)
    for a, b in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)): S.c.setdefault((x + a, t, z + b), lv)
    S.c.setdefault((x, t + 1, z), lv)


def bench(S, x, y, z, face, n=2):
    """Скамейка DECOR §3.3а: face — куда смотрит сидящий; x,z — первый люк (З/С край)."""
    st = {'s': 3, 'n': 2, 'e': 1, 'w': 0}[face]
    if face in ('n', 's'):
        cells = [(x + i, z) for i in range(n + 2)]; ends = ('trapdoor:6', 'trapdoor:7')
    else:
        cells = [(x, z + i) for i in range(n + 2)]; ends = ('trapdoor:4', 'trapdoor:5')
    for i, (cx, cz) in enumerate(cells):
        S.put(cx, y, cz, ends[0] if i == 0 else ends[1] if i == len(cells) - 1 else f'birch_stairs:{st}')
    return cells


# ---------------- геометрия ----------------
def geometry():
    lake, isl = P.lake_cells()
    seats = P.theatre_cells()
    objs = {k: rect(x0, x1, z0, z1) for k, _, x0, x1, z0, z1, st, *_ in P.OBJ if st == 1}
    objs['thr'] = seats; objs['isl'] = isl
    return lake, isl, seats, objs


def streets():
    """(x, z) -> (h, блоки снизу вверх от Y 63 или 64). Сечения — как у Старого города."""
    S = {}
    road = (63, ('stonebrick', 'stone_slab:5'))         # 64.5
    edge = (64, ('double_stone_slab',))                  # 65.0
    for x in range(-660, -624):                          # проспект: сечение как на X −661
        for z in range(1813, 1821):
            if z == 1813: S[(x, z)] = (65.0, edge)
            elif z in (1814, 1818): S[(x, z)] = (64.5, (63, ('double_stone_slab', 'stone_slab')))
            elif z in (1815, 1816, 1817): S[(x, z)] = (64.5, road)
            else: S[(x, z)] = (65.0, edge)
    for x in range(-659, -656): S[(x, 1813)] = (64.5, road)            # въезд Парковой ул.
    for x in range(-660, -655):                          # Парковая ул.
        for z in range(1745, 1813):
            S[(x, z)] = (65.0, edge) if x in (-660, -656) else (64.5, road)
    for z in (1770, 1771, 1772): S[(-656, z)] = (64.5, road)            # поворот на Горную дорогу
    for x in range(-655, -624):                          # Горная дорога
        for z in range(1769, 1774):
            if z in (1769, 1773): S[(x, z)] = (65.0, edge)
            elif -648 <= x <= -646 and z in (1770, 1772): S[(x, z)] = (64.5, (63, ('quartz_block', 'stone_slab:7')))   # «зебра»
            else: S[(x, z)] = (64.5, road)
    return S


def path_sets(lake, isl, seats):
    cells, role = set(), {}

    def add(cs, r):
        for c in cs:
            if c not in role: role[c] = r; cells.add(c)
    for k, x0, x1, z0, z1, st in P.PATHS:
        if st == 1: add(rect(x0, x1, z0, z1), 'orch' if k == 'ring_e' else 'ring' if k.startswith('ring') else 'walk')
    cx, cz = P.THEATRE_C
    add({(x, z) for x in (-635, -634) for z in range(1776, 1796) if (x, z) not in seats and math.hypot(x - cx, z - cz) < 4.5}, 'orch')
    add(rect(*P.VEST[1:]), 'vest')
    # Розарий: крест дорожек и площадка в центре, выход на тротуар проспекта
    add(rect(-636, -627, 1804, 1805) | rect(-632, -631, 1802, 1812) | rect(-634, -629, 1802, 1807), 'rose')
    add(rect(-655, -648, 1801, 1809), 'play')
    return cells, role


def build(W):
    lake, isl, seats, objs = geometry()
    ST = streets()
    paths, role = path_sets(lake, isl, seats)
    G, B = Sch(W), Sch(W)
    cx, cz = P.THEATRE_C
    near_lake = lambda c: any((c[0] + a, c[1] + b) in lake for a, b in N4)
    # ---- высоты дорожек: у воды — 64.0 (вровень с берегом), оркестр — 64.0, пороги дверей — 64.0
    fixed = {c: h for c, (h, _) in ST.items()}
    for c in paths:
        if role[c] in ('ring', 'orch'):                   # кольцо у воды — вровень с берегом, у улиц — полублок
            fixed[c] = 64.5 if any((c[0] + a, c[1] + b) in ST for a, b in N4) else 64.0
        elif role[c] == 'rose': fixed[c] = 65.0           # розарий — ровная площадка вровень с тротуаром
        elif role[c] == 'play': fixed[c] = 64.0
        elif role[c] == 'vest': fixed[c] = 65.0
    for c in paths:                                       # у края улицы — не больше полублока от её покрытия
        for a_, b_ in N4:
            n = (c[0] + a_, c[1] + b_)
            if n in ST and c in fixed and abs(ST[n][0] - fixed[c]) > 0.5: fixed[c] = ST[n][0] - 0.5
    doors_front = {(-641, 1795): 64.0, (-646, 1799): 64.0, (-651, 1795): 64.0}
    fixed.update(doors_front)
    for _ in range(10):                                  # дорожки не ниже газона у озера (64.0): поднимаем и пересчитываем
        H, anchors, bad = path_heights(W, paths | set(doors_front), fixed)
        low = [c for c in paths if H[c] < 64.0]
        if not low: break
        for c in low: fixed[c] = 64.0
    for c, (h, _) in ST.items(): H[c] = h
    # ---- улицы
    for (x, z), (h, (y0, bl)) in ST.items():
        g = W.surf(x, z)
        for i, b in enumerate(bl): G.put(x, y0 + i, z, b)
        for y in range(g + 1, y0): G.put(x, y, z, 'stone')
        for y in range(y0 + len(bl), max(G.plant_top(x, z), g, W.water(x, z) or 0) + 1): G.put(x, y, z, 'air')
    # ---- дорожки
    for c in sorted(paths):
        full, slab = MAT[role[c]]
        if role[c] == 'play' and (c[0] + c[1]) % 2: full = 'stained_hardened_clay:4'
        if role[c] == 'ring' and h32(*c, 7) < 0.12: full = 'sandstone:0'
        pave(G, c[0], c[1], H[c], full, slab)
    net = set(H)
    # ---- озеро: вода Y 61…63, дно — песок Y 60 (подсветка — морские фонари), берег — Y 63
    lanterns = 0
    for (x, z) in lake:
        g = W.surf(x, z)
        for y in range(g + 1, 59): G.put(x, y, z, 'stone')
        G.put(x, 59, z, 'stone')
        lamp = (x * 5 + z * 3) % 17 == 0 and all((x + a, z + b) in lake for a, b in N4)
        G.put(x, 60, z, 'sea_lantern' if lamp else 'sand'); lanterns += lamp
        for y in (61, 62, WY): G.put(x, y, z, 'water')
        for y in range(WY + 1, max(G.plant_top(x, z), g) + 1): G.put(x, y, z, 'air')
    # плотина: клетки рядом с озером (кроме объектов на воде) — твёрдые до Y 63, иначе вода уходит вбок
    for (x, z) in {(x + a, z + b) for x, z in lake for a, b in N4} - lake:
        for y in range(60, WY + 1):
            k = (x, y, z)
            if G.c.get(k, W.block(*k)) in ('air', 'water', 'plant'): G.put(x, y, z, 'stone')
    # ---- газоны, берег, остров, откосы (1:1), засыпка старой воды
    area = rect(-664, -621, 1741, 1824)
    built_cols = {(k[0], k[2]) for k in W.pre}
    busy = net | lake | {c for k, cs in objs.items() if k not in ('isl',) for c in cs}
    ptop = {c: math.ceil(H[c]) - 1 for c in net}
    stop = {c: 64 + seat_row(c) for c in seats}
    inner = rect(-653, -638, 1776, 1792)                   # внутри кольцевой аллеи — берег вровень с водой
    lawn = {}
    for c in sorted(area - busy - built_cols):
        x, z = c
        g = W.surf(x, z)
        old_water = W.water(x, z) is not None and W.water(x, z) > g
        lo, hi = -1e9, 1e9
        for a in range(-3, 4):
            for b in range(-3, 4):
                n = (x + a, z + b); d = max(abs(a), abs(b))
                if n in ptop: lo, hi = max(lo, ptop[n] - d), min(hi, ptop[n] + d)
                elif n in stop: lo = max(lo, stop[n] - 1 - d)          # у рядов театра — только подсыпка; склон — стенкой
        if c in inner or c in isl or near_lake(c): lvl = WY
        elif lo == -1e9 and hi == 1e9 and not old_water: continue
        else:
            lvl = min(max(g, lo), hi) if lo <= hi else math.floor(hi)
            if old_water: lvl = max(lvl, WY)
        lvl = int(lvl)
        if lvl == g and not old_water and W.block(x, g + 1, z) != 'water': lawn[c] = lvl; continue
        for y in range(g + 1, lvl): G.put(x, y, z, 'stone')
        G.put(x, lvl, z, 'grass')
        for y in range(lvl + 1, max(G.plant_top(x, z), g, W.water(x, z) or 0) + 1): G.put(x, y, z, 'air')
        lawn[c] = lvl
    # ---- Зелёный театр: ряды — кварцевые ступеньки лицом к сцене, под ними камень, над ними выемка
    for (x, z) in seats:
        r = seat_row((x, z)); y = 64 + r; g = W.surf(x, z)
        dx, dz = x - cx, z - cz
        meta = (0 if dx > 0 else 1) if abs(dx) >= abs(dz) else (2 if dz > 0 else 3)
        for yy in range(g + 1, y): B.put(x, yy, z, 'stone')
        if g >= y: B.put(x, y - 1, z, 'stone')
        B.put(x, y, z, f'quartz_stairs:{meta}')
        for yy in range(y + 1, max(B.plant_top(x, z), g) + 1): B.put(x, yy, z, 'air')
    walls = 0
    walls_set = set()
    for (x, z) in {(x + a, z + b) for x, z in seats for a in (-1, 0, 1) for b in (-1, 0, 1)} - seats - net - lake:
        adj = [stop[(x + a, z + b)] for a in (-1, 0, 1) for b in (-1, 0, 1) if (x + a, z + b) in seats]
        g = lawn.get((x, z), W.surf(x, z))
        if g >= max(adj) + 2:                             # подпорная стенка к склону
            for yy in range(max(adj) + 1, g): B.put(x, yy, z, 'stonebrick')
            walls += 1; walls_set.add((x, z))
    # сцена на воде: настил тёмного дуба 64.5, арка-раковина из кварца, свет в замке арки
    for (x, z) in rect(-640, -638, 1781, 1788):
        g = W.surf(x, z)
        if (x, z) not in lake:
            for y in range(g + 1, WY): B.put(x, y, z, 'stone')
        B.put(x, WY, z, 'planks:5'); B.put(x, WY + 1, z, 'wooden_slab:5')
        for y in range(WY + 2, max(B.plant_top(x, z), g) + 1): B.put(x, y, z, 'air')
    for z in (1781, 1788):
        for y in range(64, 70): B.put(-640, y, z, 'quartz_block:2')
    for z in range(1781, 1789): B.put(-640, 70, z, 'sea_lantern' if z in (1784, 1785) else 'quartz_block')
    for z in range(1782, 1788): B.put(-640, 71, z, 'quartz_block')
    for z in range(1783, 1787): B.put(-640, 72, z, 'quartz_block')
    for z in (1784, 1785): B.put(-640, 73, z, 'stone_slab:7')
    # ---- остров и ротонда
    ix, iz = -647, 1782
    for (x, z) in rect(ix - 1, ix + 1, iz - 1, iz + 1): B.put(x, WY, z, 'quartz_block')
    for a in (-1, 1):
        for b in (-1, 1):
            for y in range(64, 67): B.put(ix + a, y, iz + b, 'quartz_block:2')
    for (x, z) in rect(ix - 1, ix + 1, iz - 1, iz + 1): B.put(x, 67, z, 'sea_lantern' if (x, z) == (ix, iz) else 'quartz_block')
    for (x, z) in rect(ix - 1, ix + 1, iz - 1, iz + 1): B.put(x, 68, z, 'stone_slab:7')
    B.put(ix, 68, iz, 'quartz_block:1'); B.put(ix, 69, iz, 'stone_slab:7')
    # мостик: настил тёмного дуба вровень с берегом (64.0), перила по краям
    for (x, z) in rect(-653, -650, 1781, 1783):
        g = W.surf(x, z)
        if (x, z) not in lake:
            for y in range(g + 1, WY): B.put(x, y, z, 'stone')
        B.put(x, WY, z, 'planks:5')
        if z != 1782: B.put(x, WY + 1, z, 'dark_oak_fence')
        for y in range(WY + (2 if z != 1782 else 1), max(B.plant_top(x, z), g) + 1): B.put(x, y, z, 'air')
    # причал: нижние полублоки (63.5) — ниже для посадки в лодку; швартовые столбы в воде
    for (x, z) in rect(-651, -650, 1788, 1792):
        g = W.surf(x, z)
        if (x, z) not in lake:
            for y in range(g + 1, WY): B.put(x, y, z, 'stone')
        B.put(x, WY, z, 'wooden_slab:5')
        for y in range(WY + 1, max(B.plant_top(x, z), g) + 1): B.put(x, y, z, 'air')
    for (x, z) in ((-652, 1788), (-649, 1788)):
        if (x, z) in lake:
            for y in range(61, WY + 2): B.put(x, y, z, 'dark_oak_fence')
    # ---- Парковые ворота: песчаниковые пилоны и перемычка над входом с Рыночного переулка
    for z in (1792, 1796):
        y0 = item_y(B, H, -655, z) if (-655, z) in H else lawn.get((-655, z), W.surf(-655, z)) + 1
        for y in range(y0, 68): B.put(-655, y, z, 'sandstone:2')
        B.put(-655, 67, z, 'sea_lantern')
    for z in range(1792, 1797): B.put(-655, 68, z, 'sandstone:2'); B.put(-655, 69, z, 'stone_slab:1')
    B.put(-655, 69, 1794, 'sandstone:1')
    # ---- здания: Кафе «Озеро» и Лодочная станция (city_lib.Tower)
    def stripes(pal):
        def f(x, y, z):
            if y in (64, 67): return 'concrete:0'
            return pal[(x + z) % len(pal)]
        return f
    cafe = Tower(W, 'Кафе «Озеро»', lambda x, y, z: -645 <= x <= -637 and 1796 <= z <= 1803, (-645, -637, 1796, 1803),
                 63, 68, band='concrete:0', lobby='quartz_block', glass_fn=stripes(['stained_glass:3', 'stained_glass:0', 'stained_glass:4']))
    cafe.shell()
    cafe.door(-641, 1796, 1); cafe.door(-645, 1799, 0)
    cafe.room('электрощитовая', (-640, -638, 1800, 1802), (-641, 1801, 0), shaft=(-638, 1802))
    for x in range(-640, -637): cafe.put(x, 64, 1798, 'planks:5'); cafe.put(x, 65, 1798, 'wooden_slab:5')   # стойка
    for (x, z) in ((-643, 1798), (-643, 1801)): cafe.put(x, 64, z, 'dark_oak_fence'); cafe.put(x, 65, z, 'wooden_pressure_plate')
    boat = Tower(W, 'Лодочная станция', lambda x, y, z: -652 <= x <= -649 and 1796 <= z <= 1799, (-652, -649, 1796, 1799),
                 63, 68, band='concrete:0', lobby='quartz_block', glass_fn=stripes(['stained_glass:11', 'stained_glass:0']))
    boat.shell()
    boat.door(-651, 1796, 1)
    towers = [cafe, boat]
    for T in towers:
        T.plan_ladders()
        for k, b in T.cells.items(): B.put(*k, b)
    # ---- Детская площадка: песочница, качели, горка со стремянкой, ограда из забора
    play = rect(-655, -648, 1801, 1809)
    for (x, z) in play:
        edge = x == -655 or z in (1801, 1809) or (x == -648 and not 1804 <= z <= 1806)
        if edge: B.put(x, item_y(B, H, x, z, 'stained_hardened_clay:14'), z, 'fence')
    for (x, z) in rect(-654, -652, 1802, 1804): B.put(x, 63, z, 'sand')                 # песочница вровень с полом
    for (x, z) in ((-654, 1802), (-652, 1802), (-654, 1804), (-652, 1804)): B.put(x, 63, z, 'planks:0')
    swing = (-650, 1802)                                  # качели вдоль ограды: стойки, перекладина, сиденье на цепях
    for x in (-651, -649):
        for y in range(64, 67): B.put(x, y, 1802, 'fence')
    for x in (-651, -650, -649): B.put(x, 67, 1802, 'fence')
    B.put(-650, 66, 1802, 'iron_bars'); B.put(-650, 65, 1802, 'wooden_slab:8')
    for y in range(64, 67): B.put(-653, y, 1807, 'planks:0')            # горка: башенка, стремянка, скат
    for y in range(64, 67): B.put(-654, y, 1807, 'ladder:4')
    for i, x in enumerate((-652, -651, -650)):
        yy = 66 - i
        for y in range(64, yy): B.put(x, y, 1807, 'planks:0')
        B.put(x, yy, 1807, 'quartz_stairs:1')
    # ---- Розарий: живая изгородь, клумбы с тюльпанами и розовыми кустами, солнечные часы в центре
    rose = rect(-636, -627, 1800, 1811)
    rtop = 64                                            # клумбы вровень с дорожками (65.0)
    flowers = ['red_flower:0', 'red_flower:4', 'red_flower:0', 'red_flower:5', 'red_flower:6', 'red_flower:7', 'red_flower:2', 'red_flower:8']
    for (x, z) in sorted(rose - net):
        g = W.surf(x, z)
        for y in range(g + 1, rtop): B.put(x, y, z, 'stone')
        B.put(x, rtop, z, 'grass')
        for y in range(rtop + 1, max(B.plant_top(x, z), g) + 1): B.put(x, y, z, 'air')
        hedge = x in (-636, -627) or z in (1800, 1811)
        if hedge: B.put(x, rtop + 1, z, 'leaves:4')
        else: B.put(x, rtop + 1, z, flowers[int(h32(x, z, 4) * len(flowers))])
    for (x, z) in rect(-632, -631, 1804, 1805):          # солнечные часы
        y = item_y(B, H, x, z, 'double_stone_slab:9')
        B.put(x, y, z, 'quartz_block:1')
    y = item_y(B, H, -632, 1804, 'double_stone_slab:9')
    B.put(-632, y + 1, 1804, 'quartz_block:2'); B.put(-632, y + 2, 1804, 'stone_slab:7')
    # ---- скамейки и урны
    benches = []

    def add_bench(x, z, face, S=B, n=2):
        cells = [(x + i, z) for i in range(n + 2)] if face in ('n', 's') else [(x, z + i) for i in range(n + 2)]
        if any(c not in H for c in cells) or len({H[c] for c in cells}) > 1: return False
        y = item_y(S, H, *cells[0])
        for c in cells[1:]: item_y(S, H, *c)
        bench(S, x, y, z, face, n); benches.append((x, z, face)); return True
    add_bench(-648, 1793, 'n'); add_bench(-644, 1793, 'n')          # южная аллея — лицом к озеру
    done = 0
    for x in range(-653, -638):                          # северная аллея — лицом к озеру, где перед скамейкой берег
        if done >= 2: break
        cs = [(x + i, 1775) for i in range(4)]
        if all((c[0], 1776) not in lake and (c[0], 1776) not in isl for c in cs) and \
                all(abs(x - b[0]) > 5 for b in benches if b[1] == 1775):
            if add_bench(x, 1775, 's'): done += 1
    add_bench(-633, 1802, 's')                           # розарий — лицом к солнечным часам
    add_bench(-652, 1805, 'n')                           # детская площадка — лицом к песочнице и качелям
    urns = [(-649, 1794), (-640, 1794), (-641, 1804)]
    for (x, z) in urns: B.put(x, item_y(B, H, x, z), z, 'cauldron')
    # ---- фонари: проспект (продолжение ритма Старого города X −664, −656 …), улицы — через 8, аллеи — на газоне
    lamps = []

    def lamp_on(S, x, z, y):
        for i, b in enumerate(LAMP): S.put(x, y + i, z, b)
        lamps.append((x, z))
    for x in range(-656, -625, 8):
        for z in (1814, 1818): lamp_on(G, x, z, item_y(G, H, x, z, 'quartz_block'))
    for z in range(1749, 1812, 8):
        if not (1765 <= z <= 1777 or 1789 <= z <= 1798): lamp_on(G, -656, z, item_y(G, H, -656, z, 'double_stone_slab'))
    for x in range(-652, -625, 8):
        if not -650 <= x <= -644: lamp_on(G, x, 1773 if x % 16 else 1769, item_y(G, H, x, 1773 if x % 16 else 1769, 'double_stone_slab'))
    cand = sorted(c for c in lawn if c not in isl and any((c[0] + a, c[1] + b) in paths for a, b in N4)
                  and 1774 <= c[1] <= 1812 and -655 <= c[0] <= -627)
    need = {c for c in paths if role[c] in ('ring', 'walk', 'orch', 'vest')}
    lit = lambda c: any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) <= 5 for l in lamps)
    for c in sorted(cand, key=lambda c: (h32(*c, 11))):
        if lit(c) and all(lit(p) for p in need if max(abs(p[0] - c[0]), abs(p[1] - c[1])) <= 5): continue
        if any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) < 6 for l in lamps): continue
        y = lawn[c]
        G.put(c[0], y, c[1], 'quartz_block:1')
        for i, b in enumerate(LAMP[1:]): G.put(c[0], y + 1 + i, c[1], b)
        for yy in range(y + len(LAMP), G.plant_top(*c) + 1): G.put(c[0], yy, c[1], 'air')
        lamps.append(c)
    # ---- деревья на газонах: дуб и берёза, не ближе 2 к мощению, воде, объектам, фонарям
    trees = []
    lampset = set(lamps)
    for c in sorted(lawn, key=lambda c: h32(*c, 21)):
        x, z = c
        if not (-655 <= x <= -627 and 1774 <= z <= 1812) or c in isl or c in inner or c in walls_set: continue
        if any((x + a, z + b) in busy or (x + a, z + b) in lampset for a in (-1, 0, 1) for b in (-1, 0, 1)): continue
        if any(abs(x - t[0]) + abs(z - t[1]) < 5 for t in trees): continue
        tree(G, x, lawn[c] + 1, z, 'oak' if h32(x, z, 9) < 0.5 else 'birch', 4 + int(h32(x, z, 2) * 2)); trees.append(c)
        G.put(x, lawn[c], z, 'grass')
    # карманы пустот под выемками (склон горы F у Горной дороги): заделать камнем, кровля ≥ 3
    cv = W._cv
    digs = {}
    for S_ in (G, B):
        for (x, y, z), b in S_.c.items():
            if b in ('air', 'water') and y <= W.surf(x, z): digs[(x, z)] = min(digs.get((x, z), 999), y)
    plugged = 0
    for (x, z), y in digs.items():
        ct = W.cave_top(x, z)
        if ct is None or ct < y - 4: continue
        i = (z - cv['z0']) * cv['w'] + x - cv['x0']
        for yy in range(cv['minAir'][i], y):
            k = (x, yy, z)
            if k not in G.c and k not in B.c: G.put(x, yy, z, 'stone'); plugged += 1
    return dict(G=G, B=B, H=H, plugged=plugged, net=net, paths=paths, role=role, lake=lake, isl=isl, seats=seats, objs=objs, lawn=lawn,
                towers=towers, benches=benches, swing=swing, lamps=lamps, trees=trees, bad=bad, walls=walls, lanterns=lanterns, ST=ST)


def seat_row(c):
    cx, cz = P.THEATRE_C
    return max(0, min(7, int(math.hypot(c[0] - cx, c[1] - cz) - 4.5)))


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0])) if NAMES[0] in names else World()
    R = build(W)
    G, B, H, net = R['G'], R['B'], R['H'], R['net']
    print(f'сеть: клеток {len(net)} (улицы {len(R["ST"])}, дорожки {len(R["paths"])}) | покрытие Y {min(H.values())}…{max(H.values())} | '
          f'озеро {len(R["lake"])} кл., подсветка дна {R["lanterns"]}, остров {len(R["isl"])} кл.')
    print(f'фонарей {len(R["lamps"])}, деревьев {len(R["trees"])}, скамеек {len(R["benches"])}, рядов театра {len(R["seats"])} кл., '
          f'подпорная стенка {R["walls"]} кл.')
    outs = {}
    for nm, S in zip(NAMES, (G, B)):
        o, rel, order, dims = save_schema(S.c, os.path.join(args.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(S.c)}')

    print('== ПРОВЕРКИ ==')
    for nm, S in zip(NAMES, (G, B)):
        o, rel, order = outs[nm]
        prev = G.c if nm == NAMES[1] else {}

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
    ALL = dict(G.c); ALL.update(B.c)

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    leak = [(x + a, y, z + c) for (x, y, z), b in ALL.items() if b == 'air' for a, c in N4
            if (x + a, y, z + c) not in ALL and W.block(x + a, y, z + c) == 'water']
    print('вода рельефа, открытая в воздух схемы:', len(leak), leak[:4])
    wet = [(x, y, z) for (x, y, z), b in ALL.items() if b == 'water' for a, c in N4
           if final(x + a, y, z + c) == 'air']
    print('вода озера, открытая в воздух сбоку:', len(wet), wet[:4])
    jump = [(c, n) for c in net for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if n in net and abs(H[c] - H[n]) > 0.5]
    print('перепад покрытия между соседями > 0.5 —', len(jump) + len(R['bad']), jump[:3])
    edge = []
    for (x, z) in ((-660, 1794), (-660, 1816), (-660, 1813), (-660, 1820)):
        t = None
        for y in range(67, 60, -1):
            b = W.block(-661, y, z)
            if b not in ('air', 'plant'):
                n_, m_ = (b.split(':') + ['0'])[:2]
                t = y + (0.5 if n_ in ('stone_slab', 'stone_slab2') and int(m_) < 8 else 1.0); break
        if t is None or abs(t - H[(x, z)]) > 0.5: edge.append(((x, z), t, H[(x, z)]))
    print('со стыком (Старый город X −661) > 0.5 —', len(edge), edge[:3])
    fl = floating_over_paving(final, ALL, {c: H[c] for c in net if c != R['swing']})   # сиденье качелей висит по замыслу
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:4])
    low = [k for k, b in ALL.items() if b != 'air' and k[1] < 60 and RES(k[0], k[2])]
    print('в резерве трасс ниже Y 60 —', len(low), low[:4])
    digs = {}
    for (x, y, z), b in ALL.items():
        if b in ('air', 'water') and y <= W.surf(x, z): digs[(x, z)] = min(digs.get((x, z), 999), y)
    cv = W._cv
    roofs = []
    for (x, z), y in digs.items():
        ct = W.cave_top(x, z)
        if ct is None: continue
        i = (z - cv['z0']) * cv['w'] + x - cv['x0']
        air = [yy for yy in range(cv['minAir'][i], min(ct, y - 1) + 1) if final(x, yy, z) == 'air']
        if air: roofs.append((y - max(air) - 1, x, z))
    print(f'кровля каньона под выемками схемы (карманы заделаны: {R["plugged"]} бл.): мин.', min(roofs)[0] if roofs else '—', '(норма >= 3)')
    doors = [d for T in R['towers'] for d in T.doors]
    di = door_approach_issues(final, doors)
    print(f'подходы к наружным дверям: {len(doors)}, ошибок {len(di)}', di[:2])
    # проходимость — от проспекта, только по мощению, объектам и Старому городу (газоны не в счёт)
    walkable = net | R['seats'] | rect(-640, -638, 1781, 1788) | R['isl'] | rect(-653, -650, 1781, 1783) | \
        rect(-651, -650, 1788, 1792) | {c for T in R['towers'] for c in T.FP[0]}
    box = ((-664, -622), (1742, 1823), (58, 80))
    start = (-650, 64.5, 1816)

    def walk(fin):
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in walkable or x <= -661 else ('stone' if y < 60 else 'air')
        return dl.walk_reachable(f2, start, *box)
    seen = walk(final)
    occ = {(x, z) for (x, y, z), b in ALL.items() if (x, z) in net and b != 'air' and y >= math.ceil(H[(x, z)])}
    miss = [c for c in net if c not in occ and not dl.reached(seen, c[0], H[c], c[1])]
    print(f'ПРОХОДИМОСТЬ без прыжков от проспекта (−650,1816): клеток мощения {len(net) - len(occ)}, недостижимо {len(miss)}', miss[:6])
    top_seat = max(R['seats'], key=lambda c: (seat_row(c), -abs(c[1] - 1786)))
    targets = {'Старый город: Рыночный переулок (−662,1794)': (-662, 65.0, 1794), 'Старый город: проспект (−662,1816)': (-662, 64.5, 1816),
               'Парковая ул., север (−658,1745)': (-658, 64.5, 1745), 'Горная дорога, восток (−626,1771)': (-626, 64.5, 1771),
               'проспект, восток (−626,1816)': (-626, 64.5, 1816), '«зебра» (−647,1771)': (-647, 64.5, 1771),
               'ротонда на острове (−647,1782)': (-647, 64.0, 1782), 'сцена (−639,1784)': (-639, 64.5, 1784),
               f'верхний ряд театра {top_seat}': (top_seat[0], 64 + seat_row(top_seat) + 1.0, top_seat[1]),
               'конец причала (−650,1788)': (-650, 63.5, 1788), 'розарий, центр (−630,1805)': (-630, H[(-630, 1805)], 1805),
               'детская площадка, горка (−653,1807) верх': (-653, 67.0, 1807), 'песочница (−653,1803)': (-653, 64.0, 1803),
               'вестибюль «Парк» (−641,1810)': (-641, H[(-641, 1810)], 1810)}
    for T in R['towers']:
        targets.update(T.level_targets()); targets.update({f'{T.name}: {k}': v for k, v in T.targets.items()})
        for (x, y, z, m) in T.doors:
            a, b = DOOR_IN[m]; targets[f'{T.name}: перед дверью ({x},{z})'] = (x - a, y, z - b)
    bad_t = 0
    for k, (x, y, z) in targets.items():
        ok = dl.reached(seen, x, y, z); bad_t += 0 if ok else 1
        print(f'  маршрут → {k}: {ok}')
    # маршруты по отдельности: в кафе — только через северную дверь (западная перекрыта), в щитовую
    negc = dict(ALL); negc[(-645, 64, 1799)] = 'concrete:0'; negc[(-645, 65, 1799)] = 'concrete:0'
    s_n = walk(fin_of(negc))
    ok_n = all(dl.reached(s_n, *v) for k, v in targets.items() if k.startswith('Кафе'))
    print(f'  маршрут → кафе и щитовая только через северную дверь: {ok_n}')
    negc = dict(ALL); negc[(-641, 64, 1796)] = 'concrete:0'; negc[(-641, 65, 1796)] = 'concrete:0'
    s_w = walk(fin_of(negc))
    ok_w = all(dl.reached(s_w, *v) for k, v in targets.items() if k.startswith('Кафе'))
    print(f'  маршрут → кафе и щитовая только через западную дверь: {ok_w}')
    bad_t += (0 if ok_n else 1) + (0 if ok_w else 1)
    print('ИТОГО недостижимых точек:', len(miss) + bad_t)
    # негатив 1: мостик перекрыт стенкой в 2 блока — ротонда недостижима
    negc = dict(ALL)
    for z in (1781, 1782, 1783):
        for d in (64, 65): negc[(-652, d, z)] = 'stonebrick'
    print('НЕГАТИВ: мостик перекрыт — ротонда недостижима:', not dl.reached(walk(fin_of(negc)), -647, 64.0, 1782))
    # негатив 2: нижний ряд театра — полные блоки вместо ступенек: верхние ряды недостижимы
    negc = dict(ALL)
    for c in R['seats']:
        if seat_row(c) == 0: negc[(c[0], 64, c[1])] = 'quartz_block'
    print('НЕГАТИВ: нижний ряд театра без ступенек — верхний ряд недостижим:',
          not dl.reached(walk(fin_of(negc)), top_seat[0], 64 + seat_row(top_seat) + 1.0, top_seat[1]))
    # негатив 3: урна на блок выше мощения — висящие найдены
    negc = dict(ALL); c = (-649, 1794); negc[(c[0], math.ceil(H[c]), c[1])] = 'air'; negc[(c[0], math.ceil(H[c]) + 1, c[1])] = 'cauldron'
    print('НЕГАТИВ: урна на блок выше мощения — висящие найдены:', len(floating_over_paving(fin_of(negc), negc, {c: H[c]})) > 0)
    # негатив 4: газон перед северной дверью кафе — ошибка подхода найдена
    negc = dict(ALL); negc[(-641, 63, 1795)] = 'grass'; negc[(-646, 63, 1799)] = 'grass'
    print('НЕГАТИВ: газон перед дверью кафе — ошибка подхода найдена:', len(door_approach_issues(fin_of(negc), doors)) > 0)
    # негатив 5: перед скамейкой южной аллеи — живая изгородь: ошибка места для ног найдена
    o, rel, order = outs[NAMES[1]]
    negr = dict(rel)
    bx_, bz_, face = R['benches'][0]
    y0 = math.ceil(H[(bx_, bz_)]) - o[1]
    for i in range(1, 3): negr[(bx_ + i - o[0], y0, bz_ - 1 - o[2])] = 'leaves:4'
    terr = lambda x, y, z: (lambda b: 'stone' if b == 'ground' else ('air' if b == 'plant' else b))(
        G.c.get((x + o[0], y + o[1], z + o[2])) or W.block(x + o[0], y + o[1], z + o[2]))
    print('НЕГАТИВ: изгородь перед скамейкой: ошибок', len(dl.check_bench_front(negr, terr)), '(ждём > 0)')
    if args.preview: preview(args.preview, final, R, W)


def preview(path, final, R, W):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CX = dict(CL); CX.update({'sandstone:2': (225, 212, 160), 'sandstone:0': (215, 200, 150), 'stone_slab:1': (220, 208, 158),
                              'double_stone_slab:9': (230, 220, 170), 'quartz_block': (240, 238, 232), 'stone_slab:7': (236, 234, 228),
                              'stained_hardened_clay:14': (150, 60, 50), 'stained_hardened_clay:4': (190, 140, 40),
                              'quartz_stairs': (235, 232, 225), 'grass': (95, 150, 60), 'water': (70, 130, 215), 'sand': (220, 210, 150),
                              'leaves:4': (60, 120, 40), 'leaves:6': (110, 150, 60), 'planks:5': (70, 50, 30), 'wooden_slab:5': (80, 58, 35),
                              'red_flower': (220, 60, 90), 'double_plant': (200, 40, 60), 'concrete:0': (235, 235, 235),
                              'wool:11': (50, 70, 170), 'wool:0': (240, 240, 240), 'stained_glass:3': (150, 200, 235), 'sea_lantern': (200, 230, 230)})
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    X0, X1, Z0, Z1 = -664, -621, 1741, 1823
    S = 10
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 40 + 520, mh + 60), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 110
            while y > 40 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'stone' and (x, z) not in R['net']:
                k = (max(60, min(y, 85)) - 60) / 25; c = (int(200 - 70 * k), int(210 - 40 * k), int(140 - 60 * k))
            else: c = cc(b)
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
            if (x, z) in R['H'] and R['H'][(x, z)] != int(R['H'][(x, z)]):
                dr.line([20 + (x - X0) * S + 1, 30 + (z - Z0) * S + S - 2, 20 + (x - X0) * S + S - 2, 30 + (z - Z0) * S + 1], fill=(90, 90, 90))
    for x in range(-660, X1 + 1, 10): dr.text((20 + (x - X0) * S - 8, 16), str(x), fill='black', font=F(10))
    for z in range(1750, Z1 + 1, 10): dr.text((0, 30 + (z - Z0) * S - 5), str(z), fill='black', font=F(9))
    dr.text((20, 2), 'Парк, этап 1 (park-1-ground + park-1-build) — вид сверху; косая черта — полублок', fill='black', font=F(12))
    bx = mw + 50; S2 = 6

    def profile(y0, label, pts, lab, yr=(58, 80)):
        dr.text((bx, y0 - 14), label, fill='black', font=F(11))
        for u, (x, z) in enumerate(pts):
            for y in range(yr[0], yr[1] + 1):
                b = final(x, y, z)
                if b == 'air': continue
                n = b.split(':')[0]
                c = (150, 140, 110) if b == 'stone' else cc(b)
                yy = y0 + (yr[1] - y) * S2
                half = n in ('stone_slab', 'wooden_slab') and int((b.split(':') + ['0'])[1]) < 8
                dr.rectangle([bx + u * S2, yy + (S2 // 2 if half else 0), bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
            if u % 10 == 0: dr.text((bx + u * S2, y0 + (yr[1] - yr[0] + 1) * S2 + 1), str(lab(x, z)), fill='black', font=F(8))
    profile(30, 'разрез Z=1785: Парковая ул. — озеро — сцена — театр, X −664…−621', [(x, 1785) for x in range(-664, -620)], lambda x, z: x)
    profile(215, 'разрез Z=1782: мостик — ротонда — озеро, X −664…−621', [(x, 1782) for x in range(-664, -620)], lambda x, z: x)
    profile(400, 'разрез X=−641: Горная дорога — озеро — кафе — проспект, Z 1766…1822',
            [(-641, z) for z in range(1766, 1823)], lambda x, z: z)
    profile(585, 'разрез X=−651: озеро — причал — лодочная станция — площадка, Z 1780…1822',
            [(-651, z) for z in range(1780, 1823)], lambda x, z: z)
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
