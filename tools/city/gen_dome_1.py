"""Подводный купол, этап 1 одной порцией (CITY.md §7.8, геометрия — tools/city/plan_dome_v1.py).

Три схемы (строить строго по порядку, каждая — после полного окончания предыдущей):
- dome-1-ground.json — «сухой короб»: всё, что держит воду, — оболочки купола, станции «Купол», галереи,
  трубы и тоннеля метро, полы, опоры и подсыпки; срезка дна вокруг купола (клетки — вода). Внутренности,
  где сейчас вода, заполняются камнем-времянкой: воздуха рядом с водой в этой схеме нет, и вода ни во что
  не протекает, в каком бы порядке бот ни ставил боксы. Правило стенок (решение владельца): где снаружи
  вода — стекло блоками (над водой — голубое крашеное), где порода — облицовка каменным кирпичом,
  построенное (стенка набережной, мощение) — не трогается;
- dome-1-build.json — внутренности купола, станции «Купол», галереи и павильона (воздух вместо времянки и
  породы), сад (газон, деревья, клумбы, цветы), скамейки у стекла, лестница галереи (кварц), павильон на
  острове A и дорожка от моста, фонарь;
- dome-1-metro.json — станция «Набережная» (зал, лестница с променада с проёмом и ограждением), рампа,
  тоннель и труба, путь: рельсы, ускоряющие рельсы на блоках редстоуна (рампа — все, по ровному — через 8),
  на концах — тормозной ускоряющий рельс, упор и кнопка запуска.
Свет — морские фонари (жадное покрытие: до каждой клетки, где стоит человек, ≤ 7 по сумме осей).

Запуск: gen_dome_1.py [--outdir schemas] [--preview docs/districts/dome-1-preview.png]
Мир — World(ext=True) (после постройки — built_before('dome-1-ground.json')).
Проверки: опоры/вода/порядок (decor_lib, порядок бота) для каждой схемы; протечки (после ground внутри
объёмов воды нет; в итоге у воздуха внутри нет соседа-воды); проходимость без прыжков (мост → павильон →
галерея → купол → скамейки; купол → станция «Купол»; променад → платформа «Набережная»); ширина 3;
свет; рельсы (опора, редстоун под ускоряющими, упоры, кнопки, просвет); скамейки; задетое построенное;
кровля каньона; негативные прогоны.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import World, REPO, BUILT, built_before, save_schema, dl, col  # noqa: E402
from gen_park_1 import h32, bench  # noqa: E402
import plan_dome_v1 as PD  # noqa: E402

NAMES = ['dome-1-ground.json', 'dome-1-build.json', 'dome-1-metro.json']
SEA = PD.SEA
GLASS, TINT, LINE = 'glass', 'stained_glass:3', 'stonebrick'
RIB, QZ, PILLAR = 'concrete:0', 'quartz_block', 'quartz_block:2'
PAVE, LAMP = 'sandstone:2', 'sea_lantern'
EARTH = PD.EARTH
N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
CX, CZ = PD.DOME_C
FY = PD.DOME_FY                                       # пол купола (газон) Y 52, ноги 53
A, C = PD.DOME_RH + 0.5, PD.DOME_RV + 0.5            # радиусы внешнего объёма (центры клеток)
HUB = PD.HUB                                          # X −752…−744, Z 1942…1950
TZ = PD.TRACK_Z                                       # путь в зале станции «Купол» — Z 1948
DOOR_Z = (1944, 1945, 1946)                           # проём станция → купол
PAV = PD.PAV                                          # X −759…−753, Z 1903…1909, пол 63, ноги 64
GX = PD.GAL_X                                         # внутренность галереи X −757…−755
HALL = PD.ST_N                                        # зал «Набережной»: X −708…−699, Z 1850…1858, ноги 57
SFEET = PD.ST_FEET
STAIR_X = (-709, -707)                                # лестница с променада между кадками, вход с юга (Z 1867)
BTN_N = ((-701, -702), 1850)                          # «Набережная»: столб X −701, кнопка X −702 (смотрит на запад)


def is_water(b): return b == 'water' or b.startswith('flowing_water')


def is_rock(b): return b == 'ground' or b.split(':')[0] in EARTH


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'dome-1-preview.png'))
    return p.parse_args()


# =========================================================================================================
class Plan:
    """Всё о постройке в абсолютных координатах: три словаря клеток и служебные множества."""

    def __init__(self, W):
        self.W = W
        self.G, self.B, self.M = {}, {}, {}
        self.INT = {}                 # внутренность (воздух в итоге) -> 'B' | 'M'
        self.BODY = set()             # клетки ступеней/рельсов в объёме (тоже за «стенкой»)
        self.OPEN = set()             # соседи внутренности, которые не заделывать (проёмы на воздух)
        self.feet = {}                # (x, z) -> ноги (для света и проверок) по объектам
        self.lamp_c = {}              # группа -> кандидаты под фонари
        self.targets = {}             # группа -> клетки (x, ноги, z), которым нужен свет
        self.track = []               # (x, z, ноги, блок рельса)
        self.allow_built = set()      # построенное, которое заменяем по замыслу (проём в стенке, вход в метро)
        self.CUT = {}                 # срезка дна (вода) — в схему ground последней, где нет другой постройки

    def wb(self, x, y, z): return self.W.block(x, y, z)

    def interior(self, c, owner, group=None):
        self.INT[c] = owner


# ----------------------------------------------------------------------------- купол
def dome_volume():
    def inV(x, y, z):
        return y >= FY + 1 and ((x - CX) ** 2 + (z - CZ) ** 2) / A ** 2 + ((y - FY) / C) ** 2 <= 1
    V = {(x, y, z) for x in range(CX - 17, CX + 18) for z in range(CZ - 17, CZ + 18) for y in range(FY + 1, FY + 16)
         if inV(x, y, z)}
    shell = {c for c in V if any((c[0] + a, c[1] + b, c[2] + d) not in V for a, b, d in N6 if b >= 0)}
    return V, shell, V - shell


def build_dome(P):
    V, shell, inner = dome_volume()
    P.dome_shell, P.dome_inner = shell, inner
    foot = {(x, z) for (x, y, z) in V if y == FY + 1}
    P.dome_foot = foot
    inner_cols = {(x, z) for (x, y, z) in inner if y == FY + 1}
    r = lambda x, z: math.hypot(x - CX, z - CZ)
    # пол и подсыпка
    for (x, z) in foot:
        g = P.W.ground(x, z)
        for y in range(g + 1, FY - 1): P.G[(x, y, z)] = 'stone'
        if (x, z) not in inner_cols: P.G[(x, FY, z)] = QZ; P.G[(x, FY - 1, z)] = 'stone'; continue
        rr = r(x, z)
        paved = rr >= 9.5 or rr <= 2.5 or abs(x - CX) <= 1 or abs(z - CZ) <= 1
        P.G[(x, FY - 1, z)] = 'stone' if paved else 'dirt'
        P.G[(x, FY, z)] = PAVE if paved else 'dirt'
        if not paved: P.B[(x, FY, z)] = 'grass'
        P.feet[(x, z)] = FY + 1
    # оболочка: стекло блоками, рёбра — 8 меридианов (белый бетон)
    for (x, y, z) in shell:
        dx, dz = x - CX, z - CZ
        P.G[(x, y, z)] = RIB if (dx == 0 or dz == 0 or abs(dx) == abs(dz)) else GLASS
    for c in inner: P.interior(c, 'B')
    P.targets['купол'] = [(x, FY + 1, z) for (x, z) in inner_cols]
    # срезка дна вокруг (откос 1:1 от бровки в 2 бл.), клетки — вода
    for x in range(CX - 26, CX + 27):
        for z in range(CZ - 26, CZ + 27):
            if (x, z) in foot: continue
            d = r(x, z) - A
            if d > 10 or d < 0: continue
            g = P.W.ground(x, z)
            tgt = FY - 1 + max(0, math.ceil(d) - 2)
            if g <= tgt or not P.W.water(x, z): continue
            for y in range(tgt + 1, min(g, SEA) + 1): P.CUT[(x, y, z)] = 'water'
    return inner_cols


def dome_garden(P, inner_cols):
    """Деревья, скамейки у стекла, цветы; фонари — потом (жадное покрытие)."""
    trunks, benches_at = set(), []
    for sx, sz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        tx, tz = CX + 6 * sx, CZ + 6 * sz
        trunks.add((tx, tz))
        for y in range(FY + 1, FY + 6): P.B[(tx, y, tz)] = 'log:0' if (sx * sz > 0) else 'log:2'
        leaf = 'leaves:4' if sx * sz > 0 else 'leaves:6'
        for y, rad in ((FY + 4, 2), (FY + 5, 2), (FY + 6, 1), (FY + 7, 0)):
            for a in range(-rad, rad + 1):
                for b in range(-rad, rad + 1):
                    if rad == 2 and abs(a) == 2 and abs(b) == 2: continue
                    if rad == 1 and abs(a) + abs(b) > 1: continue
                    k = (tx + a, y, tz + b)
                    if (a or b) or y > FY + 5: P.B[k] = leaf
    # скамейки у стекла лицом наружу: север, юг, запад (восток — проём на станцию)
    benches_at.append(bench(P.B, CX - 2, FY + 1, CZ - 13, 'n'))
    benches_at.append(bench(P.B, CX - 2, FY + 1, CZ + 13, 's'))
    benches_at.append(bench(P.B, CX - 13, FY + 1, CZ - 2, 'w'))
    P.bench_cells = {(x, z) for cells in benches_at for (x, z) in cells}
    P.bench_fronts = [(CX - 1, FY + 1, CZ - 14), (CX - 1, FY + 1, CZ + 14), (CX - 14, FY + 1, CZ - 1)]
    P.trunks = trunks
    P.lamp_c['купол'] = [(x, FY, z) for (x, z) in inner_cols if (x, z) not in trunks and (x, z) not in P.bench_cells]


def put(D, x, y, z, b): D[(x, y, z)] = b


class _D(dict):
    """Словарь клеток с методом put (для gen_park_1.bench)."""
    def put(self, x, y, z, b): self[(x, y, z)] = b


# ----------------------------------------------------------------------------- станция «Купол» и проём
def build_hub(P):
    x0, x1, z0, z1 = HUB
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            g = P.W.ground(x, z)
            for y in range(g + 1, FY): P.G[(x, y, z)] = 'stone'
            P.G[(x, FY, z)] = QZ
            edge_x, edge_z = x in (x0, x1), z in (z0, z1)
            for y in range(FY + 1, FY + 5):
                if edge_x and edge_z: P.G[(x, y, z)] = PILLAR
                elif edge_x or edge_z: P.G[(x, y, z)] = GLASS
                else: P.interior((x, y, z), 'B')
            P.G[(x, FY + 5, z)] = QZ if (edge_x or edge_z) else GLASS
            if not (edge_x or edge_z): P.feet[(x, z)] = FY + 1
    for z in DOOR_Z:                                   # проём в купол: стена станции X −752 и оболочка X −753
        for x in (x0, x0 - 1):
            for y in range(FY + 1, FY + 4): P.G.pop((x, y, z), None); P.interior((x, y, z), 'B')
            P.G[(x, FY, z)] = QZ; P.feet[(x, z)] = FY + 1
    for z in (TZ - 1, TZ, TZ + 1):                     # проём для трубы в восточной стене
        for y in range(FY + 1, FY + 4): P.G.pop((x1, y, z), None); P.interior((x1, y, z), 'M')
    P.targets['станция «Купол»'] = [(x, FY + 1, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1) if z != TZ] + \
        [(x, FY + 1, z) for z in DOOR_Z for x in (x0, x0 - 1)]
    P.lamp_c['станция «Купол»'] = [(x, FY, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1) if z not in (TZ, TZ - 1)]


# ----------------------------------------------------------------------------- галерея и павильон
def build_gallery(P):
    prof = PD.gallery_profile()
    ceil = PD.gallery_ceiling(prof)
    zs = sorted(prof)
    steps = {z for z in zs if z - 1 in prof and prof[z] < prof[z - 1]}
    P.gal_prof, P.gal_steps = prof, steps
    tg = []
    for z in zs:
        f = prof[z]
        stand = f + 1 if z in steps else f
        for x in range(GX[0], GX[1] + 1):
            if (x, FY + 1, z) in P.dome_inner and f == FY + 1:
                continue                                 # уже внутри купола
            if z in steps:
                P.BODY.add((x, f, z)); P.B[(x, f, z)] = 'quartz_stairs:3'; P.G[(x, f - 1, z)] = QZ
                lo = f + 1
            else:
                P.G[(x, f - 1, z)] = QZ; lo = f
            for y in range(lo, ceil[z]):
                if (x, y, z) not in P.dome_inner: P.interior((x, y, z), 'B')
            P.feet[(x, z)] = stand
            tg.append((x, stand, z))
        # опоры под стенками через 4 ряда
        if z % 4 == 0:
            for x in (GX[0] - 1, GX[1] + 1):
                g = P.W.ground(x, z)
                for y in range(g + 1, f - 1): P.G[(x, y, z)] = LINE
    P.targets['галерея'] = tg
    P.gal_roof = [(x, ceil[z], z) for z in zs for x in range(GX[0], GX[1] + 1) if (x, ceil[z], z) not in P.dome_shell
                  and (x, ceil[z], z) not in P.dome_inner]
    # павильон
    x0, x1, z0, z1 = PAV
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            g = P.W.ground(x, z)
            for y in range(g + 1, 63): P.B[(x, y, z)] = 'stone'
            P.B[(x, 63, z)] = QZ
            ex, ez = x in (x0, x1), z in (z0, z1)
            door = (x == x0 and z0 + 2 <= z <= z0 + 4) or (z == z1 and GX[0] <= x <= GX[1])
            for y in range(64, 67):
                if door or not (ex or ez): P.B[(x, y, z)] = 'air'
                else: P.B[(x, y, z)] = PILLAR if (ex and ez) else TINT
            P.B[(x, 67, z)] = QZ if (ex or ez) else TINT
            for y in range(68, max(g, 67) + 3):
                if P.W.block(x, y, z) != 'air': P.B[(x, y, z)] = 'air'
            if not (ex or ez) or door: P.feet[(x, z)] = 64
    for z in range(z0 + 2, z0 + 5):
        for y in range(64, 67): P.OPEN.add((x0 - 1, y, z))
    P.B[(x0 + 3, 67, z0 + 3)] = LAMP
    P.targets['павильон'] = [(x, 64, z) for x in range(x0 + 1, x1) for z in range(z0 + 1, z1)]
    for x in range(GX[0], GX[1] + 1):                  # стык павильон → галерея: внутренность галереи начинается Z 1910
        for y in range(64, 67): P.OPEN.add((x, y, z1))
    # дорожка от моста (Z 1902–1903, ноги 64) к западной двери павильона
    path = PD.ISLE_PATH
    for (x, z) in path:
        g = P.W.ground(x, z)
        for y in range(g + 1, 63): P.B[(x, y, z)] = 'stone'
        P.B[(x, 63, z)] = PAVE
        for y in range(64, max(g, P.W.top(x, z) or 0) + 2):
            if P.W.block(x, y, z) != 'air': P.B[(x, y, z)] = 'air'
        P.feet[(x, z)] = 64
    pc = set(path)
    for (x, z) in path:                                # облицовка срезов грунта у дорожки
        for a, b in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            n = (x + a, z + b)
            if n in pc or PAV[0] <= n[0] <= PAV[1] and PAV[2] <= n[1] <= PAV[3]: continue
            if P.W.block(n[0], 63, n[1]) != 'ground' and (n[0], 63, n[1]) not in P.W.pre: continue
            for y in range(64, P.W.ground(*n) + 1):
                if (n[0], y, n[1]) not in P.W.pre: P.B[(n[0], y, n[1])] = LINE
    P.targets['дорожка'] = [(x, 64, z) for (x, z) in path]
    P.lamp_c['дорожка'] = [(x, 63, 1905) for x in range(-767, -759)]          # фонари вровень с мощением, по оси


# ----------------------------------------------------------------------------- метро
def build_metro(P):
    tr = PD.metro_track()
    fz = {}
    for (x, z, f) in tr: fz[(x, z)] = f
    hx0, hx1, hz0, hz1 = HALL
    # зал «Набережной»
    for x in range(hx0, hx1 + 1):
        for z in range(hz0, hz1 + 1):
            P.G[(x, SFEET - 1, z)] = 'stone:6'
            for y in range(SFEET, SFEET + 4): P.interior((x, y, z), 'M')
            P.feet[(x, z)] = SFEET
    P.targets['зал «Набережная»'] = [(x, SFEET, z) for x in range(hx0, hx1 + 1) for z in range(hz0, hz1 + 1) if x != PD.TRACK_X]
    P.lamp_c['зал «Набережная»'] = [(x, SFEET + 4, z) for x in range(hx0, hx1 + 1) for z in range(hz0, hz1 + 1)]
    # лестница с променада: ступени на юг вверх, Z 1859…1866, вход с Z 1867 (ноги 65)
    sprof = {}
    for z in range(hz1 + 1, 1867): sprof[z] = SFEET + (z - hz1) - 1    # блок ступени: 1859 -> 57 … 1866 -> 64
    stand = {z: sprof[z] + 1 for z in sprof}
    stand[hz1] = SFEET; stand[1867] = 65
    tg_st, hole = [], set()
    for z in sorted(sprof):
        roof = max(stand[z - 1], stand[z], stand[z + 1]) + 3
        for x in range(STAIR_X[0], STAIR_X[1] + 1):
            P.BODY.add((x, sprof[z], z)); P.M[(x, sprof[z], z)] = 'stone_brick_stairs:2'
            P.G[(x, sprof[z] - 1, z)] = LINE
            top = min(roof - 1, 64)
            for y in range(sprof[z] + 1, top + 1): P.interior((x, y, z), 'M')
            if roof - 1 >= 64:
                hole.add((x, z))
                for y in range(65, 68): P.OPEN.add((x, y, z))
            P.feet[(x, z)] = stand[z]; tg_st.append((x, stand[z], z))
    for x in range(STAIR_X[0], STAIR_X[1] + 1):        # вход с юга: над Z 1867 — воздух, не заделывать
        for y in range(65, 68): P.OPEN.add((x, y, 1867))
        for y in range(64, 67): P.OPEN.add((x, y, 1867))
    P.hole = hole
    for (x, z) in hole:
        for y in range(62, 65): P.allow_built.add((x, y, z))
    # ограждение проёма (стекло-панели, голубые) — по бокам и с севера, вход с юга
    hz = sorted({z for _, z in hole})
    for z in hz:
        for x in (STAIR_X[0] - 1, STAIR_X[1] + 1): P.M[(x, 65, z)] = 'stained_glass_pane:3'
    for x in range(STAIR_X[0] - 1, STAIR_X[1] + 2): P.M[(x, 65, hz[0] - 1)] = 'stained_glass_pane:3'
    P.targets['лестница «Набережной»'] = tg_st
    P.stair_lamp_c = [(x, sprof[z] + 2, z) for z in sprof for x in (STAIR_X[0] - 1, STAIR_X[1] + 1) if sprof[z] + 2 <= 61]
    # путь: зал, тоннель, рампа, труба
    tg_t, lc_t = [], []
    for i, (x, z, f) in enumerate(tr):
        along_z = (x == PD.TRACK_X and z < TZ)
        inside_hall = hx0 <= x <= hx1 and hz0 <= z <= hz1
        inside_hub = HUB[0] < x < HUB[1] and HUB[2] < z < HUB[3]
        nb = [tr[j][2] for j in (i - 1, i, i + 1) if 0 <= j < len(tr)]
        top = max(nb) + 2
        offs = [(-1, 0), (0, 0), (1, 0)] if along_z else [(0, -1), (0, 0), (0, 1)]
        if (x, z) == (PD.TRACK_X, TZ): offs = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
        if not (inside_hall or inside_hub):
            for a, b in offs:
                cx_, cz_ = x + a, z + b
                if (cx_, f - 1, cz_) not in P.G or P.G[(cx_, f - 1, cz_)] == 'water': P.G[(cx_, f - 1, cz_)] = LINE
                for y in range(f, top + 1): P.interior((cx_, y, cz_), 'M')
                if (a, b) != (0, 0):
                    P.feet[(cx_, cz_)] = f; tg_t.append((cx_, f, cz_)); lc_t.append((cx_, f - 1, cz_))
            # опоры через 6 под краями пола, где под полом вода
            if i % 6 == 0:
                for a, b in (offs[0], offs[-1]):
                    g = P.W.ground(x + a, z + b)
                    for y in range(g + 1, f - 1): P.G[(x + a, y, z + b)] = LINE
        P.BODY.add((x, f, z))
    # стенка набережной над рампой: проём, стенка ляжет на свод
    for x in range(-702, -697):
        for y in range(50, 60): P.allow_built.add((x, y, 1869))
    P.targets['метро'] = tg_t
    P.lamp_c['метро'] = lc_t
    # рельсы
    n = len(tr)
    for i, (x, z, f) in enumerate(tr):
        prev_f = tr[i - 1][2] if i else f
        along_z = (x == PD.TRACK_X and z < TZ)
        if i == 0 or i == n - 1:
            rb = 'golden_rail:0' if along_z else 'golden_rail:1'           # тормоз на конце (без питания)
            P.M[(x, f, z)] = rb; P.track.append((x, z, f, rb)); continue
        if (x, z) == (PD.TRACK_X, TZ):
            rb = 'rail:8'                                                   # поворот: север + запад
        elif f < prev_f:
            rb = 'golden_rail:4'                                            # рампа: подъём к северу
        elif i % 8 == 0:
            rb = 'golden_rail:0' if along_z else 'golden_rail:1'
        else:
            rb = 'rail:0' if along_z else 'rail:1'
        P.M[(x, f, z)] = rb
        if rb.startswith('golden'): P.M[(x, f - 1, z)] = 'redstone_block'
        P.track.append((x, z, f, rb))
    # концы: упор и кнопка запуска
    (x, z, f, _) = P.track[0]                         # «Набережная», Z 1850, упор — стена Z 1849
    P.M[(BTN_N[0][0], f, z)] = PILLAR; P.M[(BTN_N[0][1], f, z)] = 'stone_button:2'
    (x, z, f, _) = P.track[-1]                        # «Купол», X −750: упор X −751, столб Z 1947, кнопка Z 1946
    P.M[(x - 1, f, z)] = QZ; P.M[(x, f, z - 1)] = PILLAR; P.M[(x, f, z - 2)] = 'stone_button:4'
    P.buttons = [(BTN_N[0][1], P.track[0][2], P.track[0][1]), (x, f, z - 2)]


# ----------------------------------------------------------------------------- заделка и времянка
def seal(P):
    W = P.W
    expl = lambda c: (c in P.G and P.G[c] != 'air') or (c in P.B and P.B[c] != 'air') or (c in P.M and P.M[c] != 'air')
    body = set(P.INT) | P.BODY
    added = {'стекло': 0, 'облицовка': 0, 'крашеное стекло': 0}
    for c in sorted(body):
        for a, b, d in N6:
            n = (c[0] + a, c[1] + b, c[2] + d)
            if n in body or n in P.OPEN or expl(n) or n in P.G: continue
            wb = 'water' if n in P.CUT else W.block(*n)
            if is_water(wb): m = GLASS if n[1] <= SEA else TINT
            elif is_rock(wb): m = LINE
            elif wb in ('air', 'plant'): m = TINT if n[1] > SEA else LINE
            else: continue                                # построенное — не трогаем
            P.G[n] = m
            added[{GLASS: 'стекло', LINE: 'облицовка', TINT: 'крашеное стекло'}[m]] += 1
    for c, b in P.CUT.items():
        if c not in P.G and c not in body: P.G[c] = b
    temp = 0
    for c in body:
        if is_water(W.block(*c)) and c not in P.G: P.G[c] = 'stone'; temp += 1
    # внутренность: воздух в своей схеме
    for c, o in P.INT.items():
        D = P.B if o == 'B' else P.M
        if c not in D: D[c] = 'air'
    return added, temp


# ----------------------------------------------------------------------------- свет
def man(a, b): return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def cover(targets, cands, R=7):
    un, lamps = set(targets), []
    cands = list(dict.fromkeys(cands))
    while un:
        best, bc = None, 0
        for c in cands:
            k = sum(1 for t in un if man(c, t) <= R)
            if k > bc: best, bc = c, k
        if not best: break
        lamps.append(best); un = {t for t in un if man(best, t) > R}
    return lamps, un


def lights(P):
    out = {}
    plan = [('дорожка', P.B), ('купол', P.B), ('станция «Купол»', P.G), ('галерея', None), ('зал «Набережная»', P.M), ('метро', P.G),
            ('лестница «Набережной»', P.M)]
    for grp, D in plan:
        tg = P.targets[grp]
        if grp == 'галерея': cands = P.gal_roof
        elif grp == 'лестница «Набережной»':
            cands = [c for c, b in P.G.items() if b == LINE and c[0] in (STAIR_X[0] - 1, STAIR_X[1] + 1) and 1859 <= c[2] <= 1866
                     and c[1] <= 63]
        else: cands = P.lamp_c[grp]
        # уже стоящие фонари покрывают
        have = [k for S_ in (P.G, P.B, P.M) for k, b in S_.items() if b == LAMP]
        tg = [t for t in tg if not any(man(h, t) <= 7 for h in have)]
        lamps, left = cover(tg, cands)
        for k in lamps:
            dst = P.M if grp in ('метро', 'зал «Набережная»', 'лестница «Набережной»') else P.B
            if grp in ('метро', 'станция «Купол»') and k in P.M and P.M[k] == 'redstone_block': continue
            dst[k] = LAMP
        out[grp] = (len(lamps), len(left))
    return out


# =========================================================================================================
def compose(W):
    P = Plan(W)
    inner_cols = build_dome(P)
    P.B = _D(P.B)
    dome_garden(P, inner_cols)
    build_hub(P)
    build_gallery(P)
    build_metro(P)
    added, temp = seal(P)
    lt = lights(P)
    # цветы на газоне — на оставшихся клетках
    fl = 0
    for (x, z) in inner_cols:
        if P.B.get((x, FY, z)) == 'grass' and P.B.get((x, FY + 1, z), 'air') == 'air' and (x, z) not in P.trunks:
            v = h32(x, z, 7)
            if v < 0.16 and (x, z) not in P.bench_cells:
                P.B[(x, FY + 1, z)] = ('red_flower:%d' % int(v * 50 % 9)) if v < 0.11 else 'yellow_flower'; fl += 1
    return P, added, temp, lt, fl


def main():
    a = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0]), ext=True) if NAMES[0] in names else World(ext=True)
    P, added, temp, lt, fl = compose(W)
    print(f'купол: оболочка {len(P.dome_shell)} кл., внутри {len(P.dome_inner)} | галерея: ступеней {len(P.gal_steps)} рядов | '
          f'путь {len(P.track)} бл. | заделка: {added} | времянка из камня (там, где вода) {temp} | цветов {fl}')
    print('свет (фонарей поставлено / клеток без покрытия):', {k: v for k, v in lt.items()})
    outs = {}
    for nm, D in zip(NAMES, (P.G, P.B, P.M)):
        o, rel, order, dims = save_schema(dict(D), os.path.join(a.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(D)}')
    checks(W, P, outs, a)


# =========================================================================================================
def checks(W, P, outs, a):
    print('== ПРОВЕРКИ ==')
    prevs = {NAMES[0]: {}, NAMES[1]: dict(P.G), NAMES[2]: {**P.G, **P.B}}
    for nm, D in zip(NAMES, (P.G, P.B, P.M)):
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
    ALL = {**P.G, **P.B, **P.M}

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    after_g = fin_of(P.G)
    # протечки
    body = set(P.INT) | P.BODY

    def leaks(fin):
        out = []
        for c in body:
            b0 = fin(*c)
            if is_water(b0): out.append((c, c)); continue
            if b0 == 'air' or any(t in b0 for t in ('rail', '_stairs', 'button', 'flower', 'pane')):
                for a_, b_, d_ in N6:
                    n = (c[0] + a_, c[1] + b_, c[2] + d_)
                    if is_water(fin(*n)): out.append((c, n))
        return out
    wet = [c for c in body if is_water(after_g(*c))]
    print('протечки после dome-1-ground (вода внутри объёмов):', len(wet), wet[:3])
    lk = leaks(final)
    print('протечки в итоге (воздух внутри рядом с водой):', len(lk), lk[:3])
    # задетое построенное
    hit = [k for k, b in ALL.items() if k in W.pre and W.pre[k] != b and W.pre[k] not in ('air',) and not is_water(W.pre[k])
           and W.pre[k].split(':')[0] not in EARTH and k not in P.allow_built]
    print('задеты построенные (вне проёма в стенке набережной и входа в метро):', len(hit), hit[:4])
    # проходимость
    def walk(fin, start, box):
        return dl.walk_reachable(fin, start, *box)
    box1 = ((-790, -738), (1898, 1966), (48, 72))
    seen = walk(final, (-766, 64.0, 1903), box1)
    tg = {'павильон (−756,1906)': (-756, 64.0, 1906), 'низ галереи (−756,1932)': (-756, 53.0, 1932),
          'купол, центр': (CX, 53.0, CZ), 'перед скамейкой N': P.bench_fronts[0], 'перед скамейкой S': P.bench_fronts[1],
          'перед скамейкой W': P.bench_fronts[2]}
    bad = 0
    for k, t in tg.items():
        ok = dl.reached(seen, *t); bad += 0 if ok else 1
        print(f'  маршрут мост → {k}: {ok}')
    seen2 = walk(final, (CX + 10, 53.0, CZ), box1)
    for k, t in {'станция «Купол», платформа (−748,1944)': (-748, 53.0, 1944), 'кнопка (−750,1946) — перед ней': (-749, 53.0, 1945)}.items():
        ok = dl.reached(seen2, *t); bad += 0 if ok else 1
        print(f'  маршрут купол → {k}: {ok}')
    box2 = ((-716, -694), (1846, 1872), (52, 72))
    seen3 = walk(final, (-708, 65.0, 1868), box2)
    for k, t in {'платформа «Набережной» (−704,1854)': (-704, 57.0, 1854), 'у кнопки (−703,1851)': (-703, 57.0, 1851)}.items():
        ok = dl.reached(seen3, *t); bad += 0 if ok else 1
        print(f'  маршрут променад → {k}: {ok}')
    print('ИТОГО недостижимых точек:', bad)
    # ширина галереи и лестницы по рядам
    narrow = []
    for z, f in P.gal_prof.items():
        if f != FY + 1 or z < 1930:
            w = sum(1 for x in range(GX[0] - 1, GX[1] + 2) if final(x, P.feet[(GX[0], z)] + 1, z) == 'air')
            if w < 3: narrow.append(z)
    for z in range(1859, 1867):
        w = sum(1 for x in range(STAIR_X[0] - 1, STAIR_X[1] + 2) if final(x, P.feet[(STAIR_X[0], z)] + 1, z) == 'air')
        if w < 3: narrow.append(z)
    print('узких рядов (уже 3 бл.):', len(narrow), narrow[:4])
    # свет
    lamps = [k for k, b in ALL.items() if b.split(':')[0] in ('sea_lantern', 'glowstone')]

    def dark_of(lamps_):
        tgs = [t for grp, ts in P.targets.items() for t in ts]
        return [t for t in tgs if not any(man(l, t) <= 7 for l in lamps_)]
    dk = dark_of(lamps)
    print('клетки без света (фонарь дальше 7 бл. по сумме осей, свет меньше 8 — мобы спавнятся):', len(dk), dk[:8])
    # рельсы
    def rail_issues(fin):
        out = []
        for i, (x, z, f, rb) in enumerate(P.track):
            b = fin(x, f, z)
            if 'rail' not in b: out.append(('нет рельса', (x, f, z))); continue
            under = fin(x, f - 1, z).split(':')[0]
            if under in ('air', 'water', 'glass', 'stained_glass') or 'pane' in under: out.append(('нет опоры', (x, f, z)))
            if b.startswith('golden') and 0 < i < len(P.track) - 1 and under != 'redstone_block': out.append(('без питания', (x, f, z)))
            if any(fin(x, y, z) != 'air' for y in (f + 1, f + 2)): out.append(('просвет', (x, f, z)))
        t0, t1 = P.track[0], P.track[-1]
        for stop in ((t0[0], t0[2], t0[1] - 1), (t1[0] - 1, t1[2], t1[1])):
            if fin(*stop) in ('air', 'water'): out.append(('нет упора', stop))
        for bt in P.buttons:
            if 'button' not in fin(*bt): out.append(('нет кнопки', bt))
        return out
    ri = rail_issues(final)
    print('рельсы: ошибок', len(ri), ri[:3], f'| путь {len(P.track)} бл., ускоряющих {sum(1 for t in P.track if t[3].startswith("golden"))}')
    # кровля каньона
    lo = {}
    for (x, y, z), b in ALL.items():
        if is_water(b): continue
        lo[(x, z)] = min(lo.get((x, z), 999), y)
    roofs = [(y - W.cave_top(x, z) - 1, (x, z)) for (x, z), y in lo.items() if W.cave_top(x, z) is not None and W.cave_top(x, z) < y]
    low = [r for r in roofs if r[0] < 3]
    print(f'кровля каньона меньше 3 бл. под постройками: {len(low)} колонн (мин. {min(roofs)[0] if roofs else "—"})')
    lodka = [b for b in PD.BOATS if any(abs(b[0] - k[0]) < 3 and abs(b[1] - k[2]) < 3 for k in ALL)]
    print('лодки владельца задеты:', len(lodka))
    # негативы
    neg = dict(ALL)
    z0 = sorted(P.gal_steps)[1]
    for x in range(GX[0], GX[1] + 1): neg[(x, P.gal_prof[z0], z0)] = QZ; neg[(x, P.gal_prof[z0] + 1, z0)] = QZ
    print('НЕГАТИВ: ступени галереи заложены — купол недостижим:', not dl.reached(walk(fin_of(neg), (-766, 64.0, 1903), box1), CX, 53.0, CZ))
    neg = dict(ALL); sc = sorted(c for c in P.dome_shell if c[1] == FY + 3 and c[2] == CZ and c[0] < CX)[0]; neg[sc] = 'water'
    print('НЕГАТИВ: снят блок оболочки купола — протечка найдена:', len(leaks(fin_of(neg))) > 0)
    neg_l = [l for l in lamps if l[1] == FY and abs(l[0] - CX) + abs(l[2] - CZ) < 12]
    print('НЕГАТИВ: убран фонарь в куполе — тёмные клетки найдены:', len(dark_of([l for l in lamps if l != neg_l[0]])) > 0 if neg_l else False)
    neg = dict(ALL); k = next((t for t in P.track if t[3] == 'golden_rail:4')); neg[(k[0], k[2] - 1, k[1])] = LINE
    print('НЕГАТИВ: под рельсом рампы нет редстоуна — найдено:', len(rail_issues(fin_of(neg))) > 0)
    if a.preview: preview(a.preview, final, W, P)


# =========================================================================================================
def preview(path, final, W, P):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1, S = -790, -694, 1846, 1965, 6
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    S2 = 7
    secs = [('Разрез по Z 1946 (купол, станция), X −790…−740', [(x, CZ) for x in range(-790, -739)], (40, 68)),
            ('Разрез по X −756 (павильон, галерея), Z 1900…1945', [(-756, z) for z in range(1900, 1946)], (40, 70)),
            ('Разрез по X −700 (метро у набережной), Z 1846…1885', [(-700, z) for z in range(1846, 1886)], (40, 68))]
    sh = sum((y1 - y0 + 1) * S2 + 30 for _, _, (y0, y1) in secs)
    img = Image.new('RGB', (max(mw + 50, 52 * S2 + 60), mh + 40 + sh + 20), (250, 250, 247)); dr = ImageDraw.Draw(img)
    ALL = {**P.G, **P.B, **P.M}
    tops = {}
    for (x, y, z), b in ALL.items():
        if b in ('air',) or is_water(b): continue
        if (x, z) not in tops or y > tops[(x, z)][0]: tops[(x, z)] = (y, b)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            if (x, z) in tops:
                c = col(tops[(x, z)][1])
                if tops[(x, z)][1] in (GLASS,): c = (175, 215, 235)
                if tops[(x, z)][1] == TINT: c = (120, 175, 225)
            else:
                g, w = W.ground(x, z), W.water(x, z)
                bl = W.block(x, max(g, w or 0) + 1, z)
                if (x, max(g, w or 0), z) in W.pre or any((x, y, z) in W.pre for y in range(60, 70)): c = (180, 172, 160)
                elif w: k = max(0, min(1, (SEA - g) / 30)); c = (int(150 - 110 * k), int(200 - 110 * k), int(230 - 80 * k))
                else: c = (190, 195, 140)
            dr.rectangle([25 + (x - X0) * S, 25 + (z - Z0) * S, 25 + (x - X0 + 1) * S - 1, 25 + (z - Z0 + 1) * S - 1], fill=c)
    dr.text((25, 6), 'Подводный купол, этап 1: вид сверху (верх построенного) и разрезы', fill='black', font=F(12))
    oy = mh + 40
    for title, cols_, (y0, y1) in secs:
        dr.text((25, oy), title, fill='black', font=F(11)); oy += 16
        for u, (x, z) in enumerate(cols_):
            for y in range(y0, y1 + 1):
                b = final(x, y, z)
                if b == 'air': continue
                c = (70, 130, 215) if is_water(b) else (150, 135, 105) if b in ('stone', 'ground') and (x, y, z) not in ALL \
                    else (175, 215, 235) if b == GLASS else (120, 175, 225) if b == TINT else col(b)
                yy = oy + (y1 - y) * S2
                dr.rectangle([25 + u * S2, yy, 25 + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
        oy += (y1 - y0 + 1) * S2 + 14
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
