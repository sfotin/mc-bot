"""Промзона, этап 1 (CITY.md §7.9, геометрия — tools/city/plan_industry_v1.py). Три схемы, строить строго по
порядку, каждую — отдельным .cmd и только после итога «ошибок 0» у предыдущей:

- industry-1-ground.json — закладка пустот третьей ветки каньона под площадкой (колонны, где пустота выше
  Y 54, — камнем от Y 54 до площадки; по съёмке r.-2.3.mca — docs/terrain/industry-voids.json), площадка
  25 чанков (верх Y 66, газон), откосы ≤ 1:1 к рельефу вокруг (засыпка ручья у набережной X −660…−657),
  проезды (гладкий камень, края — каменный кирпич, пандусы полублоками по 0.5): Заводская ул. от тротуара
  главного проспекта, Береговой проезд от улицы набережной (бортик X −661 в створе разобран),
  Промышленный пр.; подходы к дверям корпусов этапа 1, дорожка к градирням; свет — морские фонари вровень
  с мощением;
- industry-1-npp.json — корпус АЭС: 4 зала (каждый в своём чанке; северные — обычные реакторы,
  южные — жидкостные, над ними купола-гермооболочки), внутренние двери, щитовая с кабельной шахтой,
  вентиляционная труба; две градирни (гиперболоид Ø 13 → 9, до Y 99; проходы 3 бл. по сторонам света;
  в основании — бассейн, вода 2 слоя — источник для помп);
- industry-1-halls.json — цех переработки руд и производственный цех (кирпич, шедовая кровля со
  стеклом на север), центральный склад (песчаник, свод из терракоты); в каждом — щитовая с кабельной
  шахтой (люк iron_trapdoor:8 вровень с полом, стремянка до Y 60 — к будущей техгалерее).
Механизмы IC2/AE2 ставит владелец; модовых блоков в схемах нет.

Запуск: gen_industry_1.py [--outdir schemas] [--preview docs/districts/industry-1-preview.png]
Мир — World() (участок) + съёмка промзоны docs/terrain/industry-voids.json (пустоты под площадкой и
рельеф к востоку и югу от участка). После постройки — built_before('industry-1-ground.json').
Проверки: опоры/вода/порядок (decor_lib, порядок бота) для каждой схемы; проходимость без прыжков
(от тротуара проспекта и от улицы набережной — к каждой двери, в каждый зал и щитовую, в градирни);
подходы к наружным дверям; свет ≥ 8 на всех ходовых клетках; уклоны пандусов; задетое построенное;
кровля пустот ≥ 3 под постройками; корпуса и залы в своих чанках; негативные прогоны.
"""
import argparse
import json
import math
import os
import sys
from collections import deque

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import World, REPO, BUILT, built_before, save_schema, dl, col  # noqa: E402,F401
from oldtown_lib import door_approach_issues  # noqa: E402
from gen_park_1 import h32  # noqa: E402
import plan_industry_v1 as PI  # noqa: E402

NAMES = ['industry-1-ground.json', 'industry-1-npp.json', 'industry-1-halls.json']
TOP = 66                                   # верх площадки и полов; ходим 67.0
FILL_Y = 54                                # закладка пустот — от Y 54 до площадки
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
DOOR_IN = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
LADDER_META = {(0, -1): 3, (0, 1): 2, (-1, 0): 5, (1, 0): 4}
ROAD, EDGE, ROAD_S, EDGE_S = 'double_stone_slab', 'stonebrick', 'stone_slab', 'stone_slab:5'
FLOOR, LAMP, PLATE = 'stone:6', 'sea_lantern', 'stone_pressure_plate'
POND = (-660, -657, 1847, 1857)            # ручей у конца улицы набережной — засыпается под Береговым
ALLOW = {(-661, y, z) for y in range(63, 68) for z in range(1850, 1856)}   # бортик набережной в створе
STAGE1 = ('npp', 'ct1', 'ct2', 'ore', 'prod', 'wh')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'industry-1-preview.png'))
    return p.parse_args()


def rc(x0, x1, z0, z1):
    return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def obj(k):
    return next(o for o in PI.OBJ if o[0] == k)


# =========================================================================================================
class Terrain:
    """Рельеф: участок — World, вне участка (восток, юг) — съёмка industry-voids.json; пустоты — съёмка."""

    def __init__(self, W):
        self.W = W
        d = json.load(open(os.path.join(REPO, 'docs', 'terrain', 'industry-voids.json')))
        self.d, self.x0, self.z0, self.w, self.h = d, d['x0'], d['z0'], d['w'], d['h']

    def _i(self, x, z):
        if not (0 <= x - self.x0 < self.w and 0 <= z - self.z0 < self.h): return None
        return (z - self.z0) * self.w + x - self.x0

    def ground(self, x, z):
        if self.W.inside(x, z): return self.W.ground(x, z)
        return self.d['ground'][self._i(x, z)]

    def water(self, x, z):
        return self.W.water(x, z) if self.W.inside(x, z) else None

    def vtop(self, x, z):                   # верх растительности (деревья) или None
        if self.W.inside(x, z):
            t = self.W.top(x, z)
            return t if t is not None and t > self.W.ground(x, z) else None
        return None

    def voids(self, x, z):
        i = self._i(x, z)
        return [] if i is None else self.d['voids'][i]

    def built(self, x, z):
        return any((x, y, z) in self.W.pre for y in range(58, 80))

    def block(self, x, y, z):
        """Блок исходного мира (до этапа): участок — World (пустоты съёмки — воздух), вне — съёмка."""
        for a, b, t in self.voids(x, z):
            if a <= y <= b and (x, y, z) not in self.W.pre: return {'a': 'air', 'w': 'water', 'l': 'lava'}[t]
        if self.W.inside(x, z): return self.W.block(x, y, z)
        return 'ground' if y <= self.ground(x, z) else 'air'


