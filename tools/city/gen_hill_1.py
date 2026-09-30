"""Холм E, этапы 1–2 одной порцией (CITY.md §7.6, план v1 — tools/city/plan_hill_v1.py, геометрия оттуда).

Две схемы:
- hill-1-ground.json — продолжение главного проспекта X −624…−593 (сечение как в парке, подъём по
  0.5), Башенная площадь и основание башни (мощение Y 78, ходим 79.0, узор — кварцевые кольца
  по песчанику, подсветка в мощении под башней), смотровая «Над парком», Северная лестница
  (2 марша по 7 ступеней, парапет со стороны долины) и Парадная лестница (центральный марш 7,
  площадка, боковые марши по 6, верхние площадки), парапеты по краю площади над обрывами,
  откосы 1:1 вместо выемок и насыпей, газоны, деревья, клумбы, фонари DECOR §3.2а, скамейки, урны;
- hill-1-tower.json — телебашня (schemas/ostankino.json, origin (−617, 78, 1779)) и её
  внутреннее: вестибюль в основании (city_lib.Tower, витражи, двери на север и юг, электрощитовая
  3×3 с кабельной шахтой), стремянка в стволе на центральной колонне с площадками отдыха через
  12 блоков, стеклянный пол в «тарелке» над стволом (кроме лаза), смотровая со скамейками и кафе
  «Седьмое небо» (столики, стойка).
Вне 25 чанков загрузчика — только декор (щитовая пустая).

Запуск: gen_hill_1.py [--outdir schemas] [--preview docs/districts/hill-1-preview.png]
Мир — World() (после постройки — built_before('hill-1-ground.json')).
Проверки: опоры + вода + порядок (decor_lib, порядок бота), перепад мощения, стык с парком,
перепад у края площади без парапета, проходимость без прыжков от проспекта до каждой клетки
мощения, до вестибюля, щитовой, каждой площадки стремянки и смотровой в «тарелке», подходы
к дверям, скамейки, висящие над мощением, резерв трасс, кровля каньона; негативные прогоны.
"""
import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import (World, REPO, BUILT, built_before, Tower, save_schema, DOOR_IN, N4, dl,  # noqa: E402
                      door_approach_issues, floating_over_paving, col, CL)
from gen_park_1 import Sch, h32, rect, tree, bench  # noqa: E402
import plan_hill_v1 as P  # noqa: E402

