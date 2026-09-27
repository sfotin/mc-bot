"""Мыс, этапы 2-5 одной схемой (CITY.md §7.2): дорога мыса с фонарями,
мостовая и парапет площади маяка, смотровая «Закат» с дорожкой, яхт-клуб
(2 этажа, электрощитовая, кабельная шахта, ниши под зарядные плиты),
марина (причал и 3 пальца), маяк с лестницей и галереей, выгнутый мост на
остров A (настил из полублоков, подъём 1/2 блока на блок).

Запуск:
    gen_cape_2_5.py [--out schemas/cape-2-5-build.json]
                    [--preview docs/districts/cape-2-5-preview.png]

Модель мира: рельеф docs/terrain/site.json + построенные схемы набережной
и этапа 1 мыса. Строится ПОВЕРХ них, запуск без --prepare.
Порядок слоёв (BOT.md §12): 1) массивы (подсыпки, стенки, настилы, стены),
2) полости, 3) восстановление полостей, задетых соседями, 4) детали.
Проверки: проходимость (BFS игрока 2 блока, двери и стремянки проходимы),
опоры + вода + порядок постройки (decor_lib по реальному порядку бота),
кровля каньона под шахтой.
"""
import argparse
import json
import math
import os
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
         ('embankment-4-ferris-wheel.json', (-685, 62, 1862)),
         ('cape-1-earthworks.json', (-778, 56, 1874)))
LAMP = [(0, 'quartz_block:1'), (1, 'dark_oak_fence'), (2, 'dark_oak_fence'), (3, 'sea_lantern'), (4, 'stone_slab:7')]  # DECOR §3.2а

# геометрия (CITY.md §7.2)
RX = range(-771, -766)                      # дорога мыса
RZ0, RZ1 = 1860, 1883
PX0, PX1, PZ0, PZ1 = -775, -763, 1884, 1892  # площадь маяка (стенка по периметру - этап 1)
LX, LZ = -771, 1888                          # маяк
BX0, BX1 = -768, -764                        # мост: бортики -768 и -764, проход -767..-765
BZ0, BZ1 = 1893, 1903
CX0, CX1, CZ0, CZ1 = -764, -755, 1869, 1877  # яхт-клуб
VX0, VX1, VZ0, VZ1 = -792, -786, 1861, 1867  # смотровая «Закат»
PATHZ = (1864, 1865)                         # дорожка к смотровой


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default=os.path.join(REPO, 'docs', 'terrain', 'site.json'))
    p.add_argument('--caves', default=os.path.join(REPO, 'docs', 'terrain', 'caves.json'))
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'cape-2-5-build.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'cape-2-5-preview.png'))
    return p.parse_args()


def half(T, full, slab):
    """Поверхность высотой T (шаг 0.5): (y, блок) - полный блок под целой T, нижний полублок под T+.5."""
    if T == int(T): return int(T) - 1, full
    return int(math.floor(T)), slab


