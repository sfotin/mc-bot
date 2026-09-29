"""Сити, этапы 1–3 (CITY.md §7.4, план v1 — tools/city/plan_city_v1.py, геометрия берётся оттуда).

Две схемы:
- city-1-streets.json (этапы 1–2): земляные работы под улицами (срез холма на западе проспекта,
  подсыпка ложбин), главный проспект с тротуарами, проспект Сити до улицы-набережной (проход
  в подпорной стенке Z 1849), Северная, Южная, Пограничная улицы; фонари DECOR §3.2а через
  8 блоков, берёзы на тротуарах проспекта между фонарями;
- city-1-parks.json (этап 3): Площадь Сити со стеклянным окном в каньон (кровля под окном
  снята, стенки шахты с морскими фонарями) и «Кристаллом», сквер с фонтаном 9×9 (DECOR §5.1,
  палитра med), аллея, пруд у «Гальки», аллея Каньон-парка и «Шар», смотровая «Провал»
  с ограждением, дорожки к пруду и «Провалу», деревья, скамейки, урны, кашпо, фонари.
Места вестибюлей метро «Каньон» замощены и свободны (строятся со схемой тоннеля).

Высоты покрытия (шаг 0.5): сглаженный рельеф, стык со Старым городом (X −724) и улицей-
набережной (Z 1850) вровень, поперечные сечения улиц — одной высотой, площади и сквер —
плоские, перепад соседей не больше полублока; обочины — откос не круче 1:1.

Запуск: gen_city_1.py [--outdir schemas] [--preview docs/districts/city-1-preview.png]
Мир — World() (район строится впервые; после постройки — built_before('city-1-streets.json')).
Проверки: опоры + вода + порядок (decor_lib, порядок бота), вода рельефа не открыта, перепад
покрытия, проходимость без прыжков (от улицы-набережной до каждой клетки улиц, площадей,
дорожек, стыков со Старым городом), скамейки, висящие над мощением, резерв трасс, кровля
каньона (кроме окна — задумано), негативные прогоны.
"""
import argparse
import math
import os
import sys
from collections import Counter, deque

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, BUILT, built_before  # noqa: E402
from oldtown_lib import street_top, floating_over_paving, col, CL  # noqa: E402
import plan_city_v1 as P  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402
import gen_fountain as GF  # noqa: E402

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
LAMP = ('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')
RES = lambda x, z: 1812 <= z <= 1820 or (-771 <= x <= -767 and z <= 1811)     # резерв трасс (§7.4)
MAT = {'road': ('stone:6', 'stone_slab'), 'edge': ('double_stone_slab', 'stone_slab'),
       'walk': ('quartz_block', 'stone_slab:7'), 'path': ('double_stone_slab:8', 'stone_slab'),
       'sq': ('quartz_block', 'stone_slab:7'), 'sq_line': ('stone:6', 'stone_slab'), 'rim': ('quartz_block:2', 'stone_slab:7')}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'city-1-preview.png'))
    return p.parse_args()


def rect(x0, x1, z0, z1): return {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}


def h32(x, z, k=0):
    v = (x * 73856093 ^ z * 19349663 ^ k * 83492791 ^ 0x5C17) & 0xffffffff
    v = (v ^ (v >> 13)) * 0x5bd1e995 & 0xffffffff
    return (v ^ (v >> 15)) / 0xffffffff


# ---------------- сеть ----------------
def network(W):
    """role: (x, z) -> (роль материала, схема 'streets'|'parks', группа высоты)."""
    role = {}

    def add(cells, mat, sch, grp):
        for c in cells:
            if c not in role: role[c] = (mat, sch, grp)
    # проспект и тротуары — сечение по X (группа 'av:X')
    for x in range(-800, -724):
        for z in range(1812, 1821):
            if -771 <= x <= -767: continue
            m = 'walk' if z in (1812, 1813, 1819, 1820) else ('edge' if z in (1814, 1818) else 'road')
            if -729 <= x <= -725 and z not in (1814, 1815, 1816, 1817, 1818): m = 'edge'
            role[(x, z)] = (m, 'streets', f'av:{x}')
    for z in range(1776, 1850):                              # проспект Сити — сечение по Z
        for x in range(-771, -766):
            role.setdefault((x, z), ('edge' if x in (-771, -767) else 'road', 'streets', f'pr:{z}'))
    for x in range(-784, -729):                              # Северная
        for z in range(1788, 1793):
            role.setdefault((x, z), ('edge' if z in (1788, 1792) else 'road', 'streets', f'sn:{x}'))
    for x in range(-800, -729):                              # Южная
        for z in range(1838, 1843):
            role.setdefault((x, z), ('edge' if z in (1838, 1842) else 'road', 'streets', f'ss:{x}'))
    for z in range(1776, 1850):                              # Пограничная
        for x in range(-729, -724):
            role.setdefault((x, z), ('edge' if x in (-729, -725) else 'road', 'streets', f'sb:{z}'))
    # этап 3
    add(rect(-766, -744, 1821, 1829), 'sq', 'parks', 'sq')
    add(rect(-743, -730, 1821, 1829), 'sq', 'parks', 'sq2')
    add(rect(-747, -740, 1793, 1811), 'path', 'parks', 'al')
    for k, x0, x1, z0, z1, st in P.PATHS:
        if k in ('p_look', 'p_pond', 'p_park'):
            for c in sorted(rect(x0, x1, z0, z1)):
                g = f'{k}:{c[0]}' if z0 == z1 else f'{k}:{c[1]}'
                role.setdefault(c, ('path', 'parks', g))
    sink = {(x, z) for x in range(-800, -760) for z in range(1840, 1860) if W.surf(x, z) < 50}
    for c in rect(-788, -777, 1844, 1855) - sink:
        role.setdefault(c, ('path', 'parks', 'look'))          # смотровая — плоская
    x0, x1, z0, z1 = P.POND
    pond = rect(x0, x1, z0, z1) - {(x0, z0), (x0, z1), (x1, z0), (x1, z1)}
    for c in pond: role[c] = ('pond', 'parks', 'pond')
    return role, sink, pond