NAMES = ['hill-1-ground.json', 'hill-1-tower.json']
LAMP = ('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
PY = P.PLAZA_Y                                            # 78 — мощение площади, ходим 79.0
WALK = PY + 1
CX, CZ = P.TV_C                                           # центр башни (−606, 1790)
OX, OZ = CX - 11, CZ - 11                                 # origin башни
LADDER = (CX, CZ + 1)                                     # стремянка — с юга от колонны (CX, CZ)
POD = PY + 57                                             # пол «тарелки» Y 135
LANDINGS = [PY + 1 + 12 * i for i in (1, 2, 3, 4)]        # площадки отдыха: ходим 91, 103, 115, 127
RES = lambda x, z: 1812 <= z <= 1820                      # резерв трасс под проспектом
V2 = False                                                # вариант 2 (замечания владельца после постройки, --v2)
POD_R = 9.5                                               # v2: «тарелка» расширена до r 9.5 (было ≈6)
FIX = 'hill-1-fix-1.json'
LAWN = rect(-624, -593, 1773, 1827)                       # откосы и газоны (юг — до склона к промзоне)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=None)
    p.add_argument('--v2', action='store_true', help='вариант 2 и исправление к построенной hill-1-fix-1.json')
    a = p.parse_args()
    if a.preview is None:
        a.preview = os.path.join(REPO, 'docs', 'districts', 'hill-1-fix-1-preview.png' if a.v2 else 'hill-1-preview.png')
    return a


def col_put(S, x, z, h, full, slab, fill='stone'):
    """Колонна мощения до ходовой высоты h (шаг 0.5): ниже — fill до грунта, выше — расчистка."""
    W = S.W
    g = W.surf(x, z)
    if h == int(h):
        top = int(h) - 1; S.put(x, top, z, full); low = top
    else:
        top = int(h); S.put(x, top - 1, z, full); S.put(x, top, z, slab); low = top - 1
    for y in range(g + 1, low): S.put(x, y, z, fill)
    for y in range(top + 1, max(S.plant_top(x, z), g, top) + 1): S.put(x, y, z, 'air')
    return top


def stair_put(S, x, z, w, mat, meta, fill='stonebrick'):
    """Ступенька: блок-ступенька на Y w−1 (верх w, низ w−0.5), под ней — fill до грунта."""
    W = S.W
    g = W.surf(x, z)
    S.put(x, w - 1, z, f'{mat}:{meta}')
    for y in range(g + 1, w - 1): S.put(x, y, z, fill)
    for y in range(w, max(S.plant_top(x, z), g) + 1): S.put(x, y, z, 'air')


class WG:
    """Мир с уже поставленной схемой S (для здания на новой площади)."""
    def __init__(self, W, S): self.W, self.S = W, S

    def block(self, x, y, z):
        b = self.S.c.get((x, y, z))
        return b if b is not None else self.W.block(x, y, z)

    def surf(self, x, z, ymax=120, ymin=20):
        for y in range(ymax, ymin, -1):
            if World.solid(self.block(x, y, z)): return y

    def cave_top(self, x, z): return self.W.cave_top(x, z)


# ---------------- земля ----------------
def ground(W):
    Z = P.zones()
    disc, plaza, west, st = Z['disc'], Z['plaza'], Z['west'], Z['stairs']
    G = Sch(W)
    prof = P.avenue_profile()
    H, kind = {}, {}                                    # ходовые высоты и род клетки
    # ---- проспект: проезжая часть Z 1815…1817, лотки 1814/1818, тротуары 1813, 1819…1820 (+0.5)
    for x in range(-624, -592):
        for z in range(1813, 1821):
            if z in (1815, 1816, 1817): h, full, slab = prof[x], 'stonebrick', 'stone_slab:5'
            elif z in (1814, 1818): h, full, slab = prof[x], 'double_stone_slab', 'stone_slab'
            else: h, full, slab = prof[x] + 0.5, 'double_stone_slab', 'stone_slab'
            col_put(G, x, z, h, full, slab); H[(x, z)] = h; kind[(x, z)] = 'av'
    # ---- площадь, основание башни, смотровая: 79.0; узор — кварцевые кольца по гладкому песчанику
    lit_floor = []
    for c in sorted(plaza | disc | west):
        x, z = c
        r = math.hypot(x - CX, z - CZ)
        mat = 'quartz_block' if (c in plaza and int(r) in (13,)) or (c in disc and 9.0 <= r < 10.0) else 'sandstone:2'
        if c in disc and 9.0 <= r < 11.6 and (x * 3 + z * 5) % 6 == 0 and c not in west: mat = 'sea_lantern'; lit_floor.append(c)
        if c in west and x == -620: mat = 'quartz_block'
        col_put(G, x, z, float(WALK), mat, None, fill='stonebrick')
        H[c] = float(WALK); kind[c] = 'disc' if c in disc else 'west' if c in west else 'plaza'
    # ---- Северная лестница: площадка X −624 (65.0), марш X −623…−617 (66…72), площадка −616…−615 (72),
    #      марш −614…−608 (73…79); Z 1775…1776; парапет Z 1774 со стороны долины (каменный кирпич)
    for z in range(1773, 1777):
        col_put(G, -624, z, 65.0, 'sandstone:2', None, fill='stonebrick'); H[(-624, z)] = 65.0; kind[(-624, z)] = 'st'
    wN = {}
    for x in range(-623, -607):
        w = 66 + (x + 623) if x <= -617 else 72 if x <= -615 else 73 + (x + 614)
        wN[x] = w
        for z in (1775, 1776):
            if x in (-616, -615): col_put(G, x, z, float(w), 'sandstone:2', None, fill='stonebrick')
            else: stair_put(G, x, z, w, 'sandstone_stairs', 0)
            H[(x, z)] = float(w); kind[(x, z)] = 'st'
        g = W.surf(x, 1774)                             # парапет: кирпич до уровня ступеней, сверху — песчаник + плита
        for y in range(g + 1, w): G.put(x, y, 1774, 'stonebrick')
        G.put(x, w, 1774, 'sea_lantern' if x in (-620, -612) else 'sandstone:2'); G.put(x, w + 1, 1774, 'stone_slab:1')
        for y in range(w + 2, max(G.plant_top(x, 1774), g) + 1): G.put(x, y, 1774, 'air')
    # ---- Парадная лестница (кварц): от тротуара 66.0 центральный марш X −608…−604, Z 1812…1806 (67…73),
    #      площадка Z 1804…1805 (73), боковые марши на запад X −609…−614 и восток −603…−598 (74…79) —
    #      выход прямо на площадь (Z 1803); по краям маршей — балюстрада (песчаник + плита) на каменном кирпиче
    for x in range(-608, -603):
        for z in range(1806, 1813):
            w = 66 + (1813 - z); stair_put(G, x, z, w, 'quartz_stairs', 3); H[(x, z)] = float(w); kind[(x, z)] = 'st'
        for z in (1804, 1805):
            col_put(G, x, z, 73.0, 'quartz_block', None, fill='stonebrick'); H[(x, z)] = 73.0; kind[(x, z)] = 'st'
    for i in range(6):
        for z in (1804, 1805):
            for x, meta in ((-609 - i, 1), (-603 + i, 0)):
                w = 74 + i; stair_put(G, x, z, w, 'quartz_stairs', meta); H[(x, z)] = float(w); kind[(x, z)] = 'st'
    rail = {}
    for z in range(1806, 1813):
        for x in (-609, -603): rail[(x, z)] = 66 + (1813 - z)
    for i in range(6):
        for x in (-609 - i, -603 + i): rail[(x, 1806)] = max(rail.get((x, 1806), 0), 74 + i)
    for x in (-615, -597):
        for z in (1804, 1805, 1806): rail[(x, z)] = WALK
    for (x, z), w in sorted(rail.items()):
        g = W.surf(x, z)
        for y in range(g + 1, w): G.put(x, y, z, 'stonebrick')
        G.put(x, w, z, 'sandstone:2'); G.put(x, w + 1, z, 'stone_slab:1')
        for y in range(w + 2, max(G.plant_top(x, z), g) + 1): G.put(x, y, z, 'air')
    net = set(H)
    # ---- откосы и газоны: не выше мощения + d и (у лестниц, проспекта) не ниже мощения − d (1:1);
    #      у площади и смотровой откоса вниз нет — край держит подпорная стенка с парапетом
    ptop = {c: math.ceil(h) - 1 for c, h in H.items()}
    embank = {c for c in net if kind[c] in ('st', 'av')}
    tvfoot = {(x, z) for x in range(OX, OX + 23) for z in range(OZ, OZ + 23)} & disc
    lawn = {}
    for c in sorted(LAWN - net - tvfoot - set(rail) - {(x, 1774) for x in range(-623, -607)}):
        x, z = c
        if any((x, y, z) in W.pre and W.pre[(x, y, z)] not in ('grass', 'air', 'stone', 'leaves', 'leaves:4', 'leaves:6', 'log', 'log:2')
               for y in range(55, 100)): continue
        g = W.surf(x, z)
        lo, hi = -1e9, 1e9
        for a in range(-10, 11):
            for b in range(-10, 11):
                n = (x + a, z + b); d = max(abs(a), abs(b))
                if n in ptop:
                    hi = min(hi, ptop[n] + d)
                    if n in embank: lo = max(lo, ptop[n] - d)
        lvl = int(min(max(g, lo), hi)) if lo <= hi else int(hi)
        if lvl == g: continue
        for y in range(g + 1, lvl): G.put(x, y, z, 'stone')
        G.put(x, lvl, z, 'grass')
        for y in range(lvl + 1, max(G.plant_top(x, z), g) + 1): G.put(x, y, z, 'air')
        lawn[c] = lvl

    def top_of(c):
        if c in H: return H[c]
        if c in lawn: return lawn[c] + 1
        return W.surf(*c) + 1
    # ---- парапеты по краю площади/смотровой/верхних площадок: сосед ниже на 2 и больше
    parapet = []
    for c in sorted(net):
        if kind[c] not in ('plaza', 'west', 'disc'): continue
        if any(top_of((c[0] + a, c[1] + b)) <= H[c] - 2 for a, b in N4):
            if c in tvfoot: continue
            if V2: G.put(c[0], PY + 1, c[1], 'glass_pane'); G.put(c[0], PY + 2, c[1], 'glass_pane')    # v2: стекло «в пол», 2 бл.
            else: G.put(c[0], PY + 1, c[1], 'sandstone:2'); G.put(c[0], PY + 2, c[1], 'stone_slab:1')
            parapet.append(c)
    # ---- скамейки: смотровая — 3 лицом к парку (на запад), площадь — у южного парапета лицом к башне
    #      и у северного края лицом к башне; урны между ними
    benches, urns = [], []
    busy = set(parapet)
    front = {(CX, CZ + 9), (CX, CZ + 10), (CX, CZ - 9), (CX, CZ - 10)}          # перед дверями вестибюля
    legs = tower_legs()

    def free_line(cells):
        return all(c in net and c not in busy and c not in legs and c not in front and H[c] == WALK
                   and kind[c] in ('plaza', 'west') for c in cells)
    for z0 in (1780, 1786, 1792):
        cs = [(-622, z0 + i) for i in range(4)]
        fr = [(-623, z0 + i) for i in range(1, 3)]
        if free_line(cs) and free_line(fr):
            bench(G, -622, WALK, z0, 'w'); benches.append((-622, z0, 'w')); busy |= set(cs) | set(fr)
    for (x0, z0, face) in ((-615, 1802, 'n'), (-600, 1802, 'n'), (-613, 1777, 's'), (-602, 1777, 's')):
        cs = [(x0 + i, z0) for i in range(4)]
        dz = 1 if face == 's' else -1
        fr = [(x0 + i, z0 + dz) for i in range(1, 3)]
        if free_line(cs) and free_line(fr):
            if V2 and z0 == 1802: busy |= set(cs) | set(fr); continue      # v2: у выходов Парадной — убраны, см. ниже
            bench(G, x0, WALK, z0, face); benches.append((x0, z0, face)); busy |= set(cs) | set(fr)
    for u in ((-622, 1784), (-622, 1790), (-611, 1802), (-603, 1802)):
        if free_line([u]):
            busy.add(u)
            if V2 and u[1] == 1802: continue
            G.put(u[0], WALK, u[1], 'cauldron'); urns.append(u)
    # ---- фонари: проспект (ритм парка −656, −648 … → −624, −616 …) на лотках; площадь, смотровая,
    #      лестницы — на мощении/газоне, чтобы вся сеть была в пределах 5 блоков от фонаря
    lamps = []

    def lamp_on(x, z, y):
        for i, b in enumerate(LAMP): G.put(x, y + i, z, b)
        lamps.append((x, z))
    for x in range(-624, -592, 8):
        for z in (1814, 1818):
            h = H[(x, z)]
            if h != int(h): G.put(x, int(h), z, 'double_stone_slab')
            lamp_on(x, z, math.ceil(h))
    exits = {c for c in net if kind[c] == 'st' and H[c] == WALK and any(
        kind.get((c[0] + a, c[1] + b)) in ('plaza', 'west') for a, b in N4)}
    land = {(c[0] + a, c[1] + b) for c in exits for a, b in N4 if kind.get((c[0] + a, c[1] + b)) in ('plaza', 'west')}
    near_exit = lambda c: V2 and any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) <= 2 for l in land)   # v2: у выходов лестниц — свободно
    lit = lambda c: any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) <= 5 for l in lamps)
    cand = sorted((c for c in plaza | west if c not in busy and c not in front and c not in legs
                   and not any((c[0] + a, c[1] + b) in legs or (c[0] + a, c[1] + b) in st['st_n'] | st['st_s'] for a, b in N4)
                   and any((c[0] + a, c[1] + b) in busy for a, b in N4)), key=lambda c: h32(*c, 3))
    need = {c for c in net if kind[c] in ('plaza', 'west', 'st')}
    for c in cand:
        if all(lit(p) for p in need): break
        if near_exit(c): continue
        if lit(c) and all(lit(p) for p in need if max(abs(p[0] - c[0]), abs(p[1] - c[1])) <= 5): continue
        if any(max(abs(c[0] - l[0]), abs(c[1] - l[1])) < 6 for l in lamps): continue
        lamp_on(c[0], c[1], WALK); busy.add(c)
    for c in ((-611, 1808), (-601, 1808), (-620, 1777)):                    # у Парадной и Северной — на газоне
        y = lawn.get(c, W.surf(*c))
        G.put(c[0], y, c[1], 'quartz_block:1')
        for i, b in enumerate(LAMP[1:]): G.put(c[0], y + 1 + i, c[1], b)
        for yy in range(y + len(LAMP), G.plant_top(*c) + 1): G.put(c[0], yy, c[1], 'air')
        lamps.append(c)
    # ---- v2: южные скамейки — между выходами Парадной и проходом в башню (не ближе 2 к выходам лестниц)
    if V2:
        lampset0 = set(lamps)
        for (x0, z0) in ((-611, 1802), (-604, 1802)):
            cs = [(x0 + i, z0) for i in range(4)]
            fr = [(x0 + i, z0 - 1) for i in range(1, 3)]
            if all(c in net and c not in lampset0 and c not in legs and H[c] == WALK for c in cs + fr):
                bench(G, x0, WALK, z0, 'n'); benches.append((x0, z0, 'n'))
    # ---- деревья на газонах (берёза, дуб): не ближе 2 к мощению, фонарям, парапетам, башне
    trees = []
    lampset = set(lamps)
    for c in sorted(LAWN - net - tvfoot, key=lambda c: h32(*c, 21)):
        x, z = c
        if not (1777 <= z <= 1811) or any((x, y, z) in W.pre for y in range(55, 100)): continue
        if any((x + a, z + b) in net or (x + a, z + b) in lampset or (x + a, z + b) in tvfoot for a in range(-2, 3) for b in range(-2, 3)): continue
        if any(abs(x - t[0]) + abs(z - t[1]) < 5 for t in trees): continue
        y = lawn.get(c, W.surf(x, z))
        if W.block(x, y, z) != 'ground' and c not in lawn: continue
        tree(G, x, y + 1, z, 'birch' if h32(x, z, 9) < 0.6 else 'oak', 4 + int(h32(x, z, 2) * 2)); trees.append(c)
        G.put(x, y, z, 'grass')
    # ---- клумбы у Парадной лестницы: цветы на газоне по сторонам центрального марша
    flowers = 0
    for z in range(1806, 1813):
        for x in (-611, -610, -602, -601):
            c = (x, z)
            if c in lampset or c in trees: continue
            y = lawn.get(c)
            if y is None:
                y = W.surf(x, z)
                if W.block(x, y, z) != 'ground': continue
                G.put(x, y, z, 'grass')
            G.put(x, y + 1, z, ('red_flower:5', 'red_flower:2', 'red_flower:0', 'yellow_flower')[int(h32(x, z, 4) * 4)]); flowers += 1
    # карманы пустот под выемками (у проспекта на востоке каньон близко): заделать камнем, кровля ≥ 3
    cv = W._cv
    digs = {}
    for (x, y, z), b in G.c.items():
        if b == 'air' and y <= W.surf(x, z): digs[(x, z)] = min(digs.get((x, z), 999), y)
    for (x, z), b in lawn.items(): digs[(x, z)] = min(digs.get((x, z), 999), b + 1)
    plugged = 0
    for (x, z), y in digs.items():
        ct = W.cave_top(x, z)
        if ct is None or ct < y - 4: continue
        i = (z - cv['z0']) * cv['w'] + x - cv['x0']
        for yy in range(cv['minAir'][i], y):
            k = (x, yy, z)
            if k not in G.c: G.put(x, yy, z, 'stone'); plugged += 1
    return dict(exits=exits, rail=rail, plugged=plugged, G=G, H=H, kind=kind, net=net, lawn=lawn, parapet=parapet, lamps=lamps, benches=benches, urns=urns,
                trees=trees, flowers=flowers, lit_floor=lit_floor, Z=Z, busy=busy, tvfoot=tvfoot)