def main():
    args = parse_args()
    d = json.load(open(args.site))
    W, X0, Z0 = d['w'], d['x0'], d['z0']
    cv = json.load(open(args.caves))

    def G(x, z): return d['ground'][(z - Z0) * W + x - X0]

    def WA(x, z): return d['water'][(z - Z0) * W + x - X0]

    def T(x, z): return d['top'][(z - Z0) * W + x - X0]

    def cave_top(x, z):
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

    def surf(x, z):
        for y in range(100, 30, -1):
            if SOLID(world(x, y, z)): return y

    cells = {}
    AIRZ = []  # отложенные полости (слой 2)

    def put(x, y, z, b): cells[(x, y, z)] = b

    def fill_under(x, y, z, b='stone'):  # подсыпка под блок до грунта
        for yy in range(surf(x, z) + 1, y): put(x, yy, z, b)

    def clear_above(x, y, z, h=3):  # воздух над поверхностью (срез грунта, трава)
        for yy in range(y + 1, max(y + h, surf(x, z)) + 1): AIRZ.append((x, yy, z))

    # ================= 1. МАССИВЫ =================
    # --- дорога мыса: от аллеи (верх 65) подъём 1/2 на блок до 68, по хребту ровно, спуск к площади (верх 65)
    def road_T(z): return min(65 + 0.5 * (z - 1859), 68.0, 65 + 0.5 * (1884 - z))
    ROAD = {}
    for z in range(RZ0, RZ1 + 1):
        t = road_T(z)
        for x in RX:
            mid = x in (-770, -769, -768)
            y, b = half(t, 'double_stone_slab:8' if x == -769 else ('sandstone:2' if mid else 'double_stone_slab:9'),
                        'stone_slab:0' if x == -769 else 'stone_slab:1')
            fill_under(x, y, z, 'stone'); put(x, y, z, b); ROAD[(x, z)] = (y, t)
            clear_above(x, y, z)
        for x in (-772, -766):  # обочины: подпорная стенка в выемке (до грунта), бортик на насыпи (до верха дороги)
            g = surf(x, z); top = math.ceil(t)
            rng = range(top - 1, g + 1) if g >= top else range(g + 1, top)
            for yy in rng: put(x, yy, z, 'stonebrick')
    # --- мостовая площади маяка (Y 64): гладкий песчаник, кольцо плит вокруг маяка, ось дороги
    for x in range(PX0 + 1, PX1):
        for z in range(PZ0, PZ1):
            r2 = (x - LX) ** 2 + (z - LZ) ** 2
            b = 'double_stone_slab:8' if 12 < r2 <= 20 or x == -769 and z <= 1885 else 'double_stone_slab:9'
            put(x, 64, z, b)
    # --- мост: бортики - полные блоки, проход - полублоки
    def bridge_T(z): return min(65 + 0.5 * (z - 1892), 64 + 0.5 * (1902 - z), 67.0) if z <= 1902 else 64.0
    BRIDGE = {}
    for z in range(BZ0, BZ1 + 1):
        t = bridge_T(z)
        for x in range(BX0, BX1 + 1):
            if x in (BX0, BX1):
                y = math.ceil(t) - 1; b = 'stonebrick'
            else:
                y, b = half(t, 'sandstone:2', 'stone_slab:1')
            put(x, y, z, b); BRIDGE[(x, z)] = (y, t)
            if z in (BZ0, 1901, 1902, 1903):  # опоры на концах - от дна/грунта
                for yy in range(surf(x, z) + 1, y): put(x, yy, z, 'stonebrick')
            elif z in (1894, 1900) and x in (BX0, BX1):  # пяты арки
                for yy in range(63, y): put(x, yy, z, 'stonebrick')
    # --- смотровая «Закат»: площадка Y 63 (верх 64), парапет с запада
    for x in range(VX0, VX1 + 1):
        for z in range(VZ0, VZ1 + 1):
            edge = x == VX0 or z in (VZ0, VZ1)
            fill_under(x, 63, z, 'stonebrick' if edge else 'stone')
            put(x, 63, z, 'stonebrick' if edge else ('double_stone_slab:8' if (x + z) % 4 == 0 else 'double_stone_slab:9'))
            clear_above(x, 63, z)
    # --- дорожка к смотровой: по грунту, на ступеньке в 1 блок - полублок посередине
    PATH = {}
    for x in range(VX1 + 1, -772):
        for z in PATHZ:
            g = surf(x, z); PATH[(x, z)] = g
    for (x, z), g in PATH.items():
        put(x, g, z, 'sandstone:2'); clear_above(x, g, z)
        if PATH.get((x + 1, z), g) == g + 1 or PATH.get((x - 1, z), g) == g + 1:
            put(x, g + 1, z, 'stone_slab:1')
    # --- яхт-клуб: пол 1 эт. Y 64, стены 65..67, перекрытие Y 68, 2 эт. 69..71, крыша Y 72, парапет Y 73
    for x in range(CX0, CX1 + 1):
        for z in range(CZ0, CZ1 + 1):
            fill_under(x, 64, z, 'stone'); put(x, 64, z, 'double_stone_slab:9')
            wall = x in (CX0, CX1) or z in (CZ0, CZ1)
            corner = x in (CX0, CX1) and z in (CZ0, CZ1)
            for y in range(65, 72):
                if y == 68: put(x, y, z, 'quartz_block' if wall else 'double_stone_slab:9')
                elif wall: put(x, y, z, 'quartz_block:2' if corner else 'concrete:0')
            put(x, 72, z, 'quartz_block' if wall else 'double_stone_slab:9')
            if wall: put(x, 73, z, 'quartz_block')
    # терраса к марине: X -754..-752, пол Y 64
    for x in range(-754, -751):
        for z in range(CZ0, CZ1 + 1):
            fill_under(x, 64, z, 'stone'); put(x, 64, z, 'sandstone:2' if x != -752 else 'stonebrick'); clear_above(x, 64, z, 4)
    # площадка у входа с дороги (2 эт.): X -765, Z 1872..1874 - полублок Y 68
    for z in (1872, 1873, 1874):
        fill_under(-765, 68, z, 'stone'); put(-765, 68, z, 'stone_slab:1'); clear_above(-765, 68, z)
    # --- марина: причал Z 1878..1879 (X -757..-739) и пальцы X -753/-748/-743 по Z 1880..1890, настил Y 63
    PONT = [(x, z) for x in range(-757, -738) for z in (1878, 1879)] + [(x, z) for x in (-753, -748, -743) for z in range(1880, 1891)]
    for x, z in PONT:
        put(x, 63, z, 'planks:1'); clear_above(x, 63, z)
    # --- маяк: башня Ø5 (Y 65..88), галерея Y 89, фонарная Y 90..92, крыша Y 93..96
    def r2(x, z): return (x - LX) ** 2 + (z - LZ) ** 2
    DISC = [(x, z) for x in range(LX - 5, LX + 6) for z in range(LZ - 5, LZ + 6)]
    RING = [(x, z) for x, z in DISC if 2 < r2(x, z) <= 6.5]
    INNER = [(x, z) for x, z in DISC if r2(x, z) <= 2]
    WALK = [(x, z) for x, z in DISC if 6.5 < r2(x, z) <= 13.5]
    RAIL = [(x, z) for x, z in DISC if 13.5 < r2(x, z) <= 20.5]
    for x, z in RING:
        for y in range(65, 89): put(x, y, z, 'quartz_block')
    for x, z in RING + INNER + WALK + RAIL: put(x, 89, z, 'quartz_block')
    for x, z in WALK: put(x, 88, z, 'stone_slab:15')  # карниз под галереей
    for x, z in RING:
        for y in (90, 91, 92): put(x, y, z, 'glass')
    for x, z in RING + INNER: put(x, 93, z, 'stained_hardened_clay:14')
    for x, z in INNER: put(x, 94, z, 'stained_hardened_clay:14')
    put(LX, 95, LZ, 'stained_hardened_clay:14'); put(LX, 96, LZ, 'iron_bars')

    # ================= 2. ПОЛОСТИ =================
    for k in AIRZ:
        if k not in cells: put(*k, 'air')
    for x, z in INNER:  # ствол маяка
        for y in range(65, 89): put(x, y, z, 'air')
        for y in (90, 91, 92): put(x, y, z, 'air')
    for x in range(CX0 + 1, CX1):  # помещения клуба
        for z in range(CZ0 + 1, CZ1):
            for y in (65, 66, 67, 69, 70, 71): put(x, y, z, 'air')
    for x in range(PX0 + 1, PX1):  # над площадью
        for z in range(PZ0, PZ1):
            if (x, z) not in RING + INNER:
                for y in (65, 66, 67): put(x, y, z, 'air')
    for (x, z), (y, t) in BRIDGE.items():  # над мостом
        for yy in range(y + 1, y + 4):
            if (x, yy, z) not in cells or cells[(x, yy, z)] == 'air': put(x, yy, z, 'air')

    # ================= 3. ВОССТАНОВЛЕНИЕ (после полостей) =================
    # лестница клуба между этажами: ступени X -757..-760 у северной стены, проём в перекрытии
    for i, x in enumerate((-757, -758, -759, -760)):
        put(x, 65 + i, 1870, 'quartz_stairs:1')  # подъём на запад, верхняя ступень - в уровне перекрытия
    put(-758, 68, 1870, 'air'); put(-759, 68, 1870, 'air')  # проём в перекрытии над 2-й и 3-й ступенью
    # электрощитовая 1 эт.: X -763..-761, Z 1874..1876, перегородки по X -760 и Z 1873, дверь с севера
    for z in (1874, 1875, 1876):
        for y in (65, 66, 67): put(-760, y, z, 'concrete:0')
    for x in (-763, -762, -761):
        for y in (65, 66, 67): put(x, y, 1873, 'concrete:0')
    # кабельная шахта 1x1 в углу щитовой: X -763, Z 1876, от Y 61 до перекрытия 2 эт., ревизионные люки в полах
    SH = (-763, 1876)
    shaft_bot = 61
    ct = cave_top(*SH)
    for y in range(shaft_bot, 64): put(SH[0], y, SH[1], 'air')

    # ================= 4. ДЕТАЛИ =================
    put(SH[0], 64, SH[1], 'iron_trapdoor'); put(SH[0], 68, SH[1], 'iron_trapdoor')  # люки (закрыты, нижняя половина)
    put(-762, 65, 1873, 'wooden_door:3'); put(-762, 66, 1873, 'wooden_door:8')        # дверь щитовой (на север)
    put(CX1, 65, 1873, 'wooden_door:0'); put(CX1, 66, 1873, 'wooden_door:8')          # вход 1 эт. с террасы (восток)
    put(CX0, 69, 1873, 'wooden_door:2'); put(CX0, 70, 1873, 'wooden_door:8')          # вход 2 эт. с дороги (запад)
    put(-756, 64, 1873, 'air'); put(-763, 68, 1873, 'air')  # ниши под зарядные плиты сразу за дверями (углубление в полу на 1 блок)
    for z in range(CZ0 + 1, CZ1):  # окна: восток - на марину, юг
        if z != 1873:
            for y in (66, 67, 69, 70): put(CX1, y, z, 'glass_pane')
    for x in range(CX0 + 1, CX1):
        if x not in (-763, -762, -761):
            for y in (66, 67): put(x, y, CZ1, 'glass_pane')
        for y in (69, 70): put(x, y, CZ1, 'glass_pane')
    for z in (1871, 1875):
        for y in (69, 70): put(CX0, y, z, 'glass_pane')
    for x, z in ((-758, 1874), (-761, 1871), (-758, 1872)): put(x, 68, z, 'sea_lantern')  # свет в потолке 1 эт.
    for x, z in ((-761, 1872), (-758, 1875)): put(x, 72, z, 'sea_lantern')                # и 2 эт.
    put(-762, 67, 1875, 'air'); put(-762, 68, 1875, 'sea_lantern')                        # свет в щитовой
    # мебель: 1 эт. - диван лицом к окнам на восток, столик; 2 эт. - обеденный стол DECOR §2.1 со стульями
    put(-759, 65, 1874, 'trapdoor:4'); put(-759, 65, 1875, 'spruce_stairs:1'); put(-759, 65, 1876, 'trapdoor:5')
    put(-757, 65, 1875, 'fence'); put(-757, 66, 1875, 'wooden_pressure_plate')
    for x in (-762, -761, -760):
        put(x, 69, 1874, 'spruce_stairs:5' if x == -762 else 'spruce_stairs:4' if x == -760 else 'wooden_slab:9')
        put(x, 69, 1875, 'spruce_stairs:5' if x == -762 else 'spruce_stairs:4' if x == -760 else 'wooden_slab:9')
    for x in (-762, -761, -760):
        put(x, 69, 1876, 'spruce_stairs:2')
    for x in (-762, -760): put(x, 69, 1873, 'spruce_stairs:3')
    # перила у проёма лестницы на 2 эт.
    for x in (-757, -758, -759): put(x, 69, 1871, 'dark_oak_fence')
    put(-757, 69, 1870, 'dark_oak_fence')
    # тент над террасой: шерсть полосами на Y 68, стойки из забора
    for x in range(-754, -751):
        for z in range(CZ0, CZ1 + 1): put(x, 68, z, 'wool:11' if z % 2 else 'wool:0')
    for z in range(CZ0, CZ1 + 1):  # ограждение террасы с востока, стойки тента через 4
        for y in ((65, 66, 67) if z in (CZ0, 1873, CZ1) else (65,)): put(-752, y, z, 'dark_oak_fence')
    # фонари: дорога, площадь, мост, смотровая, причал
    LAMPS = [(-772, 1868), (-766, 1868), (-772, 1876), (-766, 1876),
             (PX0, PZ0), (PX1, PZ0), (BX0 - 1, PZ1), (BX1 + 1, PZ1),
             (BX0, 1903), (BX1, 1903), (VX0, VZ0), (VX0, VZ1), (-739, 1879), (-753, 1890), (-743, 1890)]
    def top_of(x, z):
        for y in range(80, 30, -1):
            b = cells.get((x, y, z)) or world(x, y, z)
            if SOLID(b): return y
    for x, z in LAMPS:
        t0 = top_of(x, z)
        for dy, b in LAMP: put(x, t0 + 1 + dy, z, b)
    # парапет площади: кварц на стенке, проёмы - дорога (север, не стенка) и мост
    for x in range(PX0, PX1 + 1):
        for z in range(PZ0, PZ1 + 1):
            if (x in (PX0, PX1) or z == PZ1) and not (BX0 <= x <= BX1 and z == PZ1) and (x, 65, z) not in cells:
                put(x, 65, z, 'quartz_block')
    # скамейки на площади: лицом на восток (бухта, марина) и на запад (закат)
    for i, z in enumerate(range(1885, 1889)): put(-764, 65, z, ('trapdoor:4', 'birch_stairs:1', 'birch_stairs:1', 'trapdoor:5')[i])
    for i, z in enumerate(range(1885, 1889)):
        if (-774, z) not in RING: put(-774, 65, z, ('trapdoor:4', 'birch_stairs:0', 'birch_stairs:0', 'trapdoor:5')[i])
    # маяк: дверь на восток, стремянка внутри до галереи, окна, свет, выход на галерею, перила
    put(LX + 2, 65, LZ, 'wooden_door:0'); put(LX + 2, 66, LZ, 'wooden_door:8')
    for y in range(65, 90): put(LX, y, LZ - 1, 'ladder:3')
    for y in (71, 78, 85): put(LX, y, LZ + 2, 'glass_pane'); put(LX - 2, y, LZ, 'glass_pane')
    for y in (68, 74, 80, 86): put(LX - 2, y, LZ - 1, 'sea_lantern')
    put(LX, 90, LZ, 'sea_lantern'); put(LX, 91, LZ, 'sea_lantern'); put(LX, 92, LZ, 'glowstone')
    put(LX, 90, LZ + 2, 'air'); put(LX, 91, LZ + 2, 'air')
    for x, z in RAIL: put(x, 90, z, 'iron_bars')
    # мост: перила - забор на бортиках, кварцевые столбы на концах
    for (x, z), (y, t) in BRIDGE.items():
        if x in (BX0, BX1) and z <= 1902:
            put(x, y + 1, z, 'quartz_block:2' if z in (BZ0, 1902) else 'dark_oak_fence')
    # смотровая: парапет с запада, скамейка лицом на запад, кашпо
    for z in range(VZ0 + 1, VZ1): put(VX0, 64, z, 'quartz_block')
    for i, z in enumerate(range(1862, 1866)): put(VX0 + 1, 64, z, ('trapdoor:4', 'birch_stairs:0', 'birch_stairs:0', 'trapdoor:5')[i])
    for x, z in ((VX1, VZ0), (VX1, VZ1)): put(x, 64, z, 'hardened_clay'); put(x, 65, z, 'leaves:4')
    # аллея: скамейка на входе дороги мыса убирается (X -770..-767, Z 1859)
    for x in range(-770, -766): put(x, 65, 1859, 'air')

    # ================= выход =================
    for k in [k for k, b in cells.items() if b == 'air' and world(*k) in ('air',)]: del cells[k]  # лишний воздух
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, 'габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, 'записей', len(cells))
    print(Counter(cells.values()).most_common(25))
    print('кабельная шахта: низ Y', shaft_bot, '| кровля каньона под ней:', ct)

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

    PASS = {'air', 'carpet', 'tripwire', 'wooden_door', 'ladder'}

    def nm(b): return b.split(':')[0]

    def free(x, y, z): return nm(final(x, y, z)) in PASS

    def stand(x, y, z):
        below = final(x, y - 1, z)
        onground = SOLID(below) and nm(below) not in PASS
        return free(x, y, z) and free(x, y + 1, z) and (onground or nm(final(x, y, z)) == 'ladder' or nm(below) == 'ladder')

    start = (-769, 65, 1856); seen = {start}; q = deque([start])
    while q:
        x, y, z = q.popleft()
        moves = [(a, dy, c) for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)) for dy in (0, -1, 1)]
        if nm(final(x, y, z)) == 'ladder' or nm(final(x, y - 1, z)) == 'ladder': moves += [(0, 1, 0), (0, -1, 0)]
        for a, dy, c in moves:
            n = (x + a, y + dy, z + c)
            if n in seen or not (-800 <= n[0] <= -735 and 1850 <= n[2] <= 1906 and 60 <= n[1] <= 95): continue
            if dy == 1 and a == 0 and c == 0: pass
            elif dy == 1 and not free(x, y + 2, z): continue
            if stand(*n): seen.add(n); q.append(n)
    TARGETS = {'дорога, хребет': (-769, 68, 1870), 'площадь маяка': (-766, 65, 1886), 'маяк внутри': (-771, 65, 1888),
               'галерея маяка': (LX + 3, 90, LZ), 'мост, середина': (-766, 67, 1896), 'остров A': (-766, 64, 1905),
               'смотровая «Закат»': (-789, 64, 1864), 'клуб 2 эт.': (-761, 69, 1872), 'клуб 1 эт.': (-758, 65, 1873),
               'щитовая': (-762, 65, 1875), 'терраса': (-753, 65, 1872), 'причал': (-745, 64, 1879), 'палец марины': (-748, 64, 1889)}
    bad = {k: v for k, v in TARGETS.items() if v not in seen}
    print('ПРОХОДИМОСТЬ: контрольных точек', len(TARGETS), 'недостижимо', len(bad), bad)
    # мост: ни одной ступеньки выше 1/2 блока по проходу
    steps = [bridge_T(z + 1) - bridge_T(z) for z in range(BZ0 - 1, BZ1)]
    print('МОСТ: профиль верха', [bridge_T(z) for z in range(BZ0 - 1, BZ1 + 1)], 'макс. перепад', max(abs(s) for s in steps),
          '| просвет над водой в середине', min(BRIDGE[(-766, z)][0] for z in range(1895, 1898)) - 63, 'блока')
    print('ДОРОГА: профиль верха', [road_T(z) for z in range(RZ0 - 1, RZ1 + 2)])

    if args.preview:
        preview(args.preview, final)