def solve_heights(W, role):
    net = set(role)
    grp = {c: role[c][2] for c in net}
    members = {}
    for c, g in grp.items(): members.setdefault(g, []).append(c)

    def t0(x, z):
        hs = sorted(W.surf(x + a, z + b) + 1 for a in range(-2, 3) for b in range(-2, 3)
                    if W.surf(x + a, z + b) >= 55)
        return hs[len(hs) // 2]
    H = {c: float(t0(*c)) for c in net}
    for _ in range(10):
        H = {c: (H[c] * 2 + sum(H.get((c[0] + a, c[1] + b), H[c]) for a, b in N4)) / 6 for c in net}
    # якоря: Старый город (X −724) и улица-набережная (Z 1850) — верх покрытия построенного
    anchors = {}
    for c in net:
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n in net or not (n[0] >= -724 or n[1] >= 1850): continue
            t = street_top(W, *n)
            if t is not None and abs(t - H[c]) < 4: anchors[n] = t
    for g, cs in members.items():                            # группы — одной высотой (медиана)
        v = sorted(round(H[c] * 2) / 2 for c in cs)[len(cs) // 2]
        for c in cs: H[c] = v
    # не выше/ниже якорей больше чем на 0.5 за клетку; группы опускаются/поднимаются целиком
    dist = {}
    for a in anchors:
        d = {a: 0}; q = deque([a])
        while q:
            c = q.popleft()
            for u, v in N4:
                n = (c[0] + u, c[1] + v)
                if n in net and n not in d: d[n] = d[c] + 1; q.append(n)
        for c, k in d.items():
            if c in net:
                lo, hi = dist.get(c, (-1e9, 1e9))
                dist[c] = (max(lo, anchors[a] - 0.5 * k), min(hi, anchors[a] + 0.5 * k))
    for c, (lo, hi) in dist.items(): H[c] = min(max(H[c], lo), hi)
    bnd = {g: [] for g in members}                         # внешние соседи группы: (сосед, якорь?)
    for c, g in grp.items():
        for a, b in N4:
            n = (c[0] + a, c[1] + b)
            if n in net and grp[n] != g: bnd[g].append((n, False))
            elif n in anchors: bnd[g].append((n, True))
    for _ in range(500):                                   # только опускание: сходится, перепад <= 0.5
        changed = False
        for g, cs in members.items():
            if not bnd[g]: continue
            hi = min((anchors[n] if isa else H[n]) + 0.5 for n, isa in bnd[g])
            if H[cs[0]] > hi + 1e-9:
                for c in cs: H[c] = hi
                changed = True
        if not changed: break
    pond_level = H[members['pond'][0]]
    if pond_level != int(pond_level):                         # пруд: уровень берега — целый блок
        for c in members['pond']: H[c] = math.floor(pond_level)
    return H, anchors


# ---------------- постройка ----------------
class Sch:
    def __init__(self, W): self.W = W; self.c = {}

    def put(self, x, y, z, b): self.c[(x, y, z)] = b

    def plant_top(self, x, z):
        y = self.W.surf(x, z) + 1
        while self.W.block(x, y, z) == 'plant': y += 1
        return y - 1


def pave(S, x, z, h, full, slab, clear_to=None):
    """Покрытие колонны до высоты h (шаг 0.5); ниже — камень до грунта; выше — расчистка."""
    g = S.W.surf(x, z)
    if h == int(h):
        top = int(h) - 1
        S.put(x, top, z, full)
    else:
        top = int(h)
        S.put(x, top - 1, z, full); S.put(x, top, z, slab)
    for y in range(g + 1, (top if h == int(h) else top - 1)): S.put(x, y, z, 'stone')
    for y in range(top + 1, max(S.plant_top(x, z), g, clear_to or 0) + 1): S.put(x, y, z, 'air')
    return top


def item_y(S, H, x, z, full='quartz_block'):
    """Y предмета на мощении: на полублоке — полублок меняется на полный блок (висящие, BOT.md §12)."""
    h = H[(x, z)]
    if h == int(h): return int(h)
    S.put(x, int(h), z, full)
    return int(h) + 1


def tree(S, x, y, z, kind='birch', trunk=4):
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
    """Скамейка DECOR §3.3а: face — куда смотрит сидящий ('n','s','e','w'); x,z — первый люк (З/С край)."""
    st = {'s': 3, 'n': 2, 'e': 1, 'w': 0}[face]
    if face in ('n', 's'):
        cells = [(x + i, z) for i in range(n + 2)]; ends = ('trapdoor:6', 'trapdoor:7')
    else:
        cells = [(x, z + i) for i in range(n + 2)]; ends = ('trapdoor:4', 'trapdoor:5')
    for i, (cx, cz) in enumerate(cells):
        S.put(cx, y, cz, ends[0] if i == 0 else ends[1] if i == len(cells) - 1 else f'birch_stairs:{st}')
    return cells


def build(W):
    role, sink, pond = network(W)
    H, anchors = solve_heights(W, role)
    ST, PK = Sch(W), Sch(W)
    SCH = {'streets': ST, 'parks': PK}
    net = set(role)
    wx = {(x, z) for x in range(-766, -743) for z in range(1821, 1830)
          if (x, z) in {c for c in P.rect_canyon(W)}} if hasattr(P, 'rect_canyon') else None
    cv = W._cv
    air = lambda x, z: cv['air'][(z - cv['z0']) * cv['w'] + x - cv['x0']] or 0
    canyon = {(x, z) for x in range(-806, -700) for z in range(1768, 1869) if air(x, z) >= 8 and (W.cave_top(x, z) or 0) >= 50}
    wx = {(x, z) for x in range(-766, -743) for z in range(1821, 1830)} & canyon
    lamps, trees_s, marks = set(), set(), {}

    # фонари: тротуары проспекта (внешний край), проспект Сити, улицы — через 8 блоков, не у перекрёстков
    def near_cross(x, z, r=2):
        return any(role.get((x + a, z + b), ('', '', ''))[2].split(':')[0] not in (role[(x, z)][2].split(':')[0], 'av')
                   and (x + a, z + b) in net and role[(x + a, z + b)][1] == 'streets'
                   for a in range(-r, r + 1) for b in range(-r, r + 1))
    for x in range(-796, -725, 8):
        for z in (1812, 1820):
            if not (-773 <= x <= -765) and not (-731 <= x): lamps.add((x, z))
    for x in range(-792, -725, 8):                            # берёзы между фонарями
        for z in (1812, 1820):
            if not (-773 <= x <= -765) and not (-731 <= x): trees_s.add((x, z))
    for z in range(1780, 1849, 8):
        for x in (-771, -767):
            if not near_cross(x, z, 3): lamps.add((x, z))
    for x in range(-780, -730, 8):
        for z in (1788, 1792):
            if not near_cross(x, z, 3): lamps.add((x, z))
    for x in range(-796, -730, 8):
        for z in (1838, 1842):
            if not near_cross(x, z, 3): lamps.add((x, z))
    for z in range(1780, 1849, 8):
        for x in (-729, -725):
            if not near_cross(x, z, 3) and not (1809 <= z <= 1823): lamps.add((x, z))

    # покрытие
    for (x, z), (m, sch, g) in role.items():
        S = SCH[sch]; h = H[(x, z)]
        if m == 'pond': continue
        full, slab = MAT[m]
        if m == 'sq':
            if (x, z) in wx: full, slab = 'glass', 'glass'
            elif (x - z) % 6 == 0 or (x + z) % 6 == 0: full, slab = MAT['sq_line']
        if m == 'road' and h32(x, z, 3) < 0.10: full = 'stone:5'          # андезит — пятна
        if m == 'walk' and (x + 1) % 4 == 0: full = 'stone:4'              # диорит — ритм тротуара
        top = pave(S, x, z, h, full, slab)
        marks[(x, z)] = top
    # обочины: кольца 1..3 вокруг сети — откос 1:1, сверху трава
    SH = {}
    for (x, z) in net:
        for a in range(-3, 4):
            for b in range(-3, 4):
                c = (x + a, z + b)
                if c in net or c in sink: continue
                d = max(abs(a), abs(b)); lvl = math.ceil(H[(x, z)]) - 1
                lo, hi = SH.get(c, (-1e9, 1e9)); SH[c] = (max(lo, lvl - d), min(hi, lvl + d))
    SHO = 0
    built_cols = {(k[0], k[2]) for k in W.pre}
    for c, (lo, hi) in SH.items():
        x, z = c
        if not (-800 <= x <= -725 and 1776 <= z <= 1856) or c in built_cols: continue
        near = min((max(abs(x - n[0]), abs(z - n[1])), role[n][1]) for n in
                   [(x + a, z + b) for a in range(-3, 4) for b in range(-3, 4)] if n in net)
        S = SCH[near[1]]
        g = W.surf(x, z)
        if W.water(x, z) is not None and W.water(x, z) > g: continue
        lo_i, hi_i = math.ceil(lo), math.floor(hi)
        if lo_i > hi_i: hi_i = lo_i
        if g > hi_i:
            for y in range(hi_i + 1, max(S.plant_top(x, z), g) + 1): S.put(x, y, z, 'air')
            S.put(x, hi_i, z, 'grass'); SHO += 1
        elif g < lo_i:
            for y in range(g + 1, lo_i): S.put(x, y, z, 'stone')
            S.put(x, lo_i, z, 'grass')
            for y in range(lo_i + 1, S.plant_top(x, z) + 1): S.put(x, y, z, 'air')
            SHO += 1

    # фонари и деревья (этап 2)
    for (x, z) in lamps:
        S = SCH[role[(x, z)][1]]; y = item_y(S, H, x, z)
        for i, b in enumerate(LAMP): S.put(x, y + i, z, b)
    for (x, z) in trees_s:
        y = item_y(ST, H, x, z)
        ST.put(x, y - 1, z, 'grass'); tree(ST, x, y, z, 'birch', 5)     # крона с 3-го блока — над головой

    # ---------- этап 3 ----------
    lvl = lambda c: math.ceil(H[c]) - 1                       # Y верхнего блока покрытия
    # окно в каньон: стекло вровень, под ним — воздух до пустоты; стенки шахты — морские фонари
    shaft = 0
    for (x, z) in wx:
        top = lvl((x, z)); ct = W.cave_top(x, z)
        for y in range(ct + 1, top): PK.put(x, y, z, 'air'); shaft += 1
    rim = {(x + a, z + b) for x, z in wx for a, b in N4} - wx
    for (x, z) in rim:
        ct = W.cave_top(x, z) or 0
        top = lvl((x, z)) if (x, z) in H else W.surf(x, z)
        for y in range(top - 3, ct + 1, -4):
            if any((x + a, z + b) in wx for a, b in N4) and y > 50 and z > 1820: PK.put(x, y, z, 'sea_lantern')
    for (x, z) in rim:                                          # рамка окна — кварц-колонна
        if (x, z) in H and role[(x, z)][0] == 'sq': PK.put(x, lvl((x, z)), z, 'quartz_block:2')
    # «Кристалл»
    _, cx0, cx1, cz0, cz1 = P.INSTALL[0]
    b0 = max(lvl((x, z)) for x in range(cx0, cx1 + 1) for z in range(cz0, cz1 + 1))
    for x in range(cx0, cx1 + 1):
        for z in range(cz0, cz1 + 1):
            corner = x in (cx0, cx1) and z in (cz0, cz1)
            inner = cx0 < x < cx1 and cz0 < z < cz1
            PK.put(x, b0, z, 'quartz_block:2')
            for y in (b0 + 1, b0 + 2):
                if not corner: PK.put(x, y, z, 'sea_lantern' if inner else 'stained_glass:3')
            if inner:
                for y in (b0 + 3, b0 + 4, b0 + 5): PK.put(x, y, z, 'stained_glass:3')
    PK.put(cx0 + 1, b0 + 6, cz0 + 1, 'stained_glass:0'); PK.put(cx0 + 2, b0 + 6, cz0 + 2, 'stained_glass:0')
    PK.put(cx0 + 1, b0 + 7, cz0 + 1, 'stained_glass:0')
    # фонтан 9×9 в сквере (DECOR §5.1, палитра med): слой y0 — уровень мощения
    fx0, fx1, fz0, fz1 = P.FOUNTAIN
    fy = lvl((fx0 + 4, fz0 + 4))
    for (x, y, z), b in GF.build_core(GF.PALETTES['med'], fx0, fy, fz0).items(): PK.put(x, y, z, b)
    # пруд: берег вровень с мощением, вода на той же Y (§6), глубина 3, дно — песок на камне
    wy = lvl(next(iter(pond)))
    px0, px1, pz0, pz1 = P.POND
    for (x, z) in pond:
        g = W.surf(x, z)
        edge = any((x + a, z + b) not in pond for a, b in N4)
        if edge:
            for y in range(g + 1, wy): PK.put(x, y, z, 'stonebrick')
            for y in range(min(g, wy - 1), wy - 3, -1): PK.put(x, y, z, 'stonebrick')
            PK.put(x, wy, z, 'stonebrick')
        else:
            for y in range(wy - 2, wy + 1): PK.put(x, y, z, 'water')
            lamp = (x - px0) % 3 == 2 and (z - pz0) % 3 == 2
            PK.put(x, wy - 3, z, 'sea_lantern' if lamp else 'sand')
            PK.put(x, wy - 4, z, 'stone')
            for y in range(g + 1, wy - 4): PK.put(x, y, z, 'stone')
        for y in range(wy + 1, max(PK.plant_top(x, z), g) + 1): PK.put(x, y, z, 'air')
    # «Шар» в Каньон-парке: постамент и шар из голубого стекла с морским фонарём
    _, sx0, sx1, sz0, sz1 = P.INSTALL[1]
    scx, scz = (sx0 + sx1) // 2, (sz0 + sz1) // 2
    sy = max(W.surf(x, z) for x in range(sx0, sx1 + 1) for z in range(sz0, sz1 + 1)) + 1
    for x in range(sx0, sx1 + 1):
        for z in range(sz0, sz1 + 1):
            for y in range(W.surf(x, z) + 1, sy): PK.put(x, y, z, 'stone')
            PK.put(x, sy - 1, z, 'grass')
    PK.put(scx, sy, scz, 'quartz_block:2')
    for dy, pat in ((1, 'cross'), (2, 'full'), (3, 'full'), (4, 'cross')):
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                if pat == 'cross' and a and b: continue
                PK.put(scx + a, sy + dy, scz + b, 'sea_lantern' if (a, b) == (0, 0) and dy in (2, 3) else 'stained_glass:3')
    # «Провал»: ограждение вокруг провала на кольце мощения
    ring = {(x + a, z + b) for x, z in sink for a in (-1, 0, 1) for b in (-1, 0, 1)} - sink
    rail = 0
    for (x, z) in ring:
        if (x, z) in H and role[(x, z)][1] == 'parks':
            PK.put(x, item_y(PK, H, x, z), z, 'iron_bars'); rail += 1
    # скамейки, урны, кашпо, деревья, фонари парков
    benches = []

    def add_bench(x, z, face, n=2):
        cells = [(x + i, z) for i in range(n + 2)] if face in ('n', 's') else [(x, z + i) for i in range(n + 2)]
        if any(c not in H for c in cells): print('  скамейка не на мощении:', x, z); return False
        if any(c in wx for c in cells): print('  скамейка на стекле окна:', x, z); return False
        y = max(H[c] for c in cells)
        if any(H[c] != y for c in cells): print('  скамейка на неровном мощении:', x, z); return False
        by = item_y(PK, H, cells[0][0], cells[0][1])
        for c in cells[1:]: item_y(PK, H, *c)
        bench(PK, x, by, z, face, n); benches.append((x, z, face)); return True
    add_bench(-743, 1823, 'e'); add_bench(-731, 1823, 'w')           # у фонтана
    add_bench(-762, 1821, 's'); add_bench(-751, 1828, 'n')          # площадь — лицом к окну/проспекту
    add_bench(-788, 1848, 'e')                                       # «Провал» — лицом к провалу
    add_bench(-747, 1800, 'e'); add_bench(-740, 1800, 'w')          # аллея
    urns = [(-743, 1827), (-731, 1827), (-747, 1805), (-777, 1846)]
    for (x, z) in urns: PK.put(x, item_y(PK, H, x, z), z, 'cauldron')
    pots = [(-743, 1821), (-743, 1829), (-730, 1821), (-730, 1829), (-766, 1821), (-744, 1829)]
    for (x, z) in pots:
        y = item_y(PK, H, x, z); PK.put(x, y, z, 'hardened_clay'); PK.put(x, y + 1, z, 'leaves:4')
    for (x, z) in ((-745, 1795), (-745, 1809), (-742, 1795), (-742, 1809)):   # аллея — берёзы в газоне
        y = item_y(PK, H, x, z); PK.put(x, y - 1, z, 'grass'); tree(PK, x, y, z, 'birch', 4)
    for (x, z) in ((-778, 1831), (-774, 1829)):              # аллея парка — фонари на газоне рядом
        g = W.surf(x, z); PK.put(x, g, z, 'quartz_block:1')
        for i, b in enumerate(LAMP[1:]): PK.put(x, g + 1 + i, z, b)
        for y in range(g + 1 + len(LAMP) - 1, PK.plant_top(x, z) + 1): PK.put(x, y, z, 'air')
        lamps.add((x, z))
    for (x, z) in ((-754, 1825), (-736, 1829), (-782, 1846), (-780, 1854), (-747, 1797), (-747, 1810),
                   (-744, 1801)):
        if (x, z) in H and not any(PK.c.get((x, y, z), 'air') not in ('air',) for y in range(lvl((x, z)) + 1, lvl((x, z)) + 3)):
            y = item_y(PK, H, x, z)
            for i, b in enumerate(LAMP): PK.put(x, y + i, z, b)
            lamps.add((x, z))
    # деревья Каньон-парка — на газоне, не ближе 2 бл. к дорожкам, будущим зданиям, окну и провалу
    busy = set(net) | {c for f in P_FOOT.values() for c in f} | sink | rect(-751, -748, 1806, 1810)
    busy |= {(x, z) for S_ in (PK, ST) for (x, y, z), b in S_.c.items() if b not in ('air', 'grass', 'stone')}
    ptrees = []
    park = {(x + a, z + b) for (x, z) in canyon for a in range(-2, 3) for b in range(-2, 3)} & rect(-800, -725, 1796, 1848)
    lawn = rect(-798, -727, 1778, 1847) - park                 # газоны вне парка — реже, дальше от будущих зданий
    for (x, z) in sorted(park) + sorted(lawn):
        inpark = (x, z) in park
        if (x * 3 + z * 5) % (5 if inpark else 9) != 0: continue
        m = 1 if inpark else 2
        if any((x + a, z + b) in busy for a in range(-m, m + 1) for b in range(-m, m + 1)): continue
        if any(abs(x - t[0]) + abs(z - t[1]) < (4 if inpark else 7) for t in ptrees): continue
        g = W.surf(x, z)
        if g < 60: continue
        tree(PK, x, g + 1, z, 'oak' if h32(x, z, 9) < 0.4 else 'birch', 4 + int(h32(x, z, 2) * 2)); ptrees.append((x, z))
    return ST, PK, H, role, lamps, trees_s, ptrees, benches, wx, sink, pond, SHO, anchors, shaft, rail


P_FOOT = {}


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before('city-1-streets.json')) if 'city-1-streets.json' in names else World()
    # следы будущих зданий (план) — деревья и фонари их не занимают
    for k, _, x0, x1, z0, z1, st, occ, *_r in P.TOWERS:
        P_FOOT[k] = {(x, z) for x in range(x0 - 1, x1 + 2) for z in range(z0 - 1, z1 + 2)}
    for k, x0, x1, z0, z1, st in P.PATHS:
        if k not in ('p_look', 'p_pond', 'p_park'): P_FOOT[k] = rect(x0, x1, z0, z1)
    P_FOOT['top'] = rect(-800, -792, 1784, 1793)
    ST, PK, H, role, lamps, trees_s, ptrees, benches, wx, sink, pond, SHO, anchors, shaft, rail = build(W)
    net = set(role)
    print(f'сеть: клеток {len(net)} (улицы {sum(1 for v in role.values() if v[1] == "streets")}, этап 3 '
          f'{sum(1 for v in role.values() if v[1] == "parks")}) | верх покрытия Y {min(H.values())}…{max(H.values())} | '
          f'якорей (Старый город, набережная) {len(anchors)}')
    print(f'фонарей {len(lamps)}, берёз на тротуарах {len(trees_s)}, деревьев парка {len(ptrees)}, скамеек {len(benches)}, '
          f'обочин изменено {SHO}, окно {len(wx)} кл. (шахта: воздуха {shaft}), ограждение «Провала» {rail}')

    outs = {}
    for nm, S in (('city-1-streets.json', ST), ('city-1-parks.json', PK)):
        cells = S.c
        xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
        o = (min(xs), min(ys), min(zs))
        rel = {(x - o[0], y - o[1], z - o[2]): b for (x, y, z), b in cells.items()}
        order = dl.compute_order(rel)
        dl.save(rel, os.path.join(args.outdir, nm), order)
        outs[nm] = (o, rel, order, cells)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {max(xs) - o[0] + 1} {max(ys) - o[1] + 1} {max(zs) - o[2] + 1} | '
              f'записей {len(cells)}')

    print('== ПРОВЕРКИ ==')
    W2 = {}
    W2.update(ST.c)
    base = lambda x, y, z: W.block(x, y, z)
    for nm, (o, rel, order, cells) in outs.items():
        prev = dict(W2) if nm == 'city-1-parks.json' else {}

        def terr(x, y, z, o=o, prev=prev):
            k = (x + o[0], y + o[1], z + o[2])
            b = prev.get(k) or base(*k)
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:6]: print('   ', m)
        be = dl.check_bench_front(rel, terr)
        print(f'{nm}: скамейки (место для ног): ошибок {len(be)}', be[:3])

    ALL = dict(ST.c); ALL.update(PK.c)

    def final(x, y, z):
        b = ALL.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
    leak = [(x + a, y, z + c) for (x, y, z), b in ALL.items() if b == 'air' for a, c in N4
            if (x + a, y, z + c) not in ALL and W.block(x + a, y, z + c) == 'water']
    print('вода рельефа, открытая в воздух схемы:', len(leak), leak[:4])
    over = [(x, y, z) for (x, y, z), b in ALL.items() if (x, z) in wx and b not in ('air', 'glass')
            and math.ceil(H[(x, z)]) - 1 <= y <= math.ceil(H[(x, z)]) + 1]
    print('предметы на стекле окна в каньон:', len(over), over[:3])
    jump = [(c, n) for c in net for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if n in net and abs(H[c] - H[n]) > 0.5
            and 'pond' not in (role[c][0], role[n][0])]
    edge = [(c, a) for c in net for a in anchors if abs(c[0] - a[0]) + abs(c[1] - a[1]) == 1 and abs(H[c] - anchors[a]) > 0.5]
    print('перепад покрытия между соседями > 0.5 —', len(jump), '| со стыком (Старый город, набережная) > 0.5 —', len(edge), edge[:3])
    fl = floating_over_paving(final, ALL, {c: H[c] for c in net if role[c][0] != 'pond'})
    print('висящие над мощением (под предметом воздух или нижний полублок):', len(fl), fl[:4])
    low = [k for k, b in ALL.items() if b != 'air' and k[1] < 60 and RES(k[0], k[2])]
    print('в резерве трасс ниже Y 60 —', len(low), low[:4])
    digs = {}
    for (x, y, z), b in ALL.items():                         # выемки: воздух ниже исходной поверхности
        if b == 'air' and y <= W.surf(x, z) and (x, z) not in wx: digs[(x, z)] = min(digs.get((x, z), 999), y)
    roofs = [(y - W.cave_top(x, z) - 1, x, z) for (x, z), y in digs.items() if W.cave_top(x, z) is not None]
    print('кровля каньона под выемками схемы (кроме окна — задумано): мин.', min(roofs)[0] if roofs else '—', '(норма >= 3)')
    # проходимость — от улицы-набережной (проход в стенке на проспекте Сити)
    WALK_X, WALK_Z, WALK_Y = (-806, -718), (1770, 1858), (55, 95)
    start = (-769, 65.0, 1852)
    busy_cells = {(x, z) for (x, y, z), b in ALL.items() if b not in ('air',) and (x, z) in net and y >= math.ceil(H[(x, z)])}

    def walk(fin):                                         # только по мощению (газоны не в счёт) + набережная, Старый город
        f2 = lambda x, y, z: fin(x, y, z) if (x, z) in net or z >= 1849 or x >= -724 else 'air'
        return dl.walk_reachable(f2, start, WALK_X, WALK_Z, WALK_Y)
    seen = walk(final)
    miss = [c for c in net if c not in busy_cells and role[c][0] != 'pond' and (c not in wx or True)
            and not dl.reached(seen, c[0], H[c], c[1])]
    print(f'ПРОХОДИМОСТЬ без прыжков от улицы-набережной (−769,1852): клеток сети {len(net) - len(busy_cells)}, недостижимо {len(miss)}',
          miss[:6])
    targets = {'Старый город: проспект (−724,1816)': (-724, 1816), 'Старый город: переулок (−724,1790)': (-724, 1790),
               'Старый город: переулок (−724,1840)': (-724, 1840), 'запад проспекта (−800,1816)': (-800, 1816),
               'север проспекта Сити (−769,1776)': (-769, 1776), 'Площадь Сити, стекло окна': sorted(wx)[len(wx) // 2],
               'сквер у фонтана (−742,1825)': (-742, 1825), 'аллея (−744,1793)': (-744, 1793), 'берег пруда (−776,1804)': (-776, 1804),
               '«Провал» (−786,1850)': (-786, 1850), 'аллея парка у «Шара» (−778,1830)': (-778, 1830)}
    bad = 0
    for k, (x, z) in targets.items():
        hh = H.get((x, z), street_top(W, x, z) or 67)
        ok = dl.reached(seen, x, hh, z); bad += 0 if ok else 1
        print(f'  маршрут → {k}: {ok}')
    print('ИТОГО недостижимых точек:', len(miss) + bad)
    fin_of = lambda cells: (lambda x, y, z: (lambda b: 'air' if b == 'plant' else ('stone' if b == 'ground' else b))(
        cells.get((x, y, z)) or W.block(x, y, z)))
    # негатив 1: оба выхода на набережную (проспект Сити и Пограничная) перекрыты стенкой в 2 блока
    negc = dict(ALL)
    for x in list(range(-771, -766)) + list(range(-729, -724)):
        for d in (0, 1): negc[(x, math.ceil(H[(x, 1847)]) + d, 1847)] = 'stonebrick'
    for z in range(1844, 1856):
        if (-777, z) in H:
            for d in (0, 1): negc[(-777, math.ceil(H[(-777, z)]) + d, z)] = 'stonebrick'
    s2 = walk(fin_of(negc))
    print('НЕГАТИВ: выходы на набережную перекрыты — Площадь Сити недостижима:', not dl.reached(s2, -755, H[(-755, 1825)], 1825))
    # негатив 2: ступень в полный блок поперёк проспекта Сити у северного конца
    negc = dict(ALL)
    for x in range(-771, -766): negc[(x, math.ceil(H[(x, 1784)]), 1784)] = 'stonebrick'
    s3 = walk(fin_of(negc))
    print('НЕГАТИВ: ступень 1 блок поперёк проспекта Сити (Z 1784) — северный конец недостижим:',
          not dl.reached(s3, -769, H[(-769, 1776)], 1776))
    negc = dict(ALL); c = (-742, 1825); negc[(c[0], math.ceil(H[c]) + 1, c[1])] = 'cauldron'
    fl2 = floating_over_paving(fin_of(negc), negc, {c: H[c]})
    print('НЕГАТИВ: урна на блок выше мощения — висящие найдены:', len(fl2) > 0)
    if args.preview: preview(args.preview, final, H, net, wx, W)


def preview(path, final, H, net, wx, W_):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1 = -802, -720, 1774, 1858
    S = 9
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    img = Image.new('RGB', (mw + 40 + 620, max(mh + 60, 920)), 'white')
    dr = ImageDraw.Draw(img)
    CX = dict(CL); CX.update({'stone:6': (135, 138, 138), 'stone:5': (120, 122, 122), 'stone:4': (205, 205, 205),
                              'double_stone_slab:8': (170, 170, 170), 'glass': (170, 225, 245), 'stained_glass:3': (120, 190, 240),
                              'stained_glass:0': (240, 240, 250), 'leaves:6': (110, 150, 60), 'leaves:4': (60, 120, 40),
                              'log:2': (220, 220, 210), 'grass': (95, 150, 60), 'sand': (220, 210, 150), 'water': (70, 130, 215)})

    def cc(b):
        return CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 120
            while y > 25 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            if (x, z) in wx: b = 'glass'
            if b == 'stone' and (x, z) not in net:
                k = (max(60, min(y, 80)) - 60) / 20; c = (int(200 - 70 * k), int(210 - 40 * k), int(140 - 60 * k))
                if y < 55: c = (30, 25, 25)
            else: c = cc(b)
            dr.rectangle([20 + (x - X0) * S, 30 + (z - Z0) * S, 20 + (x - X0 + 1) * S - 1, 30 + (z - Z0 + 1) * S - 1], fill=c)
            if (x, z) in net and H[(x, z)] != int(H[(x, z)]):
                dr.line([20 + (x - X0) * S + 1, 30 + (z - Z0) * S + S - 2, 20 + (x - X0) * S + S - 2, 30 + (z - Z0) * S + 1], fill=(60, 60, 60))
    for x in range(-800, X1 + 1, 10): dr.text((20 + (x - X0) * S - 8, 16), str(x), fill='black', font=F(10))
    for z in range(1780, Z1 + 1, 10): dr.text((0, 30 + (z - Z0) * S - 5), str(z), fill='black', font=F(9))
    dr.text((20, 2), 'Сити, этапы 1–3 (city-1-streets + city-1-parks) — вид сверху; косая черта — полублок', fill='black', font=F(12))
    bx = mw + 40; S2 = 6

    cv = W_._cv
    def profile(y0, label, pts, lab, yr=(56, 80)):
        dr.text((bx, y0 - 14), label, fill='black', font=F(11))
        for u, (x, z) in enumerate(pts):
            ct = W_.cave_top(x, z); ca = cv['air'][(z - cv['z0']) * cv['w'] + x - cv['x0']] or 0
            for y in range(yr[0], yr[1] + 1):
                b = final(x, y, z)
                if ct is not None and ca >= 8 and ct - ca < y <= ct and b == 'stone': b = 'air'
                if b == 'air': continue
                n = b.split(':')[0]
                c = (150, 140, 110) if b == 'stone' else cc(b)
                yy = y0 + (yr[1] - y) * S2
                half = n in ('stone_slab', 'wooden_slab') and int((b.split(':') + ['0'])[1]) < 8
                dr.rectangle([bx + u * S2, yy + (S2 // 2 if half else 0), bx + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
            if u % 10 == 0: dr.text((bx + u * S2, y0 + (yr[1] - yr[0] + 1) * S2 + 1), str(lab(x, z)), fill='black', font=F(8))
    profile(30, 'главный проспект Z=1816, X −800…−720 (Y 56…80)', [(x, 1816) for x in range(-800, -719)], lambda x, z: x)
    profile(215, 'проспект Сити X=−769, Z 1776…1856', [(-769, z) for z in range(1776, 1857)], lambda x, z: z)
    wz = sorted({z for _, z in wx})[len({z for _, z in wx}) // 2]
    profile(400, f'разрез окна в каньон Z={wz}, X −770…−745 (Y 30…80)', [(x, wz) for x in range(-770, -744)], lambda x, z: x, (30, 80))
    profile(740, 'пруд и «Провал»: X=−777, Z 1800…1856', [(-777, z) for z in range(1800, 1857)], lambda x, z: z)
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