def tower_rel():
    return {(b['x'], b['y'], b['z']): b['block'] for b in json.load(open(os.path.join(REPO, 'schemas', 'ostankino.json')))}


def tower_legs():
    """Клетки (x, z) опор башни на уровне ходьбы (y 1…2 схемы)."""
    return {(OX + x, OZ + z) for (x, y, z) in tower_rel() if y in (1, 2)}


# ---------------- башня и её внутреннее ----------------
def tower(W, G):
    WGd = WG(W, G)
    T = Sch(WGd)
    rel = tower_rel()
    for (x, y, z), b in rel.items(): T.put(OX + x, PY + y, OZ + z, b)
    # вестибюль в основании: остеклённый круг r ≤ 8.3, пол 78, кровля 83; двери на север и юг
    occ = lambda x, y, z: math.hypot(x - CX, z - CZ) <= 8.3
    glass = lambda x, y, z: 'stained_glass_pane:3' if y == PY + 4 or (x + z) % 5 == 0 else 'stained_glass_pane:0'
    L = Tower(WGd, 'Вестибюль', occ, (CX - 9, CX + 9, CZ - 9, CZ + 9), PY, PY + 5, glass_fn=glass)
    L.shell()
    L.door(CX, CZ + 8, 3); L.door(CX, CZ - 8, 1)
    L.room('Электрощитовая', (CX + 4, CX + 6, CZ - 1, CZ + 1), (CX + 3, CZ, 0), shaft=(CX + 6, CZ + 1))
    if V2:                                                  # рама двери из полных блоков: стекло-панель у двери даёт щели
        for (x, y, z, m) in L.doors:
            side = [(x - 1, z), (x + 1, z)] if m in (1, 3) else [(x, z - 1), (x, z + 1)]
            for (sx, sz) in side:
                for yy in (y, y + 1, y + 2): L.put(sx, yy, sz, 'concrete:0')
            L.put(x, y + 2, z, 'concrete:0')
    for k, b in L.cells.items(): T.put(*k, b)
    # центральная колонна и стремянка до пола «тарелки»; лаз в кровле вестибюля и в полу «тарелки»
    for y in range(PY + 1, POD + 1):                         # v1: морские фонари в колонне — стремянка на них не держится
        T.put(CX, y, CZ, 'sea_lantern' if (y - PY) % 6 == 0 and not V2 else 'concrete:0')
    for y in range(PY + 1, POD + 1): T.put(LADDER[0], y, LADDER[1], 'ladder:3')
    # площадки отдыха: верхние полублоки кварца вокруг стремянки (не в стенах ствола)
    land_cells = [(CX - 1, CZ + 1), (CX + 1, CZ + 1), (CX - 1, CZ + 2), (CX, CZ + 2), (CX + 1, CZ + 2)]
    placed = []
    for w in LANDINGS:
        for (x, z) in land_cells:
            k = (x - OX, w - 1 - PY, z - OZ)
            if k in rel or any((x - OX, w - PY + d, z - OZ) in rel for d in (0, 1)): continue
            T.put(x, w - 1, z, 'stone_slab:15'); placed.append((x, w - 1, z))
    if V2: return tower_v2(T, L, rel, land_cells, placed)
    # пол «тарелки»: над стволом — стекло (смотреть вниз), кроме лаза стремянки
    glass_floor = 0
    for x in range(CX - 6, CX + 7):
        for z in range(CZ - 6, CZ + 7):
            k = (x - OX, 57, z - OZ)
            if k in rel or (x, z) in (LADDER, (CX, CZ)): continue
            if math.hypot(x - CX, z - CZ) <= 4.5: T.put(x, POD, z, 'glass'); glass_floor += 1
    # смотровая: скамейки лицом к окнам (свободная клетка перед сиденьем), кафе «Седьмое небо»
    inside = lambda x, z: (x - OX, 58, z - OZ) not in rel and (x - OX, 57, z - OZ) in rel | {(x - OX, 57, z - OZ)} \
        and math.hypot(x - CX, z - CZ) <= 6.5
    floor_ok = lambda x, z: T.c.get((x, POD, z)) not in (None, 'air') or (x - OX, 57, z - OZ) in rel
    deck = {(x, z) for x in range(CX - 7, CX + 8) for z in range(CZ - 7, CZ + 8)
            if (x - OX, 58, z - OZ) not in rel and floor_ok(x, z) and math.hypot(x - CX, z - CZ) <= 6.5}
    pod_b = []
    for (x0, z0, face) in ((CX - 1, CZ - 3, 'n'), (CX + 3, CZ - 1, 'e'), (CX - 3, CZ - 2, 'w')):
        cells = [(x0 + i, z0) for i in range(4)] if face == 'n' else [(x0, z0 + i) for i in range(4)]
        d = {'n': (0, -1), 'e': (1, 0), 'w': (-1, 0)}[face]
        fr = [(c[0] + d[0], c[1] + d[1]) for c in cells[1:3]]
        if all(c in deck and c != LADDER and c != (CX, CZ) for c in cells + fr):
            bench(T, x0, POD + 1, z0, face); pod_b.append((x0, z0, face))
    cafe = []
    # стойка (перевёрнутые ступеньки + верхние плиты) и два столика-забора с плитами, у южного окна
    for (x, z, b) in ((CX - 1, CZ + 4, 'quartz_stairs:5'), (CX, CZ + 4, 'stone_slab:15'), (CX + 1, CZ + 4, 'quartz_stairs:4')):
        if (x, z) in deck: T.put(x, POD + 1, z, b); cafe.append((x, z))
    for (x, z) in ((CX - 3, CZ + 2), (CX + 3, CZ + 2)):
        if (x, z) in deck: T.put(x, POD + 1, z, 'fence'); T.put(x, POD + 2, z, 'wooden_pressure_plate'); cafe.append((x, z))
    return dict(T=T, L=L, placed=placed, glass_floor=glass_floor, pod_b=pod_b, cafe=cafe, deck=deck)