def preview(path, final):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    font = ImageFont.truetype(fp, 13) if fp else ImageFont.load_default()
    COL = {'water': (70, 120, 200), 'sand': (219, 207, 163), 'ground': (110, 150, 70), 'stonebrick': (122, 122, 122),
           'sandstone': (222, 212, 170), 'double_stone_slab': (205, 200, 180), 'stone_slab': (205, 200, 180), 'stone': (125, 125, 125),
           'quartz_block': (242, 240, 235), 'concrete': (232, 234, 235), 'planks': (115, 85, 50), 'dark_oak_fence': (60, 40, 20),
           'sea_lantern': (170, 225, 225), 'glass': (190, 225, 235), 'glass_pane': (190, 225, 235), 'stained_hardened_clay': (160, 50, 40),
           'iron_bars': (90, 90, 95), 'leaves': (60, 130, 50), 'log': (90, 70, 40), 'hardened_clay': (150, 90, 65),
           'wool': (240, 240, 240), 'glowstone': (250, 220, 120), 'birch_stairs': (200, 185, 130), 'quartz_stairs': (242, 240, 235)}

    def col(b):
        n, _, m = b.partition(':')
        if n == 'wool' and m == '11': return (50, 70, 170)
        return COL.get(n, (150, 140, 110) if n == 'ground' else (200, 150, 200))

    def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)
    S = 9
    X0, X1, Z0, Z1 = -797, -735, 1850, 1906
    mw, mh = (X1 - X0 + 1) * S, (Z1 - Z0 + 1) * S
    eh = (98 - 58) * S
    img = Image.new('RGB', (mw + 20 + mw, max(mh, eh * 2 + 30) + 40), 'white')
    dr = ImageDraw.Draw(img)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 100
            while y > 30 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z); c = col(b)
            if b == 'water':
                yb = y
                while yb > 30 and final(x, yb, z) == 'water': yb -= 1
                c = shade(c, 1 - min(y - yb, 15) / 30)
            else: c = shade(c, 0.72 + 0.012 * (y - 60))
            dr.rectangle([(x - X0) * S, 20 + (z - Z0) * S, (x - X0 + 1) * S - 1, 20 + (z - Z0 + 1) * S - 1], fill=c)
    dr.text((4, 2), 'вид сверху, X −797…−735, Z 1850…1906 (север вверху)', fill='black', font=font)
    bx = mw + 20
    SKY = (200, 225, 245)

    def elev(y0, label, rays):
        dr.rectangle([bx, y0, bx + len(rays) * S - 1, y0 + eh - 1], fill=SKY)
        for u, ray in enumerate(rays):
            for y in range(58, 98):
                for i, (x, z) in enumerate(ray):
                    b = final(x, y, z)
                    if b != 'air':
                        yy = y0 + (97 - y) * S
                        dr.rectangle([bx + u * S, yy, bx + (u + 1) * S - 1, yy + S - 1], fill=shade(col(b), 1 - min(i, 20) / 45))
                        break
        dr.text((bx + 4, y0 - 16), label, fill='black', font=font)
    elev(20, 'вид с юга (с моря): X −797…−735', [[(x, z) for z in range(1906, 1850, -1)] for x in range(X0, X1 + 1)])
    elev(40 + eh, 'вид с запада: Z 1850…1906 (юг справа)', [[(x, z) for x in range(-800, -730)] for z in range(Z0, Z1 + 1)])
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
