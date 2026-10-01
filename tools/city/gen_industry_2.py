"""Промзона, этап 2 (CITY.md §7.9, геометрия — tools/city/plan_industry_v1.py; этап 1 построен). Три схемы,
строить строго по порядку, каждую — отдельным .cmd и только после итога «ошибок 0» у предыдущей:

- industry-2-ground.json — техгалереи под всеми проездами (пол Y 60, внутри 4×3: проход 3 + кабельный ряд,
  каменный кирпич, морские фонари в своде; на рампе Заводской свод — само мощение), резерв выхода коллектора
  к проспекту (тупик Z 1821); цех генерации булыжника — чанк (−39, 115) целиком, пол Y 14, внутри Y 15…19,
  замкнутая коробка (вокруг — пустоты каньона), свет в полу; лаз из склада (стремянка 1×1, деревянный люк
  вровень с полом) и кабельный канал 1×1 рядом (люк iron_trapdoor:8); подходы к корпусам этапа 2,
  дорожка к ветрякам (3 бл.), фонари вровень с мощением;
- industry-2-build.json — диспетчерская (башня 10×10, 6 этажей, голубое стекло, часы, мачта; место загрузчика
  чанков (−617, 67, 1879) — центр чанка (−39, 117) — свободно; щитовая и серверная МЭ 3×3 с проёмами),
  подстанция (лестница в техгалерею под Промышленным, ограждение проёма), цех автокрафта МЭ (шеды),
  лаборатория материи (кварц, фиолетовые витражи, стеклянный купол), машинный зал, насосная (бассейн
  4×2 — источник для помп); в каждом корпусе щитовая с кабельной шахтой;
- industry-2-green.json — оранжерея селекции (стеклянный свод блоками на кварцевых рёбрах, грядки из пашни с
  поливочными канавками, проходы 3 бл.), три ветряка (мачта, гондола, лопасти — декор; генератор IC2 на
  мачте ставит владелец).
Модовых блоков нет; механизмы, загрузчик, кабели — владелец.

Запуск: gen_industry_2.py [--outdir schemas] [--preview docs/districts/industry-2-preview.png]
Мир — World(built_before('industry-2-ground.json')) + съёмка docs/terrain/industry-voids.json.
Проверки: опоры/вода/порядок для каждой схемы; проходимость без прыжков от тротуара проспекта (двери, залы,
щитовые, этажи диспетчерской, техгалереи — каждая ветка, оранжерея, ветряки); цех булыжника — от низа лаза;
лаз непрерывен; подходы к дверям; свет; ширина галерей и проходов ≥ 3; задетое построенное; загрузчик
свободен и в центре чанка; цех булыжника = чанк; негативные прогоны.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import World, REPO, built_before, save_schema, dl, col, Tower  # noqa: E402
from oldtown_lib import door_approach_issues  # noqa: E402
import plan_industry_v1 as PI  # noqa: E402
from gen_industry_1 import (Terrain, Plan, B, windows, place_lamps, man, rc, obj, TOP, N4, DOOR_IN,  # noqa: E402
                            LADDER_META, ROAD, LAMP, FLOOR, PLATE)

NAMES = ['industry-2-ground.json', 'industry-2-build.json', 'industry-2-green.json']
GY0, GY1 = 60, 64                                  # галереи: пол 60, внутри 61…63, свод 64
GAL = [(-626, -623, 1822, 1919), (-656, -594, 1886, 1889), (-656, -594, 1851, 1854)]   # внутренности (4 бл.)
CX, CZ, CF, CC = -39, 115, 14, 20                  # цех булыжника: чанк, пол, потолок
COB = (CX * 16, CX * 16 + 15, CZ * 16, CZ * 16 + 15)
LAZ, CAB = (-610, 1840), (-609, 1840)              # лаз (стремянка) и кабельный канал — в складе, над цехом
LOADER = PI.LOADER_BLOCK
PAVE_KEEP = ('double_stone_slab', 'stone_slab', 'stonebrick', 'sea_lantern')
STAIR_X = (-598, -596)                             # лестница подстанции в галерею
WIND_Z = (1831, 1838, 1845)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'industry-2-preview.png'))
    return p.parse_args()


# ============================================================================== ground: галереи, цех, подходы
def build_ground(P):
    W, G = P.W, P.G
    gi = set()
    for x0, x1, z0, z1 in GAL:
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1): gi.add((x, z))
    shell = {(x + a, z + b) for (x, z) in gi for a in (-1, 0, 1) for b in (-1, 0, 1)} - gi
    keep = lambda x, y, z: y >= GY1 and W.block(x, y, z).split(':')[0] in PAVE_KEEP
    for (x, z) in shell:
        for y in range(GY0, GY1 + 1):
            if not keep(x, y, z): G[(x, y, z)] = 'stonebrick'
    for (x, z) in gi:
        G[(x, GY0, z)] = 'stonebrick'
        for y in range(GY0 + 1, GY1): G[(x, y, z)] = 'air'
        if not keep(x, GY1, z): G[(x, GY1, z)] = 'stonebrick'
    P.gal = gi
    P.targets['техгалереи'] = [(x, GY0 + 1, z) for (x, z) in gi]
    P.lamp_c.setdefault(NAMES[0], []).extend((x, GY1, z) for (x, z) in gi if not keep(x, GY1, z))
    # цех булыжника: коробка, внутри воздух, пол — полированный андезит
    x0, x1, z0, z1 = COB
    for x in range(x0 - 1, x1 + 2):
        for z in range(z0 - 1, z1 + 2):
            inner = x0 <= x <= x1 and z0 <= z <= z1
            G[(x, CF, z)] = 'stonebrick'; G[(x, CC, z)] = 'stonebrick'
            for y in range(CF + 1, CC): G[(x, y, z)] = 'air' if inner else 'stonebrick'
            if inner: G[(x, CF, z)] = FLOOR
    P.targets['цех булыжника'] = [(x, CF + 1, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    P.lamp_c.setdefault(NAMES[0], []).extend((x, CF, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                                             if (x, z) not in (LAZ, CAB))
    # лаз и кабельный канал из склада: кольцо из каменного кирпича от потолка цеха до пола склада
    (lx, lz), (kx, kz) = LAZ, CAB
    for x in range(lx - 1, kx + 2):
        for z in range(lz - 1, lz + 2):
            if (x, z) in (LAZ, CAB): continue
            for y in range(CC, TOP): G[(x, y, z)] = 'stonebrick'
    for y in range(CF + 1, TOP): G[(lx, y, lz)] = f'ladder:{LADDER_META[(0, -1)]}'
    G[(lx, TOP, lz)] = 'trapdoor:8'
    for y in range(CC, TOP): G[(kx, y, kz)] = 'air'
    G[(kx, TOP, kz)] = 'iron_trapdoor:8'
    # подходы к корпусам этапа 2/3 и дорожка к ветрякам (вместо газона)
    for k, rects in PI.APRONS.items():
        if k in ('ore', 'prod', 'wh', 'ct'): continue
        for r in rects:
            for (x, z) in rc(*r):
                G[(x, TOP, z)] = ROAD
                for y in range(TOP + 1, TOP + 3):
                    if W.block(x, y, z) not in ('air',): G[(x, y, z)] = 'air'
                P.paved[(x, z)] = 67.0
    P.targets['подходы этапа 2'] = [(x, 67.0, z) for (x, z) in P.paved]
    P.lamp_c[NAMES[0]].extend((x, TOP, z) for (x, z) in P.paved)


# ============================================================================== build
def build_box(P, D, k, top, wall, roof, wall_fn, doors, room, sch, room_mat):
    o = obj(k); x0, x1, z0, z1 = o[2:6]
    b = B(P, D, o[1], (x0, x1, z0, z1), top, wall, roof, sch)
    b.box(wall_fn)
    for (x, z) in b.ring: b.put(x, top + 1, z, 'stone_slab:7' if wall.startswith(('concrete', 'quartz')) else 'stone_slab:5')
    for (x, z, m) in doors: b.door(x, z, m)
    b.room('щитовая', *room, room_mat)
    P.halls[o[1]] = ((x0 + x1) // 2, TOP + 1, (z0 + z1) // 2)
    return b


def pil_fn(rect, period):
    x0, x1, z0, z1 = rect
    return lambda x, z: (x in (x0, x1) and z in (z0, z1)) or (z in (z0, z1) and (x - x0) % period == 0) or \
        (x in (x0, x1) and (z - z0) % period == 0)


def wall_lamps(b, pil, y, skip=()):
    x0, x1, z0, z1 = b.rect
    for (x, z) in b.ring:
        if pil(x, z) and not (x in (x0, x1) and z in (z0, z1)) and (x, z) not in skip: b.put(x, y, z, LAMP)


def build_dispatch(P):
    D = P.B
    o = obj('disp'); x0, x1, z0, z1 = o[2:6]
    t = Tower(P.W, o[1], lambda x, y, z: True, (x0, x1, z0, z1), TOP, 90, glass='stained_glass:3', band='concrete:0',
              floor='concrete:0', lobby='quartz_block')
    t.shell()
    t.door(x0, 1877, 0)
    P.doors.append((x0, TOP + 1, 1877, 0))
    for z in (1876, 1878):                          # рама двери из полных блоков
        for y in range(TOP + 1, TOP + 4): t.put(x0, y, z, 'concrete:0')
    t.put(x0, TOP + 3, 1877, 'concrete:0')

    def room(rect, door, opening=()):
        rx0, rx1, rz0, rz1 = rect
        ring = rc(rx0 - 1, rx1 + 1, rz0 - 1, rz1 + 1) - rc(rx0, rx1, rz0, rz1)
        for (x, z) in ring:
            if x in (x0, x1) or z in (z0, z1): continue
            for y in range(TOP + 1, TOP + 4): t.put(x, y, z, 'concrete:0')
        for (x, z) in rc(rx0, rx1, rz0, rz1):
            for y in range(TOP + 1, TOP + 4): t.put(x, y, z, 'air')
        dx_, dz_, m = door
        t.put(dx_, TOP + 1, dz_, f'birch_door:{m}'); t.put(dx_, TOP + 2, dz_, 'birch_door:8')
        a, b = DOOR_IN[m]
        t.put(dx_ + a, TOP + 1, dz_ + b, PLATE); t.put(dx_ - a, TOP + 1, dz_ - b, PLATE)
        for (ox, oy, oz) in opening: t.put(ox, oy, oz, 'air')
        t.res_k.setdefault(0, set()).update(rc(rx0 - 1, rx1 + 1, rz0 - 1, rz1 + 1) | {(dx_ - a, dz_ - b), (dx_ + a, dz_ + b)})
        return ((rx0 + rx1) // 2, TOP + 1, (rz0 + rz1) // 2)
    P.rooms['Диспетчерская: серверная МЭ'] = room((-614, -612, 1878, 1880), (-615, 1879, 0), [(-615, TOP + 2, 1880)])
    P.rooms['Диспетчерская: щитовая'] = room((-614, -612, 1874, 1876), (-613, 1877, 3), [(-612, TOP + 3, 1877)])
    # кабельная шахта в щитовой (до Y 60), люк вровень с полом
    sx, sz = -612, 1874
    for y in range(60, TOP): t.put(sx, y, sz, f'ladder:{LADDER_META[(1, 0)]}')
    t.put(sx, TOP, sz, 'iron_trapdoor:8')
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            if (a, b) != (0, 0):
                for y in range(59, TOP): t.put(sx + a, y, sz + b, 'stonebrick')
    t.put(sx, 59, sz, 'stonebrick')
    t.reserved |= {LOADER, (LOADER[0] + 1, LOADER[1]), (LOADER[0], LOADER[1] + 1)}
    lost = t.plan_ladders()
    # часы на южном и западном фасадах (Y 84…88), мачта на кровле
    for face in ('s', 'w'):
        for u in range(-3, 4):
            for v in range(-3, 4):
                d = math.hypot(u, v)
                hand = (u == 0 and 0 <= v <= 2) or (v == 0 and 0 <= u <= 1)
                if 1.9 <= d <= 2.9 or hand:
                    y = 86 + v
                    c = (-616 + u, y, z1) if face == 's' else (x0, y, 1878 + u)
                    if y % 4 == 2: continue                       # не трогать перекрытия
                    t.put(*c, 'concrete:15' if hand else 'quartz_block')
    for y in range(91, 98): t.put(-616, y, 1878, 'iron_bars')
    t.put(-616, 98, 1878, LAMP)
    D.update(t.cells)
    tg = t.level_targets()
    P.rooms.update({k: v for k, v in tg.items()})
    # свет/цели: все этажи (кроме комнат) — по клеткам этажей
    cells = []
    for k_ in range(t.storeys()):
        y = t.ys[k_]
        for (x, z) in t.walk_fp(k_):
            if all((x + a, z + b) in t.walk_fp(k_) for a, b in N4) and D.get((x, y + 1, z), 'air') == 'air' \
                    and D.get((x, y, z), '').split(':')[0] not in ('ladder', 'iron_trapdoor') and D.get((x, y + 2, z), 'air') == 'air':
                cells.append((x, y + 1, z))
    P.targets['Диспетчерская'] = cells
    busy = t.reserved | t.res_k.get(0, set()) | set(t.ladders) | {(sx, sz)}
    P.lamp_c[NAMES[1]].extend((x, TOP, z) for (x, y, z) in cells if y == TOP + 1 and (x, z) not in busy
                              and D.get((x, TOP + 1, z)) == 'air')
    P.tower = t
    P.tower_lost = lost
    P.halls['Диспетчерская: место загрузчика'] = (LOADER[0], TOP + 1, LOADER[1])


def build_sub(P):
    o = obj('sub'); rect = o[2:6]; x0, x1, z0, z1 = rect
    pil = pil_fn(rect, 4)
    wf = lambda x, y, z: 'concrete:7' if pil(x, z) or y <= TOP + 1 else \
        ('glass_pane' if windows(x, z, y, 4, 69, 72, rect, phase=2) else 'concrete:8')
    b = build_box(P, P.B, 'sub', 75, 'concrete:7', 'concrete:7', wf, [(-600, z1, 3)],
                  ((-606, -604, 1874, 1876), (-603, 1875, 2), (-606, 1874, (-1, 0))), NAMES[1], 'concrete:8')
    # лестница в техгалерею под Промышленным: марш 6 ступеней на юг, проём в полу над первыми пятью
    xs = range(STAIR_X[0], STAIR_X[1] + 1)
    for i, z in enumerate(range(1875, 1881)):
        top_ = TOP - i                               # 66 … 61: ступени, ходим 67 … 62
        for x in xs:
            b.put(x, top_, z, 'stone_brick_stairs:3')
            for y in range(top_ - 1, GY0, -1): b.put(x, y, z, 'stonebrick')
            for y in range(top_ + 1, top_ + 5):
                if y <= TOP: b.put(x, y, z, 'air')
            b.res.add((x, z))
        for x in (STAIR_X[0] - 1, STAIR_X[1] + 1):
            for y in range(top_, TOP): b.put(x, y, z, 'stonebrick')
    for z in range(1875, 1880):                      # ограждение проёма (кроме входа с севера)
        for x in (STAIR_X[0] - 1, STAIR_X[1] + 1): b.put(x, TOP + 1, z, 'iron_bars'); b.res.add((x, z))
    for x in range(STAIR_X[0] - 1, STAIR_X[1] + 2): b.put(x, TOP + 1, 1880, 'iron_bars')
    for z in range(1881, 1886):                      # тоннель до галереи (пол 60, ноги 61, свод 64)
        for x in xs:
            b.put(x, GY0, z, 'stonebrick')
            for y in range(GY0 + 1, GY1): b.put(x, y, z, 'air')
            b.put(x, GY1, z, 'stonebrick')
        for x in (STAIR_X[0] - 1, STAIR_X[1] + 1):
            for y in range(GY0, GY1 + 1): b.put(x, y, z, 'stonebrick')
    for x in xs: b.put(x, TOP, 1880, 'stonebrick')   # свод над нижней ступенью (просвет 4: 62…65)
    b.walls_in |= {(x, z) for x in range(STAIR_X[0] - 1, STAIR_X[1] + 2) for z in range(1875, 1881)}
    wall_lamps(b, pil, 72, skip={(-600, z1)})
    b.floor_targets()
    P.targets['лестница в галерею'] = [(x, float(TOP - i), z) for i, z in enumerate(range(1875, 1881)) for x in xs] + \
        [(x, GY0 + 1, z) for z in range(1881, 1886) for x in xs]
    P.lamp_c[NAMES[1]].extend((x, GY1, z) for z in range(1881, 1886) for x in xs)
    P.stair_cells = {(x, z) for x in xs for z in range(1875, 1881)}


def build_saw(P, k, doors, room):
    D = P.B
    o = obj(k); x0, x1, z0, z1 = o[2:6]
    R = 77
    rect = (x0, x1, z0, z1)

    def T(x):
        kk = (x - (x0 + 1)) % 5
        return {0: 81, 1: 80, 2: 79, 3: 78, 4: R}[kk], kk
    pil = lambda x, z: (x in (x0, x1) and z in (z0, z1)) or (z in (z0, z1) and (x - x0) % 5 == 1) or (x in (x0, x1) and (z - z0) % 5 == 0)

    def wall_fn(x, y, z):
        if pil(x, z) or y <= TOP + 1: return 'stonebrick'
        if windows(x, z, y, 5, 69, 74, rect, phase=3) or windows(x, z, y, 5, 69, 74, rect, phase=4) or \
                (x in (x0, x1) and windows(x, z, y, 5, 69, 74, rect, phase=2)): return 'glass_pane'
        return 'brick_block'
    b = B(P, D, o[1], rect, R, 'stonebrick', 'brick_block', NAMES[1])
    b.box(wall_fn)
    last = None
    for x in range(x0 + 1, x1):
        t, kk = T(x)
        last = t
        for z in range(z0, z1 + 1):
            edge = z in (z0, z1)
            if kk == 4: continue
            for y in range(R, t + 1):
                if edge: b.put(x, y, z, 'brick_block'); continue
                if kk == 0: b.put(x, y, z, 'air' if y == R else ('glass_pane' if y < t else 'brick_block'))
                else: b.put(x, y, z, 'brick_stairs:1' if y == t else 'air')
    for z in range(z0, z1 + 1):
        for x in (x0, x1): b.put(x, R + 1, z, 'stone_slab:5')
    if last and last > R + 1:                       # восточный торец — до последней ступени
        for z in range(z0, z1 + 1):
            for y in range(R + 1, last): b.put(x1, y, z, 'brick_block')
            b.put(x1, last, z, 'stone_slab:5')
    for x in range(x0, x1 + 1):
        if T(x)[1] == 4 or x in (x0, x1):
            for z in (z0, z1):
                if b.D.get((x, R + 1, z)) is None: b.put(x, R + 1, z, 'stone_slab:5')
    for (x, z, m) in doors: b.door(x, z, m)
    b.room('щитовая', *room, 'stonebrick')
    wall_lamps(b, pil, 72, skip={(d[0], d[1]) for d in doors})
    b.floor_targets()
    P.halls[o[1]] = ((x0 + x1) // 2, TOP + 1, (z0 + z1) // 2)
    return b


def build_matter(P):
    o = obj('matter'); rect = o[2:6]; x0, x1, z0, z1 = rect
    pil = pil_fn(rect, 4)
    wf = lambda x, y, z: 'quartz_block:2' if pil(x, z) else ('quartz_block' if y <= TOP + 1 or y >= 76 else
                                                             ('stained_glass_pane:10' if windows(x, z, y, 4, 69, 74, rect, phase=2) else 'quartz_block'))
    b = build_box(P, P.B, 'matter', 79, 'quartz_block', 'quartz_block', wf, [(-600, z0, 1)],
                  ((-606, -604, 1866, 1868), (-603, 1867, 2), (-606, 1868, (-1, 0))), NAMES[1], 'quartz_block')
    cx, cz, r = -600.5, 1864.0, 4.5
    for x in range(-606, -594):
        for z in range(1859, 1870):
            for y in range(79, 85):
                d = math.sqrt((x - cx) ** 2 + (z - cz) ** 2 + (y - 79) ** 2)
                if d <= r:
                    inner = d <= r - 1.1
                    b.put(x, y, z, 'air' if inner else ('quartz_block' if y == 79 else 'stained_glass:10'))
    wall_lamps(b, pil, 72, skip={(-600, z0)})
    b.floor_targets()


def build_turb(P):
    o = obj('turb'); rect = o[2:6]; x0, x1, z0, z1 = rect
    pil = pil_fn(rect, 5)
    wf = lambda x, y, z: 'concrete:7' if pil(x, z) or y <= TOP + 1 else \
        ('glass_pane' if windows(x, z, y, 5, 70, 78, rect, phase=2) or windows(x, z, y, 5, 70, 78, rect, phase=3) else 'concrete:8')
    b = build_box(P, P.B, 'turb', 81, 'concrete:7', 'concrete:7', wf, [(x1, 1900, 2)],
                  ((-639, -637, 1895, 1897), (-636, 1896, 2), (-639, 1895, (-1, 0))), NAMES[1], 'concrete:8')
    wall_lamps(b, pil, 74, skip={(x1, 1900)})
    b.floor_targets()


def build_pump(P):
    o = obj('pump'); rect = o[2:6]; x0, x1, z0, z1 = rect
    pil = pil_fn(rect, 4)
    wf = lambda x, y, z: 'stonebrick' if pil(x, z) or y <= TOP + 1 else \
        ('glass_pane' if windows(x, z, y, 4, 69, 71, rect, phase=2) else 'concrete:8')
    b = build_box(P, P.B, 'pump', 74, 'stonebrick', 'concrete:7', wf, [(-650, z0, 1)],
                  ((-655, -653, 1895, 1897), (-652, 1896, 2), (-655, 1895, (-1, 0))), NAMES[1], 'concrete:8')
    basin = rc(-650, -647, 1900, 1901)
    for (x, z) in basin:
        b.put(x, TOP, z, 'water'); b.put(x, TOP - 1, z, 'water'); b.put(x, TOP - 2, z, 'stone')
        for a, c in N4:
            n = (x + a, z + c)
            if n not in basin: b.put(n[0], TOP - 1, n[1], 'stonebrick')
        b.walls_in.add((x, z))
    b.basin = basin
    wall_lamps(b, pil, 71, skip={(-650, z0)})
    b.floor_targets()


# ============================================================================== green
def build_greenhouse(P):
    D = P.E
    o = obj('gh'); x0, x1, z0, z1 = o[2:6]
    WT = 71
    zc = (z0 + z1) / 2; half = (z1 - z0) / 2
    Hz = {z: WT + max(0, round(5.5 * math.sqrt(max(0.0, 1 - ((z - zc) / (half + 0.5)) ** 2)))) for z in range(z0, z1 + 1)}
    rect = (x0, x1, z0, z1)
    rib = lambda x: (x - x0) % 5 == 0
    frame = lambda x, z, y: (x in (x0, x1) and z in (z0, z1)) or y in (TOP + 1, WT) or \
        (z in (z0, z1) and rib(x)) or (x in (x0, x1) and (z - z0) % 4 == 0)
    b = B(P, D, o[1], rect, WT, 'quartz_block', 'glass', NAMES[2])
    b.box(lambda x, y, z: 'quartz_block' if frame(x, z, y) else 'glass_pane')
    for y in range(TOP + 1, TOP + 4):                # рама двери из полных блоков
        for x in (-645, -643): b.put(x, y, z1, 'quartz_block')
    b.put(-644, TOP + 3, z1, 'quartz_block')
    for z in range(z0, z1 + 1):
        h = Hz[z]
        for x in range(x0, x1 + 1):
            end = x in (x0, x1)
            for y in range(WT, h):
                if end: b.put(x, y, z, 'quartz_block' if (z in (z0, z1) or (z - z0) % 4 == 0) else 'glass_pane')
                elif z in (z0, z1): b.put(x, y, z, 'quartz_block' if rib(x) else 'glass_pane')
                else: b.put(x, y, z, 'air')
            b.put(x, h, z, 'quartz_block' if (rib(x) or end) else 'glass')
    # грядки: пашня с поливочными канавками; главный проход Z 1835…1837 и X −645…−643, служебные — 1 бл.
    beds, water, aisle = set(), set(), set()
    for (x, z) in b.inner:
        if 1835 <= z <= 1837 or -645 <= x <= -643:
            aisle.add((x, z)); continue
        u = (x - (x0 + 1)) % 6
        if u == 5: aisle.add((x, z)); continue
        if u == 2: water.add((x, z))
        else: beds.add((x, z))
    room = (-655, -653, 1827, 1829)
    for (x, z) in beds | water:
        if room[0] - 1 <= x <= room[1] + 1 and room[2] - 1 <= z <= room[3] + 1: continue
        if (x, z) in water: b.put(x, TOP, z, 'water'); b.put(x, TOP - 1, z, 'stone')
        else: b.put(x, TOP, z, 'farmland:7')
        b.walls_in.add((x, z))
    b.door(-644, z1, 3)
    b.room('щитовая', room, (-652, 1828, 2), (-655, 1827, (-1, 0)), 'quartz_block')
    for (x, z) in b.ring:
        if (x in (x0, x1) and (z - z0) % 4 == 0 or z in (z0, z1) and rib(x)) and not (x in (x0, x1) and z in (z0, z1)) \
                and (x, z) != (-644, z1):
            b.put(x, 69, z, LAMP)
    b.floor_targets()
    P.lamp_c[NAMES[2]] = [c for c in P.lamp_c[NAMES[2]] if (c[0], c[2]) in aisle]
    P.halls['Оранжерея: главный проход'] = (-644, TOP + 1, 1836)
    P.halls['Оранжерея: служебный проход у восточной стены'] = (-638, TOP + 1, 1830)


def build_wind(P):
    D = P.E
    for zc in WIND_Z:
        x = -597
        for y in range(TOP, 95): D[(x, y, zc)] = 'concrete:0'
        for xx in range(-598, -595): D[(xx, 95, zc)] = 'concrete:0'          # гондола по оси X
        D[(-596, 95, zc)] = 'concrete:8'
        for ang in (90, 210, 330):                                           # лопасти в плоскости X −598
            for r in (1, 2, 3):
                z = round(zc + r * math.cos(math.radians(ang)))
                y = round(95 + r * math.sin(math.radians(ang)))
                if (z, y) != (zc, 95): D[(-599, y, z)] = 'concrete:0'
        D[(-599, 95, zc)] = 'concrete:8'
        P.halls[f'ветряк Z {zc}, у мачты'] = (-598, TOP + 1, zc)


# ============================================================================== main
def main():
    a = parse_args()
    W = World(built_before(NAMES[0]))
    P = Plan(W)
    P.B, P.E = {}, {}
    P.paved = {}
    P.lamp_c = {NAMES[0]: [], NAMES[1]: [], NAMES[2]: []}
    build_ground(P)
    build_dispatch(P)
    build_sub(P)
    build_saw(P, 'craft', [(-615, 1859, 1)], ((-619, -617, 1866, 1868), (-616, 1867, 2), (-619, 1868, (-1, 0))))
    build_matter(P)
    build_turb(P)
    build_pump(P)
    build_greenhouse(P)
    build_wind(P)
    exist = {n: [k for k, b in D.items() if b == LAMP] for n, D in zip(NAMES, (P.G, P.B, P.E))}
    exist[NAMES[1]] += P.W and [k for k, b in P.W.pre.items() if b == LAMP and -660 <= k[0] <= -590 and 1820 <= k[2] <= 1936]
    tg = lambda ns: [t for n in ns for t in P.targets[n]]
    f1 = lambda ts: [(x, math.floor(h), z) for (x, h, z) in ts]
    P.lamps = {}
    P.lamps[NAMES[0]] = place_lamps(P, P.G, P.lamp_c[NAMES[0]], f1(tg(['техгалереи', 'цех булыжника', 'подходы этапа 2'])), exist[NAMES[1]])
    b_names = [obj(k)[1] for k in ('sub', 'craft', 'matter', 'turb', 'pump')] + ['лестница в галерею', 'Диспетчерская']
    P.lamps[NAMES[1]] = place_lamps(P, P.B, P.lamp_c[NAMES[1]] + [k for k, v in P.B.items() if v == 'concrete:0' and k[1] in (70, 74, 78, 82, 86)
                                                                  and False], f1(tg(b_names)), exist[NAMES[1]] + exist[NAMES[0]] + P.lamps[NAMES[0]])
    P.lamps[NAMES[2]] = place_lamps(P, P.E, P.lamp_c[NAMES[2]], f1(tg([obj('gh')[1]])), exist[NAMES[2]])
    outs = {}
    for nm, D in zip(NAMES, (P.G, P.B, P.E)):
        os.makedirs(a.outdir, exist_ok=True)
        o, rel, order, dims = save_schema(dict(D), os.path.join(a.outdir, nm))
        outs[nm] = (o, rel, order)
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(D)}')
    checks(W, P, outs, a)


def checks(W, P, outs, a):
    T = P.T
    print('== ПРОВЕРКИ ==')

    def base(x, y, z):
        b = T.block(x, y, z)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
    prevs = {NAMES[0]: {}, NAMES[1]: dict(P.G), NAMES[2]: {**P.G, **P.B}}
    for nm, D in zip(NAMES, (P.G, P.B, P.E)):
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
    ALL = {**P.G, **P.B, **P.E}

    def fin_of(cells):
        def f(x, y, z):
            b = cells.get((x, y, z))
            if b is None: b = base(x, y, z)
            return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        return f
    final = fin_of(ALL)
    wo = [k for k, b in ALL.items() if b == 'water' and any(final(k[0] + a_, k[1] + b_, k[2] + c_) in ('air',)
                                                          for a_, b_, c_ in ((1, 0, 0), (-1, 0, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))]
    print(f'вода, открытая в воздух (сбоку или снизу): {len(wo)}', wo[:3])
    # пустоты, открытые в постройку (воздух/вода/лава съёмки рядом с воздухом схемы)
    opened = []
    for k, b in ALL.items():
        if b != 'air' or k[1] > 60: continue
        for a_, b_, c_ in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (k[0] + a_, k[1] + b_, k[2] + c_)
            if n not in ALL and base(*n) in ('air', 'water', 'lava'): opened.append(n)
    print(f'протечки (пустоты каньона, открытые в цех и лаз): {len(opened)}', opened[:3])
    hit = [k for k, b in ALL.items() if k in W.pre and W.pre[k] != b and (k[0], k[2]) not in (LAZ, CAB)
           and W.pre[k] not in ('air', 'grass', 'dirt', 'stone') and not (W.pre[k] in (ROAD, 'stone_slab', 'stonebrick') and k[1] < TOP)]
    print('задеты построенные (кроме мощения над галереями, газона под подходами и люков лаза в полу склада):', len(hit), hit[:4])
    # проходимость
    box = ((-664, -588), (1816, 1940), (58, 100))
    s0 = dl.walk_reachable(final, (-624, 65.0, 1820), *box)
    tgts = {}
    for (x, y, z, m) in P.doors:
        dx, dz = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}[m]
        tgts[f'перед дверью ({x}, {z})'] = (x + dx, 67.0, z + dz)
    for k, c in {**P.halls, **P.rooms}.items(): tgts[k] = (c[0], float(c[1]), c[2])
    for i, (x0, x1, z0, z1) in enumerate(GAL):
        tgts[f'техгалерея {["Заводская", "Промышленный", "Береговой"][i]}: конец'] = ((x0 + x1) // 2 if i == 0 else x0 + 1, 61.0, z0 + 1 if i == 0 else (z0 + z1) // 2)
        if i == 0: tgts['техгалерея Заводская: юг'] = (-624, 61.0, 1918)
    bad = 0
    for k, t in tgts.items():
        ok = dl.reached(s0, *t); bad += 0 if ok else 1
        print(f'  маршрут тротуар проспекта → {k}: {ok}')
    # цех булыжника — от низа лаза; лаз непрерывен
    s1 = dl.walk_reachable(final, (LAZ[0], float(CF + 1), LAZ[1] + 1), (COB[0] - 1, COB[1] + 1), (COB[2] - 1, COB[3] + 1), (CF, CC))
    for k, t in {'цех булыжника: дальний угол': (COB[0], CF + 1.0, COB[3]), 'цех булыжника: у лаза': (LAZ[0], CF + 1.0, LAZ[1])}.items():
        ok = dl.reached(s1, *t); bad += 0 if ok else 1
        print(f'  маршрут низ лаза → {k}: {ok}')
    lz_ok = all(final(LAZ[0], y, LAZ[1]).startswith('ladder') for y in range(CF + 1, TOP)) and \
        all(final(LAZ[0], y, LAZ[1] - 1) not in ('air', 'water', 'lava') for y in range(CF + 1, TOP)) and final(LAZ[0], TOP, LAZ[1]) == 'trapdoor:8'
    print('  проходимость: лаз из склада в цех булыжника непрерывен (стремянка Y 15…65 на сплошной стене, люк):', lz_ok)
    bad += 0 if lz_ok else 1
    print(f'  проходимость: стремянки диспетчерской — недостижимых частей этажей {P.tower_lost}')
    bad += P.tower_lost
    print('ИТОГО недостижимых точек:', bad)
    gaps = [c for c, h in P.paved.items() if not dl.reached(s0, c[0], h, c[1])]
    print('разрывов дорожки', len(gaps), gaps[:4])
    di = door_approach_issues(final, P.doors)
    print(f'подходы к наружным дверям: {len(P.doors)}, ошибок {len(di)}', di[:3])
    # ширина: галереи (поперёк), лестница подстанции, проходы оранжереи
    narrow = []
    for (x0, x1, z0, z1) in GAL:
        if x1 - x0 < z1 - z0:
            for z in range(z0, z1 + 1):
                if sum(1 for x in range(x0, x1 + 1) if final(x, 62, z) == 'air') < 3: narrow.append(('гал', z))
        else:
            for x in range(x0, x1 + 1):
                if sum(1 for z in range(z0, z1 + 1) if final(x, 62, z) == 'air') < 3: narrow.append(('гал', x))
    for z in range(1875, 1886):
        if len(STAIR_X) and STAIR_X[1] - STAIR_X[0] + 1 < 3: narrow.append(('лестница', z))
    print(f'узких рядов (уже 3 бл.): {len(narrow)}', narrow[:4])
    lamps = [k for k, b in ALL.items() if b == LAMP] + [k for k, b in W.pre.items() if b == LAMP]
    tl = [(x, math.floor(h), z) for g, ts in P.targets.items() for (x, h, z) in ts]
    dark = [t for t in tl if not any(man(l, t) <= 7 for l in lamps)]
    print(f'клетки без света (фонарь дальше 7 бл. по сумме осей, свет меньше 8): {len(dark)}', dark[:5],
          f'| фонарей: ground {len(P.lamps[NAMES[0]])}, build {len(P.lamps[NAMES[1]])}, green {len(P.lamps[NAMES[2]])}')
    # загрузчик, цех булыжника = чанк, корпуса в 25 чанках
    lx, lz = LOADER
    free = all(final(lx, y, lz) == 'air' for y in (TOP + 1, TOP + 2)) and final(lx, TOP, lz) not in ('air',)
    cen = (lx >> 4, lz >> 4) == PI.LOADER_CHUNK and lx == PI.LOADER_CHUNK[0] * 16 + 7 and lz == PI.LOADER_CHUNK[1] * 16 + 7
    print(f'загрузчик ({lx}, 67, {lz}): место свободно {free}, центр чанка (−39, 117) {cen} — в одном чанке — ошибок {0 if free and cen else 1}')
    cob_cells = {(x, z) for x in range(COB[0], COB[1] + 1) for z in range(COB[2], COB[3] + 1) if final(x, CF + 2, z) in ('air', 'ladder:3')}
    cob_ch = {(x >> 4, z >> 4) for x, z in cob_cells}
    print(f'цех булыжника: {len(cob_cells)} кл. внутри, чанки {sorted(cob_ch)}, высота {CC - CF - 1} — в одном чанке — ошибок '
          f'{0 if len(cob_cells) == 256 and cob_ch == {(CX, CZ)} and CC - CF - 1 >= 5 else 1}')
    outside = sorted({(x >> 4, z >> 4) for (x, y, z) in {**P.B, **P.E} if (x >> 4, z >> 4) not in PI.LOADER})
    print(f'вне района (корпуса вне 25 чанков): {len(outside)}', outside[:4])
    # негативы
    box_neg = box
    neg = dict(ALL)
    for x in STAIR_X and range(STAIR_X[0], STAIR_X[1] + 1):
        for y in range(GY0 + 1, GY1): neg[(x, y, 1883)] = 'stonebrick'
    sN = dl.walk_reachable(fin_of(neg), (-624, 65.0, 1820), *box_neg)
    print('НЕГАТИВ: тоннель подстанции заложен — техгалерея недостижима:', not dl.reached(sN, -624, 61.0, 1918))
    neg = dict(ALL); neg[(LAZ[0], 40, LAZ[1])] = 'air'
    ok2 = all(fin_of(neg)(LAZ[0], y, LAZ[1]).startswith('ladder') for y in range(CF + 1, TOP))
    print('НЕГАТИВ: разрыв стремянки в лазе — найдено:', not ok2)
    neg = dict(ALL); neg[(lx, TOP + 1, lz)] = 'ladder:2'
    print('НЕГАТИВ: на месте загрузчика стремянка — найдено:', fin_of(neg)(lx, TOP + 1, lz) != 'air')
    some = P.lamps[NAMES[0]][0]
    dk = [t for t in tl if not any(man(l, t) <= 7 for l in lamps if l != some)]
    print('НЕГАТИВ: убран фонарь в галерее — тёмные клетки найдены:', len(dk) > 0)
    hole = next(((COB[0] - 1, y, z) for z in range(COB[2], COB[3] + 1) for y in range(CF + 1, CC)
                 if base(COB[0] - 2, y, z) in ('air', 'water', 'lava')), None) or \
        next(((x, y, COB[3] + 1) for x in range(COB[0], COB[1] + 1) for y in range(CF + 1, CC)
              if base(x, y, COB[3] + 2) in ('air', 'water', 'lava')), (COB[0] - 1, CF + 2, COB[2]))
    neg = dict(ALL); neg[hole] = 'air'
    op = [1 for k, b in neg.items() if b == 'air' and k[1] <= 60 and any(
        (k[0] + a_, k[1] + b_, k[2] + c_) not in neg and base(k[0] + a_, k[1] + b_, k[2] + c_) in ('air', 'water', 'lava')
        for a_, b_, c_ in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))]
    print('НЕГАТИВ: дыра в стене цеха булыжника — протечка найдена:', len(op) > len(opened))
    if a.preview: preview(a.preview, final, W, P, ALL)


def preview(path, final, W, P, ALL):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    X0, X1, Z0, Z1, S = -666, -586, 1814, 1942, 6
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    S2 = 5
    secs = [('Разрез по X −597 (север → юг): ветряки, Береговой с галереей, лаборатория материи, подстанция с лестницей в галерею, АЭС',
             [(-597, z) for z in range(1820, 1936)], (56, 104)),
            ('Разрез по Z 1877 (запад → восток): производственный цех, Заводская с галереей, диспетчерская, подстанция',
             [(x, 1877) for x in range(-660, -590)], (56, 104)),
            ('Разрез по X −615 (север → юг), глубина: склад, лаз, цех булыжника (Y 14…20), Береговой',
             [(-615, z) for z in range(1826, 1860)] + [(-610, z) for z in range(1836, 1846)], (12, 80))]
    sw = max(len(c) for _, c, _ in secs) * S2
    sh = sum((y1 - y0 + 1) * S2 + 34 for _, _, (y0, y1) in secs)
    img = Image.new('RGB', (max(mw + 50, sw + 60), mh + 40 + sh + 20), (250, 250, 247)); dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            c = None
            for y in range(110, 50, -1):
                if not (W.inside(x, z) or P.T._i(x, z) is not None): break
                b = final(x, y, z)
                if b in ('air', 'plant') or b.endswith('pressure_plate') or 'door' in b: continue
                nat = (x, y, z) not in ALL and (x, y, z) not in W.pre
                if b == 'water': c = (120, 170, 225)
                elif nat and b in ('stone', 'ground'): c = (150, 175, 110)
                elif b == 'grass': c = (125, 175, 95)
                elif b in ('glass', 'stained_glass:3'): c = (180, 215, 235)
                else: c = col(b)
                k = max(0, min(1, (y - 60) / 50))
                c = tuple(min(255, int(v * (0.75 + 0.35 * k))) for v in c)
                break
            if c is None: c = (225, 225, 225)
            dr.rectangle([25 + (x - X0) * S, 25 + (z - Z0) * S, 25 + (x - X0 + 1) * S - 1, 25 + (z - Z0 + 1) * S - 1], fill=c)
    for x in range(X0, X1 + 1):
        if x % 16 == 0: dr.line([25 + (x - X0) * S, 25, 25 + (x - X0) * S, 25 + mh], fill=(60, 60, 60), width=1)
    for z in range(Z0, Z1 + 1):
        if z % 16 == 0: dr.line([25, 25 + (z - Z0) * S, 25 + mw, 25 + (z - Z0) * S], fill=(60, 60, 60), width=1)
    dr.text((25, 6), 'Промзона, этап 2: вид сверху (этапы 1+2) и разрезы; оранжевый контур — цех булыжника (Y 14…20)', fill='black', font=F(12))
    dr.rectangle([25 + (COB[0] - X0) * S, 25 + (COB[2] - Z0) * S, 25 + (COB[1] + 1 - X0) * S, 25 + (COB[3] + 1 - Z0) * S], outline=(230, 120, 0), width=2)
    oy = mh + 40
    for title, cols_, (y0, y1) in secs:
        dr.text((25, oy), title, fill='black', font=F(11)); oy += 16
        for u, (x, z) in enumerate(cols_):
            for y in range(y0, y1 + 1):
                if not (W.inside(x, z) or P.T._i(x, z) is not None): continue
                b = final(x, y, z)
                if b in ('air', 'plant'): continue
                c = (120, 170, 225) if b == 'water' else (230, 100, 20) if b == 'lava' else \
                    (150, 135, 105) if b in ('stone', 'ground') and (x, y, z) not in ALL and (x, y, z) not in W.pre else col(b)
                yy = oy + (y1 - y) * S2
                dr.rectangle([25 + u * S2, yy, 25 + (u + 1) * S2 - 1, yy + S2 - 1], fill=c)
        oy += (y1 - y0 + 1) * S2 + 18
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