def tower_v2(T, L, rel, land_cells, placed):
    """v2: свет внутри ствола, «тарелка» r 9.5 — пол, стены и потолок стеклянные (стены «в пол»),
    по краю — белый и красный пояс; скамейки у окон, кафе; свет — морские фонари в полу и потолке."""
    # свет в стволе: морские фонари у внутренней стороны оболочки через 5 блоков по высоте, через 3 по кругу
    lights = []
    avoid = {(CX, CZ), LADDER} | set(land_cells)
    for yr in range(8, 90, 5):
        if 55 <= yr <= 65: continue
        ring = []
        for (x, y, z) in rel:
            if y != yr: continue
            dx, dz = x - 11, z - 11
            if dx == 0 and dz == 0: continue
            nx, nz = (x - (dx > 0) + (dx < 0), z) if abs(dx) >= abs(dz) else (x, z - (dz > 0) + (dz < 0))
            if (nx, yr, nz) in rel or math.hypot(nx - 11, nz - 11) >= math.hypot(dx, dz): continue
            a = (OX + nx, PY + yr, OZ + nz)
            if (a[0], a[2]) in avoid or T.c.get(a, 'air') != 'air': continue
            ring.append((math.atan2(dz, dx), a))
        ring = sorted(set(ring))
        for i, (_, a) in enumerate(ring):
            if i % 3 == 0: T.put(*a, 'sea_lantern'); lights.append(a)
    # «тарелка»: снять старую (y 57…64), поставить новую
    for (x, y, z), b in rel.items():
        if 57 <= y <= 64: T.put(OX + x, PY + y, OZ + z, 'air')
    glass_floor, deck = 0, set()
    lan = []
    for x in range(CX - 10, CX + 11):
        for z in range(CZ - 10, CZ + 11):
            r = math.hypot(x - CX, z - CZ)
            if r > POD_R: continue
            rim = r > POD_R - 1
            if (x, z) == LADDER: pass
            elif (x, z) == (CX, CZ): pass
            else:
                fl = 'concrete:0' if rim else 'glass'
                if not rim and abs(r - 5) < 0.5 and (x + 2 * z) % 4 == 0: fl = 'sea_lantern'; lan.append((x, POD, z))
                T.put(x, POD, z, fl); glass_floor += fl == 'glass'
            for y in range(POD + 1, POD + 7): T.put(x, y, z, 'glass' if rim else 'air')
            ce = 'concrete:14' if rim else 'glass'
            if not rim and abs(r - 6.5) < 0.5 and (2 * x + z) % 4 == 0: ce = 'sea_lantern'; lan.append((x, POD + 7, z))
            if (x - OX, 65, z - OZ) in rel and not rim: ce = 'concrete:14'            # под стенками верхнего ствола
            T.put(x, POD + 7, z, ce)
            if not rim and (x, z) != LADDER: deck.add((x, z))
    pod_b = []
    for (x0, z0, face) in ((CX - 1, CZ - 7, 'n'), (CX - 1, CZ + 7, 's'), (CX + 7, CZ - 1, 'e'), (CX - 7, CZ - 1, 'w')):
        cells = [(x0 + i, z0) for i in range(4)] if face in ('n', 's') else [(x0, z0 + i) for i in range(4)]
        d = {'n': (0, -1), 's': (0, 1), 'e': (1, 0), 'w': (-1, 0)}[face]
        fr = [(c[0] + d[0], c[1] + d[1]) for c in cells[1:3]]
        if all(c in deck for c in cells + fr):
            bench(T, x0, POD + 1, z0, face); pod_b.append((x0, z0, face))
    cafe = []
    for (x, z, b) in ((CX - 1, CZ + 4, 'quartz_stairs:5'), (CX, CZ + 4, 'stone_slab:15'), (CX + 1, CZ + 4, 'quartz_stairs:4')):
        T.put(x, POD + 1, z, b); cafe.append((x, z))
    for (x, z) in ((CX - 4, CZ + 3), (CX + 4, CZ + 3), (CX - 4, CZ - 3), (CX + 4, CZ - 3)):
        T.put(x, POD + 1, z, 'fence'); T.put(x, POD + 2, z, 'wooden_pressure_plate'); cafe.append((x, z))
    return dict(T=T, L=L, placed=placed, glass_floor=glass_floor, pod_b=pod_b, cafe=cafe, deck=deck, lights=lights, pod_lan=lan)


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    global V2
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0])) if NAMES[0] in names else World()
    if args.v2:                                              # построенное (v1) — для исправления
        R1 = ground(W); Q1 = tower(W, R1['G'])
        OLD = dict(R1['G'].c); OLD.update(Q1['T'].c)
        V2 = True
    R = ground(W)
    G, H, net = R['G'], R['H'], R['net']
    Q = tower(W, G)
    T, L = Q['T'], Q['L']
    if V2:
        print(f'v2: свет в стволе — {len(Q["lights"])} морских фонарей, в «тарелке» — {len(Q["pod_lan"])}; «тарелка» r {POD_R}, '
              f'палуба {len(Q["deck"])} кл.; парапеты площади и смотровой — стекло-панели 2 бл.; рамы дверей; колонна без фонарей')
    print(f'сеть: клеток {len(net)} | покрытие Y {min(H.values())}…{max(H.values())} | парапетов {len(R["parapet"])} | '
          f'газонов/откосов {len(R["lawn"])} | фонарей {len(R["lamps"])} | деревьев {len(R["trees"])} | скамеек {len(R["benches"])} | '
          f'урн {len(R["urns"])} | цветов {R["flowers"]} | подсветка в мощении под башней {len(R["lit_floor"])}')
    print(f'башня: блоков схемы {len(tower_rel())}, origin ({OX}, {PY}, {OZ}), верх Y {PY + 109} | вестибюль — дверей {len(L.doors)}, '
          f'щитовая {L.rooms} | стремянка Y {PY + 1}…{POD}, площадок {len(LANDINGS)} ({len(Q["placed"])} полублоков) | '
          f'стеклянный пол «тарелки» {Q["glass_floor"]} | скамеек в «тарелке» {len(Q["pod_b"])} | кафе {len(Q["cafe"])} предм.')
    outs = {}
    import tempfile
    tmp = tempfile.mkdtemp() if V2 else None
    for nm, S in zip(NAMES, (G, T)):
        o, rel, order, dims = save_schema(S.c, os.path.join(tmp if V2 else args.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(S.c)}')

    print('== ПРОВЕРКИ ==')
    for nm, S in zip(NAMES, (G, T)):
        o, rel, order = outs[nm]
        prev = G.c if nm == NAMES[1] else {}

        def terr(x, y, z, o=o, prev=prev):
            k = (x + o[0], y + o[1], z + o[2])
            b = prev.get(k) or W.block(*k)
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        if not V2:                                           # v1 построена; ошибка найдена на сервере и исправлена в fix-1
            known = [e for e in se if 'ladder' in e and 'sea_lantern' in e]
            se = [e for e in se if e not in known]
            if known: print(f'{nm}: известная ошибка v1 — стремянка на морских фонарях колонны ({len(known)} шт.), исправлена в {FIX}')
        print(f'{nm}{" (v2)" if V2 else ""}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:6]: print('   ', m)
        be = dl.check_bench_front(rel, terr)
        print(f'{nm}: скамейки (место для ног): ошибок {len(be)}', be[:3])
    ALL = dict(G.c); ALL.update(T.c)
    if V2:                                                   # исправление к построенной (hill-1-ground + hill-1-tower)
        def was(k):
            b = OLD.get(k) or W.block(*k)
            return 'air' if b == 'plant' else b
        fix = {k: b for k, b in ALL.items() if was(k) != b}
        for k, b in OLD.items():
            if k not in ALL and b != 'air' and W.block(*k) in ('air', 'plant'): fix[k] = 'air'
        lost = {(LADDER[0], y, LADDER[1]): 'ladder:3' for y in range(PY + 1, POD + 1)}   # стремянки отлетели — поставить заново
        fix.update(lost)
        fx = [k[0] for k in fix]; fy = [k[1] for k in fix]; fz = [k[2] for k in fix]
        fo = (min(fx), min(fy), min(fz))
        frel = {(x - fo[0], y - fo[1], z - fo[2]): b for (x, y, z), b in fix.items()}
        forder = dl.compute_order(frel)
        dl.save(frel, os.path.join(args.outdir, FIX), forder)

        def fterr(x, y, z):
            k = (x + fo[0], y + fo[1], z + fo[2])
            b = was(k)
            if k[0] == LADDER[0] and k[2] == LADDER[1] and b.startswith('ladder'): b = 'air'       # на сервере их нет
            return 'stone' if b == 'ground' else b
        fe = dl.check_water(frel, fterr); fs, fw = dl.check_supports(frel, forder, fterr)
        from collections import Counter
        print(f'{FIX}: origin {fo[0]} {fo[1]} {fo[2]} | записей {len(frel)} | состав {dict(Counter(b.split(":")[0] for b in fix.values()).most_common(8))}')
        print(f'{FIX}: опоры/вода/порядок постройки поверх построенного: ошибок {len(fe) + len(fs)} | предупреждений {len(fw)}')
        for m in (fe + fs + fw)[:6]: print('   ', m)
        ok = all((fix.get(k) or was(k)) == b for k, b in ALL.items())
        print('построенное + исправление = вариант 2:', ok)

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z)) or W.block(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    leak = [(x + a, y, z + c) for (x, y, z), b in ALL.items() if b == 'air' for a, c in N4
            if (x + a, y, z + c) not in ALL and W.block(x + a, y, z + c) == 'water']
    print('вода рельефа, открытая в воздух схемы:', len(leak), leak[:4])
    kind = R['kind']
    jump = [(c, n) for c in net for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1))
            if n in net and kind[c] != 'st' and kind[n] != 'st' and abs(H[c] - H[n]) > 0.5]
    print('перепад покрытия между соседями (кроме ступеней) > 0.5 —', len(jump), jump[:3])
    edge = []
    for z in range(1813, 1821):
        t = None
        for y in range(68, 60, -1):
            b = W.block(-625, y, z)
            if b not in ('air', 'plant'):
                n_, m_ = (b.split(':') + ['0'])[:2]
                t = y + (0.5 if n_ in ('stone_slab', 'stone_slab2') and int(m_) < 8 else 1.0); break
        if t is None or abs(t - H[(-624, z)]) > 0.5: edge.append((z, t, H[(-624, z)]))
    t = None
    for y in range(68, 60, -1):
        b = W.block(-625, y, 1773)
        if b not in ('air', 'plant'):
            n_, m_ = (b.split(':') + ['0'])[:2]
            t = y + (0.5 if n_ in ('stone_slab', 'stone_slab2') and int(m_) < 8 else 1.0); break
    if t is None or abs(t - H[(-624, 1773)]) > 0.5: edge.append(('Горная дорога', t, H[(-624, 1773)]))
    print('со стыком (парк X −625: проспект, Горная дорога) > 0.5 —', len(edge), edge[:3])

    def drops(fin, par):
        out = []
        for c in net:
            if kind[c] in ('plaza', 'west', 'disc', 'st') and c not in par:
                for a, b in N4:
                    n = (c[0] + a, c[1] + b)
                    if n in net: continue
                    y = int(H[c]) + 1
                    while y > 40 and fin(n[0], y, n[1]) in ('air',) or fin(n[0], y, n[1]).split(':')[0] in ('red_flower', 'yellow_flower', 'tallgrass', 'double_plant'):
                        y -= 1
                    if y + 1 <= H[c] - 2: out.append((c, n, y + 1))
        return out
    dr_ = drops(final, set(R['parapet']))
    print('перепад у края площади, смотровой и лестниц без парапета (обрыв ≥ 2) —', len(dr_), dr_[:3])
    items = {c: h for c, h in H.items()}
    trel = {(OX + x, PY + y, OZ + z) for (x, y, z) in tower_rel()}
    fl = floating_over_paving(final, {k: b for k, b in ALL.items() if k not in trel}, items)   # опоры башни — арки, не предметы
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:4])
    def near_exits(cells):
        land = {(c[0] + a, c[1] + b) for c in R['exits'] for a, b in N4 if R['kind'].get((c[0] + a, c[1] + b)) in ('plaza', 'west')}
        out = []
        for (x, y, z), b in cells.items():
            if (x, z) in net and y == math.ceil(H[(x, z)]) and b not in ('air',) and b.split(':')[0] not in ('stone_pressure_plate', 'glass_pane') \
                    and any(max(abs(x - l[0]), abs(z - l[1])) <= 2 for l in land):
                out.append((x, z, b))
        return out
    trel = {(OX + x, PY + y, OZ + z) for (x, y, z) in tower_rel()}
    ne = near_exits({k: b for k, b in ALL.items() if k not in trel})
    if V2: print('предметы у выходов с лестниц на площадь (≤ 2 от выхода):', len(ne), ne[:4])
    else: print(f'известная ошибка v1 — скамейки у выходов с лестниц ({len(ne)} бл.), исправлено в {FIX}')

    def door_gaps(fin):
        out = []
        for (x, y, z, m) in L.doors:
            side = [(x - 1, z), (x + 1, z)] if m in (1, 3) else [(x, z - 1), (x, z + 1)]
            for (sx, sz) in side + [(x, z)]:
                for yy in ((y, y + 1, y + 2) if (sx, sz) != (x, z) else (y + 2,)):
                    if fin(sx, yy, sz).split(':')[0] in ('glass_pane', 'stained_glass_pane'): out.append((sx, yy, sz))
        return out
    dg = door_gaps(final)
    if V2: print('двери рядом со стеклом-панелью (щели): ошибок', len(dg), dg[:3])
    low = [k for k, b in ALL.items() if b != 'air' and k[1] < 60 and RES(k[0], k[2])]
    print('в резерве трасс ниже Y 60 —', len(low), low[:4])
    digs = {}
    for (x, y, z), b in ALL.items():
        if b == 'air' and y <= W.surf(x, z): digs[(x, z)] = min(digs.get((x, z), 999), y)
    for (x, z), b in R['lawn'].items(): digs[(x, z)] = min(digs.get((x, z), 999), b + 1)
    cv = W._cv
    roofs = []
    for (x, z), y in digs.items():
        ct = W.cave_top(x, z)
        if ct is None: continue
        i = (z - cv['z0']) * cv['w'] + x - cv['x0']
        air = [yy for yy in range(cv['minAir'][i], min(ct, y - 1) + 1) if final(x, yy, z) == 'air']
        if air: roofs.append((y - max(air) - 1, x, z))
    print(f'кровля каньона под выемками схемы (карманы заделаны: {R["plugged"]} бл.): мин.', min(roofs)[0] if roofs else '—', '(норма >= 3)')
    doors = list(L.doors)

    def door_front(fin, ds):
        """Перед дверью (снаружи, 2 клетки) — мощение вровень с порогом, не газон (навес башни не в счёт)."""
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
    print(f'подходы к наружным дверям: {len(doors)}, ошибок {len(di)}', di[:2])
    legs = tower_legs()

    # проходимость — от проспекта, только по мощению, основанию башни, стволу; газоны не в счёт
    walkable = net | set(R['Z']['disc']) | {LADDER, (CX, CZ)} | {(x, z) for (x, y, z) in Q['placed']} | Q['deck'] | \
        {(-625, z) for z in range(1769, 1774)} | {(-625, z) for z in range(1813, 1821)}
    box = ((-626, -592), (1768, 1822), (58, 145))
    start = (-620, 64.5, 1816)

    def walk(fin):
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in walkable else ('stone' if y < 60 else 'air')
        return dl.walk_reachable(f2, start, *box)
    seen = walk(final)
    occ = {(x, z) for (x, y, z), b in ALL.items() if (x, z) in net and b not in ('air',) and math.ceil(H[(x, z)]) <= y <= math.ceil(H[(x, z)]) + 1
           and b.split(':')[0] not in ('stone_pressure_plate',)}
    miss = [c for c in net if c not in occ and c not in legs and not dl.reached(seen, c[0], H[c], c[1])]
    print(f'ПРОХОДИМОСТЬ без прыжков от проспекта (−620,1816): клеток мощения {len(net) - len(occ)}, недостижимо {len(miss)}', miss[:6])
    targets = {'проспект парка (−625,1816)': (-625, 64.5, 1816), 'Горная дорога, конец (−625,1771)': (-625, 64.5, 1771),
               'низ Северной лестницы (−624,1774)': (-624, 65.0, 1774), 'площадка Северной (−616,1775)': (-616, 72.0, 1775),
               'площадка Парадной (−606,1804)': (-606, 73.0, 1804), 'площадь у башни, север (−606,1777)': (-606, 79.0, 1777),
               'смотровая «Над парком» (−621,1788)': (-621, 79.0, 1788), 'между опорами (−596,1780)': (-596, 79.0, 1782),
               'вестибюль, центр (−608,1790)': (-608, 79.0, 1790)}
    targets.update(L.level_targets()); targets.update({f'{L.name}: {k}': v for k, v in L.targets.items()})
    for (x, y, z, m) in L.doors:
        a, b = DOOR_IN[m]; targets[f'{L.name}: перед дверью ({x},{z})'] = (x - a, y, z - b)
    for i, w in enumerate(LANDINGS, 1): targets[f'площадка стремянки {i} (Y {w})'] = (CX, float(w), CZ + 2)
    targets['смотровая в «тарелке», север (−606,1785)'] = (CX, float(POD + 1), CZ - 5)
    targets['смотровая в «тарелке», восток (−601,1790)'] = (CX + 5, float(POD + 1), CZ)
    targets['кафе «Седьмое небо» (−606,1793)'] = (CX, float(POD + 1), CZ + 3)
    bad_t = 0
    for k, (x, y, z) in targets.items():
        ok = dl.reached(seen, x, y, z); bad_t += 0 if ok else 1
        print(f'  маршрут → {k}: {ok}')
    # по отдельности: в вестибюль через каждую дверь (другая закрыта стеной)
    for (x, y, z, m) in L.doors:
        other = [d for d in L.doors if d[:3] != (x, y, z)][0]
        negc = dict(ALL); negc[other[:3]] = 'concrete:0'; negc[(other[0], other[1] + 1, other[2])] = 'concrete:0'
        s_ = walk(fin_of(negc))
        ok = dl.reached(s_, CX - 2, 79.0, CZ) and dl.reached(s_, CX, float(POD + 1), CZ - 5)
        print(f'  маршрут → вестибюль и «тарелка» только через дверь ({x},{z}): {ok}'); bad_t += 0 if ok else 1
    # по отдельности: площадь с проспекта только по Парадной и только по Северной (с Горной дороги)
    for nm_, cut in (('Парадная', rect(-624, -624, 1773, 1776)), ('Северная (от Горной дороги)', rect(-608, -604, 1809, 1809))):
        negc = dict(ALL)
        for (x, z) in cut:
            for y in range(int(H[(x, z)]), int(H[(x, z)]) + 3): negc[(x, y, z)] = 'stonebrick'
        s_ = walk(fin_of(negc))
        src = (-625, 64.5, 1771) if 'Северная' in nm_ else None
        s2 = dl.walk_reachable(lambda x, y, z: fin_of(negc)(x, y, z) if (x, z) in walkable else ('stone' if y < 60 else 'air'),
                               src, *box) if src else s_
        ok = dl.reached(s2, -606, 79.0, 1777)
        print(f'  маршрут → площадь только по лестнице «{nm_}»: {ok}'); bad_t += 0 if ok else 1
    print('ИТОГО недостижимых точек:', len(miss) + bad_t)
    # негатив 1: на центральном марше Парадной — полный блок вместо ступеньки (прыжок): площадь недостижима с проспекта
    negc = dict(ALL)
    for x in range(-608, -603): negc[(x, 69, 1809)] = 'quartz_block'
    s_ = walk(fin_of(negc))
    print('НЕГАТИВ: ступенька Парадной заменена полным блоком — площадь с проспекта недостижима (Северная не в счёт):',
          not dl.reached(s_, -606, 79.0, 1802))
    # негатив 2: стремянка без одного звена — «тарелка» недостижима
    negc = dict(ALL); negc[(LADDER[0], 110, LADDER[1])] = 'air'
    print('НЕГАТИВ: пропуск в стремянке — «тарелка» недостижима:', not dl.reached(walk(fin_of(negc)), CX, float(POD + 1), CZ - 5))
    # негатив 3: снят парапет — обрыв найден
    par = set(R['parapet'])
    negc = dict(ALL); c0 = sorted(par)[0]
    negc[(c0[0], PY + 1, c0[1])] = 'air'; negc[(c0[0], PY + 2, c0[1])] = 'air'
    print('НЕГАТИВ: снят парапет — обрыв найден:', len(drops(fin_of(negc), par - {c0})) > 0)
    # негатив 4: урна на блок выше мощения — висящие найдены
    negc = dict(ALL); u = R['urns'][0]; negc[(u[0], WALK, u[1])] = 'air'; negc[(u[0], WALK + 1, u[1])] = 'cauldron'
    print('НЕГАТИВ: урна на блок выше мощения — висящие найдены:', len(floating_over_paving(fin_of(negc), negc, {u: H[u]})) > 0)
    # негатив 5: газон перед южной дверью вестибюля — ошибка подхода найдена
    negc = dict(ALL); negc[(CX, PY, CZ + 9)] = 'grass'; negc[(CX, PY + 1, CZ + 9)] = 'air'
    for d in range(2, 8): negc[(CX, PY + d, CZ + 9)] = 'air'
    print('НЕГАТИВ: газон перед дверью вестибюля — ошибка подхода найдена:', len(door_front(fin_of(negc), doors)) > 0)
    # негатив 6: перед скамейкой смотровой — кашпо: ошибка места для ног найдена
    o, rel, order = outs[NAMES[0]]
    negr = dict(rel)
    bx_, bz_, face = R['benches'][0]
    negr[(bx_ - 1 - o[0], WALK - o[1], bz_ + 1 - o[2])] = 'leaves:4'
    terr0 = lambda x, y, z: (lambda b: 'stone' if b == 'ground' else ('air' if b == 'plant' else b))(W.block(x + o[0], y + o[1], z + o[2]))
    print('НЕГАТИВ: кашпо перед скамейкой: ошибок', len(dl.check_bench_front(negr, terr0)), '(ждём > 0)')
    if V2:
        negc = dict(ALL)
        for i in range(4): negc[(-615 + i, WALK, 1802)] = 'birch_stairs:2'
        print('НЕГАТИВ: скамейка v1 у выхода Парадной — найдена:', len(near_exits({k: b for k, b in negc.items() if k not in trel})) > len(ne))
        negc = dict(ALL); d = L.doors[0]; negc[(d[0] - 1, d[1], d[2])] = 'stained_glass_pane:0'
        print('НЕГАТИВ: панель у двери — щель найдена: ошибок', len(door_gaps(fin_of(negc))), '(ждём > 0)')
    if args.preview: preview(args.preview, final, R, Q)