# =========================================================================================================
class Plan:
    def __init__(self, W):
        self.W, self.T = W, Terrain(W)
        self.G, self.N, self.H = {}, {}, {}
        self.surf = {}            # (x, z) -> ходовая высота мощения/газона площадки
        self.paved = {}           # (x, z) -> высота мощения (проезды, подходы, дорожки)
        self.targets = {}         # группа -> [(x, ноги, z)] — свет и проходимость
        self.doors = []           # наружные двери (x, y, z, meta)
        self.rooms = {}           # имя -> клетка внутри (x, ноги, z)
        self.halls = {}           # имя -> клетка внутри
        self.lamp_c = {}          # схема -> [(x, y, z)] кандидаты под фонари в полу
        self.fill_cols = 0


# ----------------------------------------------------------------------------- площадка и проезды
def road_profiles():
    """Ходовая высота проездов: пандусы по 0.5 не чаще чем через 3 бл."""
    H, edge = {}, set()
    r1 = {1821: 65.0, 1822: 65.0}
    for z in range(1823, 1936): r1[z] = min(67.0, 65.5 + 0.5 * ((z - 1823) // 3))
    r3 = {-661: 65.0, -660: 65.0}
    for x in range(-659, -592): r3[x] = min(67.0, 65.5 + 0.5 * ((x + 659) // 3))
    for x in range(-627, -621):
        for z in range(1821, 1936):
            H[(x, z)] = r1[z]
            if x in (-627, -622): edge.add((x, z))
    for x in range(-661, -592):
        for z in range(1850, 1856):
            if (x, z) not in H: H[(x, z)] = r3[x]
            if z in (1850, 1855) and not -627 <= x <= -622: edge.add((x, z))
    for x in range(-656, -592):
        for z in range(1885, 1891):
            if (x, z) not in H: H[(x, z)] = 67.0
            if z in (1885, 1890) and not -627 <= x <= -622: edge.add((x, z))
    for x in (-627, -622):                                  # перекрёстки — без поперечного края
        for z in list(range(1850, 1856)) + list(range(1885, 1891)): edge.discard((x, z))
    edge.discard((-656, 1885)); edge.discard((-656, 1890))
    return H, edge, r1, r3


def build_ground(P):
    W, T, G = P.W, P.T, P.G
    PL = {(x, z) for (cx, cz) in PI.LOADER for x in range(cx * 16, cx * 16 + 16) for z in range(cz * 16, cz * 16 + 16)}
    RH, EDGES, r1, r3 = road_profiles()
    AP = {}
    for k, rects in PI.APRONS.items():
        if k not in ('ore', 'prod', 'wh', 'ct'): continue
        for r in rects:
            for c in rc(*r): AP[c] = 67.0
    paved = {**RH, **AP}
    P.paved = paved
    core = PL | set(paved)
    # ходовая высота площадки: мощение — по профилю; газон — 67, но не выше мощения + расстояние (откос 1:1)
    S = {c: 67.0 for c in core}
    S.update(paved)
    low = {c: h for c, h in paved.items() if h < 67}
    dist = {c: 0 for c in low}
    q = deque(low)
    best = dict(low)
    while q:
        c = q.popleft()
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n not in core or n in paved: continue
            v = math.floor(best[c]) + 1 if c in paved else best[c] + 1
            if n not in best or v < best[n]:
                best[n] = v; q.append(n)
    for c, v in best.items():
        if c not in paved: S[c] = min(67.0, float(math.floor(v)))
    # откосы вокруг: BFS-границы lo/hi от края, ≤ 1:1
    lo, hi = {}, {}
    q = deque()
    for c in core:
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n in core: continue
            s = math.floor(S[c])
            if n not in lo or s - 1 > lo[n]: lo[n] = s - 1
            if n not in hi or s + 1 < hi[n]: hi[n] = s + 1
            q.append(n)
    band = {}
    while q:
        c = q.popleft()
        if c in band: continue
        x, z = c
        if T.built(x, z) or z <= 1820 or (x, z) in core or (not W.inside(x, z) and T._i(x, z) is None): continue
        nat = T.ground(x, z) + 1
        new = min(max(nat, lo[c]), hi[c])
        if POND[0] <= x <= POND[1] and POND[2] <= z <= POND[3] and T.water(x, z):
            new = max(new, T.water(x, z) + 1)
        band[c] = new
        if new == nat: continue
        for a, b in N4:
            n = (x + a, z + b)
            if n in core or n in band: continue
            l2, h2 = new - 1, new + 1
            if n not in lo or l2 > lo[n]: lo[n] = l2
            if n not in hi or h2 < hi[n]: hi[n] = h2
            q.append(n)
    P.band = band
    # 1) закладка пустот: колонны, где пустота выше Y 54, — камень от Y 54 до основания площадки
    cols = core | set(band)
    for (x, z) in cols:
        if any(b >= FILL_Y for a, b, t in T.voids(x, z)):
            top = (math.floor(S[(x, z)]) - 1) if (x, z) in S else band[(x, z)] - 3
            for y in range(FILL_Y, min(top, T.ground(x, z)) + 1): G[(x, y, z)] = 'stone'
            P.fill_cols += 1
    # 2) площадка
    for (x, z) in core:
        nat = T.ground(x, z)
        h = S[(x, z)]
        top = math.ceil(h) - 1                       # верхний блок (полный или полублок)
        half = h != int(h)
        is_pv = (x, z) in paved
        for y in range(nat + 1, top - 1): G[(x, y, z)] = 'stone'
        if is_pv:
            if top - 1 > nat or (x, top - 1, z) not in G: G[(x, top - 1, z)] = 'stone'
            e = (x, z) in EDGES
            if half: G[(x, top - 1, z)] = EDGE if e else ROAD; G[(x, top, z)] = EDGE_S if e else ROAD_S
            else: G[(x, top, z)] = EDGE if e else ROAD
        else:
            G[(x, top - 1, z)] = 'dirt'; G[(x, top, z)] = 'grass'
        up = max(nat, T.vtop(x, z) or nat, top)
        w = T.water(x, z)
        if w is not None: up = max(up, w)
        for y in range(top + 1, up + 1): G[(x, y, z)] = 'air'
        if (x, z) in ALLOW_COLS:
            for y in range(top + 1, 68): G[(x, y, z)] = 'air'
    # 3) откосы
    for (x, z), new in band.items():
        nat = T.ground(x, z) + 1
        w = T.water(x, z)
        t = new - 1
        under = w is not None and t + 1 <= w
        if new > nat:
            for y in range(nat, t): G[(x, y, z)] = 'stone' if y < t - 1 else 'dirt'
            G[(x, t, z)] = 'dirt' if under else 'grass'
            if t - 1 >= nat: G[(x, t - 1, z)] = 'dirt'
        elif new < nat:
            G[(x, t, z)] = 'dirt' if under else 'grass'
            if t - 1 > FILL_Y: G[(x, t - 1, z)] = 'dirt'
            for y in range(t + 1, nat): G[(x, y, z)] = 'water' if (w is not None and y <= w) else 'air'
        up = T.vtop(x, z)
        if up:
            for y in range(max(t, nat - 1) + 1, up + 1):
                if (x, y, z) not in G: G[(x, y, z)] = 'air'
    # кандидаты под фонари: мощение с полным блоком сверху, не края, не перед дверями
    P.road_lamp_c = [(x, math.ceil(h) - 1, z) for (x, z), h in paved.items() if h == int(h) and (x, z) not in EDGES]
    P.targets['проезды и подходы'] = [(x, h, z) for (x, z), h in paved.items()]
    P.S = S
    P.core = core


ALLOW_COLS = {(-661, z) for z in range(1850, 1856)}


# ----------------------------------------------------------------------------- здания: общие
class B:
    """Короб здания rect=(x0, x1, z0, z1) — стены по периметру, пол Y 66, внутри воздух до кровли."""

    def __init__(self, P, D, name, rect, top, wall, roof, sch):
        self.P, self.D, self.name, self.rect, self.top, self.wall, self.roof, self.sch = P, D, name, rect, top, wall, roof, sch
        x0, x1, z0, z1 = rect
        self.inner = rc(x0 + 1, x1 - 1, z0 + 1, z1 - 1)
        self.ring = rc(x0, x1, z0, z1) - self.inner
        self.res = set()                 # клетки пола под плитами/шахтами — не под фонари
        self.walls_in = set()            # внутренние стены (x, z)

    def put(self, x, y, z, b): self.D[(x, y, z)] = b

    def box(self, wall_fn=None):
        for (x, z) in self.ring:
            self.put(x, TOP, z, self.wall)
            for y in range(TOP + 1, self.top): self.put(x, y, z, wall_fn(x, y, z) if wall_fn else self.wall)
            self.put(x, self.top, z, self.roof)
        for (x, z) in self.inner:
            self.put(x, TOP, z, FLOOR)
            for y in range(TOP + 1, self.top): self.put(x, y, z, 'air')
            self.put(x, self.top, z, self.roof)

    def iwall(self, cells, mat):
        for (x, z) in cells:
            for y in range(TOP + 1, self.top): self.put(x, y, z, mat)
            self.walls_in.add((x, z))

    def door(self, x, z, meta, outside=True, kind='dark_oak_door'):
        self.put(x, TOP + 1, z, f'{kind}:{meta}'); self.put(x, TOP + 2, z, f'{kind}:8')
        self.put(x, TOP, z, self.wall if (x, z) in self.ring else FLOOR)
        for y in range(TOP + 3, TOP + 4):
            if self.D.get((x, y, z)) == 'air': self.put(x, y, z, self.wall)
        a, b = DOOR_IN[meta]
        self.put(x + a, TOP + 1, z + b, PLATE); self.res.add((x + a, z + b))
        if not outside:
            self.put(x - a, TOP + 1, z - b, PLATE); self.res.add((x - a, z - b))
        else:
            self.P.doors.append((x, TOP + 1, z, meta))

    def room(self, rname, rect, door, shaft, mat):
        """Щитовая: внутренность rect, стены mat кольцом (кроме наружных стен), потолок Y 70, дверь,
        кабельная шахта 1×1 до Y 60 со стремянкой и люком iron_trapdoor:8 вровень с полом."""
        x0, x1, z0, z1 = rect
        ring = rc(x0 - 1, x1 + 1, z0 - 1, z1 + 1) - rc(x0, x1, z0, z1)
        for (x, z) in ring:
            if (x, z) in self.ring: continue
            for y in range(TOP + 1, TOP + 5): self.put(x, y, z, mat)
            self.walls_in.add((x, z))
        for (x, z) in rc(x0, x1, z0, z1):
            for y in range(TOP + 1, TOP + 4): self.put(x, y, z, 'air')
            self.put(x, TOP + 4, z, mat)
        dx_, dz_, meta = door
        self.door(dx_, dz_, meta, outside=False)
        sx, sz, att = shaft
        for y in range(60, TOP): self.put(sx, y, sz, f'ladder:{LADDER_META[att]}')
        self.put(sx, TOP, sz, 'iron_trapdoor:8')
        self.put(sx, 59, sz, 'stonebrick')
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                if (a, b) != (0, 0):
                    for y in range(59, TOP): self.put(sx + a, y, sz + b, 'stonebrick')
        self.res |= {(sx, sz)}
        self.P.rooms[f'{self.name}: {rname}'] = ((x0 + x1) // 2, TOP + 1, (z0 + z1) // 2)
        self.room_cells = rc(x0, x1, z0, z1)

    def floor_targets(self):
        cells = [(x, z) for (x, z) in self.inner if (x, z) not in self.walls_in]
        self.P.targets[self.name] = [(x, TOP + 1, z) for (x, z) in cells]
        self.P.lamp_c.setdefault(self.sch, []).extend((x, TOP, z) for (x, z) in cells if (x, z) not in self.res)


def windows(x, z, y, period, lo, hi, rect, phase=2):
    x0, x1, z0, z1 = rect
    if not lo <= y <= hi: return False
    if x in (x0, x1) and z in (z0, z1): return False
    along = x - x0 if z in (z0, z1) else z - z0
    return along % period == phase


# ----------------------------------------------------------------------------- корпус АЭС
def build_npp(P):
    D = P.N
    o = obj('npp'); x0, x1, z0, z1 = o[2:6]
    top = 83
    rect = (x0, x1, z0, z1)
    pil = lambda x, z: (x in (x0, x1) and z in (z0, z1)) or (z in (z0, z1) and (x - x0) % 7 == 0) or (x in (x0, x1) and (z - z0) % 7 == 0)

    def wall_fn(x, y, z):
        if pil(x, z): return 'concrete:8'
        if y <= TOP + 1: return 'concrete:8'
        if windows(x, z, y, 7, 71, 80, rect, phase=3) or windows(x, z, y, 7, 71, 80, rect, phase=4): return 'glass_pane'
        return 'concrete:0'
    b = B(P, D, 'Корпус АЭС', rect, top, 'concrete:8', 'concrete:8', NAMES[1])
    b.box(wall_fn)
    XW, ZW = -608, 1904                                  # внутренние стены по границам чанков
    b.iwall({(XW, z) for z in range(z0 + 1, z1)} | {(x, ZW) for x in range(x0 + 1, x1)}, 'concrete:0')
    for (x, z) in b.ring:                                # парапет
        b.put(x, top + 1, z, 'stone_slab:7')
    # двери: наружные на запад (Заводская), внутренние в восточные залы
    b.door(x0, 1897, 0)
    b.door(x0, 1912, 0)
    b.door(XW, 1897, 0, outside=False)
    b.door(XW, 1912, 0, outside=False)
    # щитовая в зале 1 (СЗ угол) с шахтой
    b.room('щитовая', (-620, -618, 1892, 1894), (-619, 1895, 3), (-620, 1892, (-1, 0)), 'concrete:0')
    # свет на стенах залов: морские фонари в стенах на 74 и 79 через 5 (внутренний вид), не в окнах
    for y in (74, 79):
        for (x, z) in b.ring:
            if pil(x, z) and not (x in (x0, x1) and z in (z0, z1)): b.put(x, y, z, LAMP)
        for (x, z) in list(b.walls_in):
            if (x == XW and (z - z0) % 5 == 0 and z not in (1897, 1912, ZW)) or (z == ZW and (x - x0) % 5 == 0 and x != XW):
                if b.D.get((x, y, z)) == 'concrete:0': b.put(x, y, z, LAMP)
    # купола над жидкостными залами (полые, открыты в зал)
    for cx, cz, r in ((-614.5, 1911.5, 5.5), (-600.5, 1911.5, 5.5)):
        for x in range(math.floor(cx - r), math.ceil(cx + r) + 1):
            for z in range(math.floor(cz - r), math.ceil(cz + r) + 1):
                for y in range(top, top + 7):
                    d = math.sqrt((x - cx) ** 2 + (z - cz) ** 2 + (y - top) ** 2)
                    if d <= r:
                        inner = d <= r - 1.1
                        if y == top and inner: b.put(x, y, z, 'air')
                        elif y == top: b.put(x, y, z, 'concrete:8')
                        else: b.put(x, y, z, 'air' if inner else ('concrete:8' if y == top + 1 else 'concrete:0'))
    # вентиляционная труба на стыке залов
    for x in range(XW - 1, XW + 2):
        for z in range(ZW - 1, ZW + 2):
            for y in range(top + 1, 116):
                b.put(x, y, z, 'concrete:14' if y in (104, 105, 110, 111, 114, 115) else 'concrete:0')
    b.floor_targets()
    P.halls.update({'АЭС: зал 1 (обычный реактор)': (-614, 67, 1898), 'АЭС: зал 2 (обычный реактор)': (-600, 67, 1898),
                    'АЭС: зал 3 (жидкостный)': (-614, 67, 1912), 'АЭС: зал 4 (жидкостный)': (-600, 67, 1912)})
    P.npp = b


# ----------------------------------------------------------------------------- градирни
def tower_r(y):
    t = (y - 67) / 32
    return 6.5 - 2.4 * math.sin(min(t / 0.78, 1) * math.pi / 2) + (0.7 * (t - 0.78) / 0.22 if t > 0.78 else 0)


def build_tower(P, k, cx, cz):
    D = P.N
    ring_feet = []
    for y in range(TOP, 100):
        r = tower_r(y) if y > TOP else 6.5
        for x in range(cx - 7, cx + 8):
            for z in range(cz - 7, cz + 8):
                d = math.hypot(x - cx, z - cz)
                if y == TOP:
                    if d <= 6.5:
                        if d <= 2.5: D[(x, y, z)] = 'water'; D[(x, y - 1, z)] = 'water'; D[(x, y - 2, z)] = 'stone'
                        elif d <= 5.5:
                            D[(x, y, z)] = FLOOR
                            if d <= 5.25: ring_feet.append((x, z))
                        else: D[(x, y, z)] = 'concrete:7'
                    continue
                if d <= r and d > r - 1.25:
                    leg = y <= TOP + 3
                    door = leg and (abs(x - cx) <= 1 or abs(z - cz) <= 1)
                    D[(x, y, z)] = 'air' if door else ('concrete:0' if y >= 98 else 'concrete:8')
                elif d <= r - 1.25:
                    D[(x, y, z)] = 'air'
    # проходы 3 бл. по сторонам света — пол под ними (клетки вне круга до 6.5)
    for a, b in N4:
        for s in range(5, 8):
            for w in (-1, 0, 1):
                x, z = cx + a * s + (w if a == 0 else 0), cz + b * s + (w if b == 0 else 0)
                if (x, z) not in P.paved: D[(x, TOP, z)] = FLOOR
                for y in range(TOP + 1, TOP + 4): D[(x, y, z)] = 'air'
                ring_feet.append((x, z))
    # перемычки над проходами (y 70) — оболочка уже сплошная выше ног; свет в оболочке через ≤ 5 по высоте
    for y in range(72, 98, 5):
        r = tower_r(y)
        n = max(6, int(2 * math.pi * r / 5))
        for i in range(n):
            ang = 2 * math.pi * (i + (0.5 if (y // 5) % 2 else 0)) / n
            x, z = round(cx + (r - 0.6) * math.cos(ang)), round(cz + (r - 0.6) * math.sin(ang))
            if D.get((x, y, z), '').startswith('concrete'): D[(x, y, z)] = LAMP
    # бортик бассейна вровень (вода Y 66, мощение Y 66 — выход без прыжка): ничего не надо
    ring_feet = sorted(set(ring_feet))
    P.targets[f'градирня {k}'] = [(x, TOP + 1, z) for (x, z) in ring_feet]
    P.lamp_c.setdefault(NAMES[1], []).extend((x, TOP, z) for (x, z) in ring_feet
                                             if 2.5 < math.hypot(x - cx, z - cz) <= 5.25)
    P.halls[f'градирня {k}, у бассейна'] = (cx + 4, TOP + 1, cz)


# ----------------------------------------------------------------------------- цеха с шедовой кровлей
def build_sawtooth(P, k, doors, room):
    D = P.H
    o = obj(k); x0, x1, z0, z1 = o[2:6]
    R = 77
    rect = (x0, x1, z0, z1)

    def T(x):                                           # верх кровли над колонной x внутри
        kk = (x - (x0 + 1)) % 5
        return {0: 81, 1: 80, 2: 79, 3: 78, 4: R}[kk], kk
    pil = lambda x, z: (x in (x0, x1) and z in (z0, z1)) or (z in (z0, z1) and (x - x0) % 5 == 1) or (x in (x0, x1) and (z - z0) % 5 == 0)

    def wall_fn(x, y, z):
        if pil(x, z) or y <= TOP + 1: return 'stonebrick'
        if windows(x, z, y, 5, 69, 74, rect, phase=3) or windows(x, z, y, 5, 69, 74, rect, phase=4) or \
                (x in (x0, x1) and windows(x, z, y, 5, 69, 74, rect, phase=2)): return 'glass_pane'
        return 'brick_block'
    b = B(P, D, o[1], rect, R, 'stonebrick', 'brick_block', NAMES[2])
    b.box(wall_fn)
    for x in range(x0 + 1, x1):
        t, kk = T(x)
        for z in range(z0, z1 + 1):
            edge = z in (z0, z1)
            if kk == 4: continue
            for y in range(R, t + 1):
                if edge:
                    b.put(x, y, z, 'brick_block')
                    continue
                if kk == 0:
                    b.put(x, y, z, 'air' if y == R else ('glass_pane' if y < t else 'brick_block'))
                else:
                    b.put(x, y, z, f'brick_stairs:1' if y == t else 'air')
    for z in range(z0, z1 + 1):                          # торцы — до кровли, парапет
        for x in (x0, x1):
            b.put(x, R + 1, z, 'stone_slab:5')
    for x in range(x0, x1 + 1):
        if T(x)[1] == 4 or x in (x0, x1):
            for z in (z0, z1): b.put(x, R + 1, z, 'stone_slab:5')
    for (x, z, m) in doors: b.door(x, z, m)
    b.room('щитовая', *room, 'stonebrick')
    # свет на стенах (пилястры) на 72
    for (x, z) in b.ring:
        if pil(x, z) and not (x in (x0, x1) and z in (z0, z1)) and (x, z) not in {(d[0], d[1]) for d in doors}:
            b.put(x, 72, z, LAMP)
    b.floor_targets()
    P.halls[o[1]] = ((x0 + x1) // 2, TOP + 1, (z0 + z1) // 2)
    return b


# ----------------------------------------------------------------------------- склад со сводом
def build_warehouse(P):
    D = P.H
    o = obj('wh'); x0, x1, z0, z1 = o[2:6]
    WT = 74
    cx = (x0 + x1) / 2
    half = (x1 - x0) / 2
    H = {x: WT + max(0, round(4.4 * math.sqrt(max(0.0, 1 - ((x - cx) / (half + 0.5)) ** 2)))) for x in range(x0, x1 + 1)}
    rect = (x0, x1, z0, z1)
    pil = lambda x, z: (x in (x0, x1) and z in (z0, z1)) or (x in (x0, x1) and (z - z0) % 4 == 0) or (z in (z0, z1) and (x - x0) % 7 == 0)

    def wall_fn(x, y, z):
        if pil(x, z): return 'sandstone:2'
        if y <= TOP + 1: return 'sandstone:2'
        if x in (x0, x1) and windows(x, z, y, 4, 69, 71, rect, phase=2): return 'glass_pane'
        return 'sandstone'
    b = B(P, D, o[1], rect, WT, 'sandstone:2', 'stained_hardened_clay:1', NAMES[2])
    b.box(wall_fn)
    for x in range(x0, x1 + 1):
        h = H[x]
        for z in range(z0, z1 + 1):
            side = x in (x0, x1) or z in (z0, z1)
            for y in range(WT, h): b.put(x, y, z, 'sandstone' if side else 'air')
            b.put(x, h, z, 'stained_hardened_clay:1')
    # фронтоны: круглое окно-витраж (оранжевое стекло) в центре торцов
    for z in (z0, z1):
        for x in range(x0 + 5, x1 - 4):
            for y in (WT + 1, WT + 2):
                if abs(x - cx) <= 1.5 and y < H[x] - 1: b.put(x, y, z, 'stained_glass_pane:1')
    b.door(-611, z1, 3)
    b.door(x0, 1838, 0)
    b.room('щитовая', (-607, -605, 1831, 1833), (-606, 1834, 3), (-605, 1831, (1, 0)), 'sandstone:2')
    for (x, z) in b.ring:
        if x in (x0, x1) and (z - z0) % 4 == 0 and z not in (z0, z1, 1838): b.put(x, 72, z, LAMP)
        if z in (z0, z1) and (x - x0) % 7 == 0 and x not in (x0, x1): b.put(x, 72, z, LAMP)
    b.floor_targets()
    P.halls[o[1]] = (-611, TOP + 1, 1840)
    return b


# ----------------------------------------------------------------------------- свет
def man(a, b): return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def place_lamps(P, D, cands, targets, existing):
    """Жадное покрытие: каждая ходовая клетка — не дальше 7 по сумме осей от фонаря (свет ≥ 8)."""
    lit = lambda t, L: any(man(l, t) <= 7 for l in L)
    need = [t for t in targets if not lit((t[0], t[1] - 1, t[2]) if False else t, existing)]
    lamps = []
    cset = list(dict.fromkeys(cands))
    while need:
        best, cov = None, []
        for c in cset:
            cv = [t for t in need if man(c, t) <= 7]
            if len(cv) > len(cov): best, cov = c, cv
        if not best: break
        lamps.append(best); D[best] = LAMP
        cs = set(cov); need = [t for t in need if t not in cs]
        cset.remove(best)
    return lamps


# =========================================================================================================
def main():
    a = parse_args()
    W = World()
    P = Plan(W)
    build_ground(P)
    build_npp(P)
    build_tower(P, 1, -615, 1928)
    build_tower(P, 2, -600, 1928)
    build_sawtooth(P, 'ore', [(-644, 1859, 1), (-631, 1864, 2)],
                   ((-655, -653, 1866, 1868), (-652, 1867, 2), (-655, 1868, (-1, 0))))
    build_sawtooth(P, 'prod', [(-631, 1877, 2), (-644, 1882, 3)],
                   ((-655, -653, 1874, 1876), (-652, 1875, 2), (-655, 1874, (-1, 0))))
    build_warehouse(P)
    # свет
    exist = {NAMES[1]: [k for k, b in P.N.items() if b == LAMP], NAMES[2]: [k for k, b in P.H.items() if b == LAMP]}
    tg = lambda names: [t for n in names for t in P.targets[n]]
    P.lamps = {}
    P.lamps[NAMES[0]] = place_lamps(P, P.G, P.road_lamp_c, [(x, math.floor(h), z) for (x, h, z) in P.targets['проезды и подходы']], [])
    P.lamps[NAMES[1]] = place_lamps(P, P.N, P.lamp_c[NAMES[1]], tg(['Корпус АЭС', 'градирня 1', 'градирня 2']), exist[NAMES[1]])
    hall_names = [obj(k)[1] for k in ('ore', 'prod', 'wh')]
    P.lamps[NAMES[2]] = place_lamps(P, P.H, P.lamp_c[NAMES[2]], tg(hall_names), exist[NAMES[2]])
    outs = {}
    for nm, D in zip(NAMES, (P.G, P.N, P.H)):
        os.makedirs(a.outdir, exist_ok=True)
        o, rel, order, dims = save_schema(dict(D), os.path.join(a.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(D)}')
    checks(W, P, outs, a)


# =========================================================================================================
def checks(W, P, outs, a):
    T = P.T
    print('== ПРОВЕРКИ ==')
    print(f'закладка пустот: колонн {P.fill_cols}, блоков камня в схеме ground от Y {FILL_Y}')

    def base(x, y, z):
        b = T.block(x, y, z)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
    prevs = {NAMES[0]: {}, NAMES[1]: dict(P.G), NAMES[2]: {**P.G, **P.N}}
    for nm, D in zip(NAMES, (P.G, P.N, P.H)):
        o, rel, order = outs[nm]
        prev = prevs[nm]

        def terr(x, y, z, o=o, prev=prev):
            k = (x + o[0], y + o[1], z + o[2])
            b = prev.get(k)
            return b if b is not None else base(*k)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:6]: print('   ', m)
    ALL = {**P.G, **P.N, **P.H}

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z))
            if b is None: b = base(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    # вода, открытая в воздух (вода схемы рядом с воздухом сбоку/снизу)
    wo = [k for k, b in ALL.items() if b == 'water' and any(final(k[0] + a_, k[1] + b_, k[2] + c_) == 'air'
                                                          for a_, b_, c_ in ((1, 0, 0), (-1, 0, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))]
    print(f'вода, открытая в воздух (сбоку или снизу): {len(wo)}', wo[:3])
    # задетое построенное
    hit = [k for k, b in ALL.items() if k in W.pre and W.pre[k] != b and k not in ALLOW
           and W.pre[k] not in ('air', 'grass', 'dirt', 'stone')]
    print('задеты построенные (вне бортика набережной в створе Берегового и откосов холма E):', len(hit), hit[:4])
    # проходимость
    box = ((-664, -588), (1816, 1940), (60, 90))
    starts = {'тротуар проспекта (−624, 1820)': (-624, 65.0, 1820), 'улица набережной (−663, 1852)': (-663, 65.0, 1852)}
    seen = {k: dl.walk_reachable(final, s, *box) for k, s in starts.items()}
    tgts = {}
    for (x, y, z, m) in P.doors:
        dx, dz = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}[m]
        tgts[f'перед дверью ({x}, {z})'] = (x + dx, 67.0, z + dz)
    for k, c in {**P.halls, **P.rooms}.items(): tgts[k] = (c[0], float(c[1]), c[2])
    bad = 0
    for sk, s in seen.items():
        for k, t in tgts.items():
            ok = dl.reached(s, *t); bad += 0 if ok else 1
            if not ok or sk.startswith('тротуар'): print(f'  маршрут {sk} → {k}: {ok}')
    print('ИТОГО недостижимых точек:', bad)
    # мощение без стоянки на своей высоте (дыры, ступеньки)
    gaps = [c for c, h in P.paved.items() if not dl.reached(seen['тротуар проспекта (−624, 1820)'], c[0], h, c[1])]
    print('разрывов дорожки', len(gaps), gaps[:4])
    # подходы к дверям
    di = door_approach_issues(final, P.doors)
    print(f'подходы к наружным дверям: {len(P.doors)}, ошибок {len(di)}', di[:3])
    # уклоны мощения: соседние клетки мощения не больше 0.5
    steep = [(c, n) for c, h in P.paved.items() for a_, b_ in N4 for n in [(c[0] + a_, c[1] + b_)]
             if n in P.paved and abs(P.paved[n] - h) > 0.5]
    print('перепад мощения больше 0.5 между соседями —', len(steep), steep[:3])
    # свет
    lamps = [k for k, b in ALL.items() if b == LAMP]
    tl = [(x, math.floor(h), z) for g, ts in P.targets.items() for (x, h, z) in ts]
    dark = [t for t in tl if not any(man(l, t) <= 7 for l in lamps)]
    print(f'клетки без света (фонарь дальше 7 бл. по сумме осей, свет меньше 8): {len(dark)}', dark[:5],
          f'| фонарей: проезды {len(P.lamps[NAMES[0]])}, АЭС и градирни {len(P.lamps[NAMES[1]])}, цеха {len(P.lamps[NAMES[2]])}')
    # залы реакторов в своих чанках (по построенному воздуху внутри)
    hall_ch = {}
    for n, x0, x1, z0, z1, _ in PI.HALLS:
        air = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if final(x, 70, z) == 'air']
        ch = {(x >> 4, z >> 4) for x, z in air}
        hall_ch[n] = (len(air), sorted(ch))
        wall_ok = all(final(x, 70, z) != 'air' for x, z in rc(x0 - 1, x1 + 1, z0 - 1, z1 + 1) - rc(x0, x1, z0, z1))
        print(f'  {n}: воздух {len(air)} кл. в чанках {sorted(ch)}, стены вокруг сплошные: {wall_ok}')
    print('залы реакторов в одном чанке — ошибок', sum(1 for v in hall_ch.values() if len(v[1]) != 1))
    # корпуса в 25 чанках
    outside = sorted({(x >> 4, z >> 4) for (x, y, z) in {**P.N, **P.H} if (x >> 4, z >> 4) not in PI.LOADER})
    print(f'вне района (корпуса вне 25 чанков): {len(outside)}', outside[:4])
    # кровля пустот ≥ 3 под постройками (после закладки)
    low = []
    lo = {}
    for (x, y, z), b in ALL.items():
        if b in ('air', 'water') or y < 59: continue
        lo[(x, z)] = min(lo.get((x, z), 999), y)
    for (x, z), y in lo.items():
        tv = [yy for a_, b_, t in T.voids(x, z) for yy in range(a_, min(b_, y - 1) + 1) if final(x, yy, z) in ('air', 'water', 'lava')]
        if tv and y - max(tv) - 1 < 3: low.append((x, z, y, max(tv)))
    print('кровля каньона меньше 3 бл. под постройками (после закладки):', len(low), low[:4])
    # лава/вода из пустот рядом с закладкой не открыта в воздух — пустоты ниже Y 54 остаются закрытыми
    # негативы
    neg = dict(ALL)
    for z in range(1895, 1900): neg[(-622, 66, z)] = 'air'; neg[(-622, 65, z)] = 'air'; neg[(-622, 64, z)] = 'air'
    for x in range(-627, -621):
        for y in (64, 65, 66): neg[(x, y, 1896)] = 'air'
    sN = dl.walk_reachable(fin_of(neg), (-624, 65.0, 1820), *box)
    print('НЕГАТИВ: Заводская перекопана у АЭС — зал 1 недостижим:', not dl.reached(sN, -614, 67.0, 1898))
    neg = dict(ALL); neg[(-608, 67, 1897)] = 'concrete:0'; neg[(-608, 68, 1897)] = 'concrete:0'
    sN = dl.walk_reachable(fin_of(neg), (-624, 65.0, 1820), *box)
    print('НЕГАТИВ: внутренняя дверь АЭС заложена — зал 2 недостижим:', not dl.reached(sN, -600, 67.0, 1898))
    some = P.lamps[NAMES[2]][0]
    dk = [t for t in tl if not any(man(l, t) <= 7 for l in lamps if l != some)]
    print('НЕГАТИВ: убран фонарь в цеху — тёмные клетки найдены:', len(dk) > 0)
    nd = [(d[0], d[1], d[2], d[3]) for d in P.doors[:1]]
    neg = dict(ALL); dx, dz = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}[nd[0][3]]
    neg[(nd[0][0] + dx, 66, nd[0][2] + dz)] = 'grass'
    print('НЕГАТИВ: газон перед дверью — найдено:', len(door_approach_issues(fin_of(neg), nd)) > 0)
    neg = dict(ALL)
    for x in range(-620, -609): neg[(x, 70, 1904)] = 'air'
    ch = {(x >> 4, z >> 4) for x in range(-620, -608) for z in range(1892, 1919) if fin_of(neg)(x, 70, z) == 'air' and z in range(1892, 1919)}
    print('НЕГАТИВ: проём в стене между залами 1 и 3 — зал в двух чанках:', len(ch) > 1)
    if a.preview: preview(a.preview, final, W, P, ALL)


# =========================================================================================================
def preview(path, final, W, P, ALL):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1, S = -666, -586, 1814, 1942, 6
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    S2 = 5
    secs = [('Разрез по Z 1912 (запад → восток): машинный зал (этап 2 — пусто), Заводская, жидкостные залы АЭС, купола',
             [(x, 1912) for x in range(-660, -588)], (52, 118)),
            ('Разрез по X −615 (север → юг): склад, Береговой, цех автокрафта (этап 2), диспетчерская (этап 2), АЭС, градирня',
             [(-615, z) for z in range(1816, 1940)], (52, 118)),
            ('Разрез по X −644 (север → юг): оранжерея (этап 3), цех руд, производственный цех (шеды), насосная (этап 2)',
             [(-644, z) for z in range(1816, 1910)], (52, 90))]
    sw = max(len(c) for _, c, _ in secs) * S2
    sh = sum((y1 - y0 + 1) * S2 + 34 for _, _, (y0, y1) in secs)
    img = Image.new('RGB', (max(mw + 50, sw + 60), mh + 40 + sh + 20), (250, 250, 247)); dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            c = None
            for y in range(118, 50, -1):
                b = final(x, y, z) if (W.inside(x, z) or (x, y, z) in ALL or P.T._i(x, z) is not None) else 'air'
                if b in ('air', 'plant') or b.endswith('pressure_plate') or 'door' in b: continue
                nat = (x, y, z) not in ALL and (x, y, z) not in W.pre
                if b == 'water': c = (120, 170, 225)
                elif nat and b in ('stone', 'ground'): c = (150, 175, 110)
                elif b == 'grass': c = (125, 175, 95)
                else: c = col(b)
                k = max(0, min(1, (y - 60) / 50))
                c = tuple(int(v * (0.75 + 0.35 * k)) if v * (0.75 + 0.35 * k) < 255 else 255 for v in c)
                break
            if c is None: c = (225, 225, 225)
            dr.rectangle([25 + (x - X0) * S, 25 + (z - Z0) * S, 25 + (x - X0 + 1) * S - 1, 25 + (z - Z0 + 1) * S - 1], fill=c)
    for x in range(X0, X1 + 1):
        if x % 16 == 0: dr.line([25 + (x - X0) * S, 25, 25 + (x - X0) * S, 25 + mh], fill=(60, 60, 60), width=1)
    for z in range(Z0, Z1 + 1):
        if z % 16 == 0: dr.line([25, 25 + (z - Z0) * S, 25 + mw, 25 + (z - Z0) * S], fill=(60, 60, 60), width=1)
    dr.text((25, 6), 'Промзона, этап 1: вид сверху (верх построенного, сетка — чанки) и разрезы; ground + npp + halls', fill='black', font=F(12))
    oy = mh + 40
    for title, cols_, (y0, y1) in secs:
        dr.text((25, oy), title, fill='black', font=F(11)); oy += 16
        for u, (x, z) in enumerate(cols_):
            for y in range(y0, y1 + 1):
                b = final(x, y, z) if (W.inside(x, z) or P.T._i(x, z) is not None) else 'air'
                if b in ('air', 'plant'): continue
                c = (120, 170, 225) if b == 'water' else (230, 100, 20) if b == 'lava' else \
                    (150, 135, 105) if b in ('stone', 'ground') and (x, y, z) not in ALL else col(b)
                yy = oy + (y1 - y) * S2
                dr.rectangle([25 + u * S2, yy, 25 + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
        oy += (y1 - y0 + 1) * S2 + 18
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