def preview(path, final, R, Q):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CX_ = dict(CL); CX_.update({'sandstone:2': (225, 212, 160), 'stone_slab:1': (220, 208, 158), 'quartz_block': (240, 238, 232),
                                'stone_slab:7': (236, 234, 228), 'quartz_stairs': (235, 232, 225), 'sandstone_stairs': (215, 200, 150),
                                'grass': (95, 150, 60), 'leaves:4': (60, 120, 40), 'leaves:6': (110, 150, 60),
                                'concrete:0': (238, 238, 238), 'concrete:14': (180, 40, 40), 'concrete:7': (90, 90, 90),
                                'glass': (150, 205, 235), 'glowstone': (250, 220, 90), 'sea_lantern': (200, 230, 230),
                                'stained_glass_pane:3': (120, 180, 230), 'stained_glass_pane:0': (225, 235, 240),
                                'stonebrick': (130, 130, 130), 'double_stone_slab': (170, 170, 170), 'stone_slab:5': (125, 125, 125),
                                'red_flower': (220, 60, 90), 'yellow_flower': (240, 220, 60), 'ladder': (150, 110, 60)})
    cc = lambda b: CX_.get(b) or CX_.get(b.split(':')[0]) or col(b)
    X0, X1, Z0, Z1 = -628, -593, 1768, 1824
    S = 11
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    E = 3
    ew = (X1 - X0 + 1) * E
    eh = (192 - 58) * E
    img = Image.new('RGB', (mw + 60 + ew + 60 + 330, max(mh + 60, eh + 60)), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 95 if math.hypot(x - CX, z - CZ) > 12 else PY + 5
            while y > 40 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if b == 'stone' and (x, z) not in R['net']:
                k = (max(60, min(y, 85)) - 60) / 25; c = (int(200 - 70 * k), int(210 - 40 * k), int(140 - 60 * k))
            else: c = cc(b)
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
            if (x, z) in R['H'] and R['H'][(x, z)] != int(R['H'][(x, z)]):
                dr.line([20 + (x - X0) * S + 1, 30 + (z - Z0) * S + S - 2, 20 + (x - X0) * S + S - 2, 30 + (z - Z0) * S + 1], fill=(90, 90, 90))
    for x in range(-620, X1 + 1, 10): dr.text((20 + (x - X0) * S - 8, 16), str(x), fill='black', font=F(10))
    for z in range(1770, Z1 + 1, 10): dr.text((0, 30 + (z - Z0) * S - 5), str(z), fill='black', font=F(9))
    dr.text((20, 2), 'Холм E: вид сверху (башня — кровля вестибюля), / — полублок', fill='black', font=F(12))
    # вид с юга 1:1 (разрез по Z 1790 через ствол)
    bx = mw + 60
    dr.text((bx, 16), 'Разрез Z 1790', fill='black', font=F(11))
    base = 30 + eh
    for yy in range(60, 192, 10):
        dr.line([bx, base - (yy - 58) * E, bx + ew, base - (yy - 58) * E], fill=(230, 230, 230))
        dr.text((bx + ew + 3, base - (yy - 58) * E - 5), str(yy), fill='black', font=F(8))
    for x in range(X0, X1 + 1):
        for y in range(58, 192):
            b = final(x, y, 1790)
            if b == 'air': continue
            c = (150, 140, 110) if b == 'stone' else cc(b)
            dr.rectangle([bx + (x - X0) * E, base - (y - 58 + 1) * E, bx + (x - X0 + 1) * E - 1, base - (y - 58) * E - 1], fill=c)
    # разрез по X −606 (север → юг): Северная — площадь — ствол — Парадная — проспект; и «тарелка» сверху
    bx2 = bx + ew + 40
    S2 = 5
    dr.text((bx2, 16), 'Разрез X −606: Y 60…90, «тарелка» Y 133…143', fill='black', font=F(11))
    for u, z in enumerate(range(1770, 1823)):
        for y in range(60, 91):
            b = final(-606, y, z)
            if b == 'air': continue
            c = (150, 140, 110) if b == 'stone' else cc(b)
            dr.rectangle([bx2 + u * S2, 30 + (90 - y) * S2, bx2 + (u + 1) * S2 - 1, 30 + (91 - y) * S2 - 1], fill=c)
        for y in range(133, 144):
            b = final(-606, y, z)
            if b == 'air': continue
            dr.rectangle([bx2 + u * S2, 220 + (143 - y) * S2, bx2 + (u + 1) * S2 - 1, 220 + (144 - y) * S2 - 1], fill=cc(b))
        if u % 10 == 0: dr.text((bx2 + u * S2, 190), str(z), fill='black', font=F(8))
    # план «тарелки»
    by = 300
    dr.text((bx2, by), 'План «тарелки» (Y 136): скамейки, кафе, стекло пола, лаз', fill='black', font=F(11))
    for x in range(CX - 10, CX + 11):
        for z in range(CZ - 10, CZ + 11):
            b = final(x, POD + 1, z)
            if b == 'air': b = final(x, POD, z)
            dr.rectangle([bx2 + (x - CX + 10) * 11, by + 18 + (z - CZ + 10) * 11, bx2 + (x - CX + 11) * 11 - 1, by + 18 + (z - CZ + 11) * 11 - 1],
                         fill=cc(b))
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
