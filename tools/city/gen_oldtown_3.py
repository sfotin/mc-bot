"""Старый город, этап 3: Ратушная площадь и ратуша с часовой башней (CITY.md §7.3).

Квартал X −687…−661, Z 1819…1835 (между проспектами С–Ю и главным, Ратушной ул.
и восточной границей района) целиком:
- площадь X −687…−673: пол Y 65 (верх блока Y 64), к улицам — полублоками
  (перепад соседей <= 0.5); узор — каменный кирпич, диагонали полированного
  диорита и кольца андезита вокруг колонны; колонна (кварц, золотая «фигура»)
  на оси входа в ратушу Z 1827; скамейки DECOR §3.3 лицом к ратуше, урны,
  фонари DECOR §3.2в у входа;
- ратуша X −672…−662, Z 1821…1833: 2 этажа (пол Y 65 и Y 70), 1-й этаж —
  каменный кирпич, 2-й — белый бетон, пояс и карниз — кварц, кровля —
  двускатная из кирпичных ступенек (конёк по Z); вход с площади в основании
  башни; лестница в зал 2-го этажа; электрощитовая (СЗ угол, 3×3) и кабельная
  шахта 1×1 от Y 60 с люками iron_trapdoor:8 в полах (CITY.md §6);
- часовая башня 5×5 X −672…−668, Z 1825…1829: циферблаты на 4 стороны
  (Y 84…86), звонница Y 88…90, шатёр и шпиль до Y 97, стремянка внутри от
  1-го этажа до звонницы;
- кольцо мощения вокруг ратуши, обочина за восточной границей — откосом.

v2 (после постройки v1): витражи (stained_glass_pane) в окнах 2-го этажа, над
входом и в башне; нажимные плиты у дверей изнутри (каменный пол — каменные,
CITY.md §6); правка владельца — проём из башни на чердак (USER_EDITS).
Исправление к построенному v1: --fix-from schemas/oldtown-3-townhall.json
--fix-out schemas/oldtown-3-fix-1.json (только отличия, без зон USER_EDITS).

Запуск: gen_oldtown_3.py [--out schemas/oldtown-3-townhall.json]
                         [--preview docs/districts/oldtown-3-preview.png]
                         [--fix-from <построенная v1> --fix-out <fix>]
Мир — World(built_before('oldtown-3-townhall.json')).
Проверки: опоры + вода + порядок, проходимость (площадь от всех улиц, ратуша,
2-й этаж, щитовая, звонница), скамейки (место для ног), перепад мощения <= 0.5,
кровля каньона, резерв трасс, негативные прогоны.
"""
import argparse
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from world_model import World, REPO, built_before  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'tools', 'decor'))
import decor_lib as dl  # noqa: E402

BX0, BX1, BZ0, BZ1 = -687, -661, 1819, 1835        # квартал этапа
SQ_X1 = -673                                        # площадь X −687…−673
TX0, TX1, TZ0, TZ1 = -672, -662, 1821, 1833         # ратуша (стены)
KX0, KX1, KZ0, KZ1 = -672, -668, 1825, 1829         # башня (стены)
AXZ = 1827                                          # ось входа
F = 64                                              # блок пола 1-го этажа (верх 65)
F2 = 69                                             # перекрытие 1-2 этажа (верх 70)
CEIL = 74                                           # потолок 2-го этажа
COL = (-681, AXZ)                                   # колонна
SHAFT = (-671, 1822)                                # кабельная шахта (угол щитовой)
SHAFT_BOT = 60
LADDER = (-671, 1826)
ROOF_MIN = 3
RESERVE_Y = 60
LAMP_PARTS = ('quartz_block:1', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-3-townhall.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-3-preview.png'))
    p.add_argument('--fix-from', help='построенная схема (v1) — для исправляющей схемы')
    p.add_argument('--fix-out', help='куда записать исправляющую схему')
    return p.parse_args()


# правки владельца на месте (как построено): проём башня → чердак в восточной стене башни
USER_EDITS = {(KX1, 75, AXZ): 'air', (KX1, 76, AXZ): 'air'}
# витражи: цвет по высоте окна (снизу вверх) — красный, жёлтый, синий; над входом — оранжевый/жёлтый/синий
STAINED = {70: 'stained_glass_pane:14', 71: 'stained_glass_pane:4', 72: 'stained_glass_pane:11'}


def street_top(W, x, z):
    """Верх покрытия построенной улицы (без фонарей) или None."""
    y = W.surf(x, z)
    b = W.block(x, y, z)
    while b in LAMP_PARTS: y -= 1; b = W.block(x, y, z)
    if b in ('ground', 'grass') or b.startswith('water'): return None
    return y + (0.5 if b.startswith('stone_slab') and ':' not in b[10:] or b in ('stone_slab', 'stone_slab:3', 'stone_slab:5') else 1.0)


def in_th(x, z): return TX0 <= x <= TX1 and TZ0 <= z <= TZ1


def paving_heights(W):
    """Высота мощения квартала: по умолчанию 65, конусы (0.5 на клетку) от улиц и от двери."""
    cells = [(x, z) for x in range(BX0, BX1 + 1) for z in range(BZ0, BZ1 + 1) if not in_th(x, z)]
    anchors = {}
    for x in range(BX0 - 1, BX1 + 2):
        for z in range(BZ0 - 1, BZ1 + 2):
            if (x, z) in cells or in_th(x, z): continue
            if not (BX0 - 1 <= x <= BX1 and BZ0 - 1 <= z <= BZ1 + 1): continue   # восток — не улица
            t = street_top(W, x, z)
            if t is not None: anchors[(x, z)] = t
    anchors[(TX0, AXZ)] = 65.0                      # порог двери
    H = {}
    for c in cells:
        lo = max(a - 0.5 * (abs(c[0] - p[0]) + abs(c[1] - p[1])) for p, a in anchors.items())
        hi = min(a + 0.5 * (abs(c[0] - p[0]) + abs(c[1] - p[1])) for p, a in anchors.items())
        H[c] = min(max(65.0, lo), hi)
    return H, anchors


def build(W):
    cells = {}

    def put(x, y, z, b): cells[(x, y, z)] = b

    H, anchors = paving_heights(W)

    def plant_top(x, z):
        y = W.surf(x, z) + 1
        while W.block(x, y, z) == 'plant': y += 1
        return y - 1

    # узор площади
    def pave_mat(x, z):
        if x > SQ_X1 or x < BX0 or not (BZ0 <= z <= BZ1) or z == BZ1:
            return 'double_stone_slab', 'stone_slab'                      # кольцо у ратуши, полоса у Ратушной ул.
        dx, dz = x - COL[0], z - COL[1]
        r = max(abs(dx), abs(dz))
        if r in (2, 6): return 'stone:6', 'stone_slab:5'                   # кольца андезита
        if abs(dx) == abs(dz) and r > 2: return 'stone:4', 'stone_slab:5'  # диагонали диорита
        if dz == 0 and r > 2: return 'stone:4', 'stone_slab:5'             # ось на вход
        return 'stonebrick', 'stone_slab:5'

    # ================= 1. МАССИВЫ =================
    for (x, z), h in H.items():
        g = W.surf(x, z)
        full, slab = pave_mat(x, z)
        if h == int(h):
            ty = int(h) - 1
            for y in range(g + 1, ty): put(x, y, z, 'stone')
            put(x, ty, z, full); top = ty
        else:
            k = int(h)
            for y in range(g + 1, k - 1): put(x, y, z, 'stone')
            put(x, k - 1, z, full); put(x, k, z, slab); top = k
        for y in range(top + 1, max(plant_top(x, z), g) + 1): put(x, y, z, 'air')
    # ратуша: фундамент и пол
    for x in range(TX0, TX1 + 1):
        for z in range(TZ0, TZ1 + 1):
            g = W.surf(x, z)
            for y in range(g + 1, F): put(x, y, z, 'stone')
            inner = TX0 < x < TX1 and TZ0 < z < TZ1
            put(x, F, z, ('quartz_block' if (x + z) % 2 else 'stone:6') if inner else 'stonebrick')
            put(x, F - 1, z, 'stonebrick')
            for y in range(F + 1, max(plant_top(x, z), g) + 1): put(x, y, z, 'air')
    # стены
    for x in range(TX0, TX1 + 1):
        for z in range(TZ0, TZ1 + 1):
            if not (x in (TX0, TX1) or z in (TZ0, TZ1)): continue
            for y in range(F + 1, CEIL + 1):
                if y <= F2 - 1: b = 'stonebrick'
                elif y == F2: b = 'quartz_block'
                elif y == CEIL: b = 'quartz_block'
                else: b = 'quartz_block:2' if (x in (TX0, TX1) and z in (TZ0, TZ1)) else 'concrete:0'
                put(x, y, z, b)
    # перекрытие 2-го этажа и потолок
    for x in range(TX0 + 1, TX1):
        for z in range(TZ0 + 1, TZ1):
            put(x, F2, z, 'stonebrick'); put(x, CEIL, z, 'stonebrick')
    # башня: стены от фундамента до карниза звонницы
    for x in range(KX0, KX1 + 1):
        for z in range(KZ0, KZ1 + 1):
            edge = x in (KX0, KX1) or z in (KZ0, KZ1)
            if edge:
                for y in range(F + 1, 88):
                    corner = x in (KX0, KX1) and z in (KZ0, KZ1)
                    put(x, y, z, 'quartz_block:2' if corner and CEIL < y < 87 else 'quartz_block' if y == 87 else 'stonebrick')
            else:
                put(x, 87, z, 'stonebrick')                          # пол звонницы
    # перегородка щитовой X −668, Z 1822…1824
    for z in range(1822, 1825):
        for y in range(F + 1, F2): put(-668, y, z, 'stonebrick')
    # кровля: скаты по X (ступеньки), конёк X −667, фронтоны Z 1821/1833
    for i in range(6):
        for z in range(TZ0, TZ1 + 1):
            for x, meta in ((TX0 - 1 + i, 0), (TX1 + 1 - i, 1)):
                if KX0 - 1 <= x <= KX1 and KZ0 <= z <= KZ1: continue   # башня и свес перед ней
                put(x, CEIL + 1 + i, z, f'brick_stairs:{meta}')
    for z in range(TZ0, TZ1 + 1):
        put(-667, CEIL + 6, z, 'brick_block'); put(-667, CEIL + 7, z, 'stone_slab:4')
    for z in (TZ0, TZ1):
        for x in range(TX0, TX1 + 1):
            h = min(x - (TX0 - 1), (TX1 + 1) - x)          # ряд ската над этой X
            for y in range(CEIL + 1, CEIL + 1 + h): put(x, y, z, 'concrete:0')
    # верх башни: звонница, шатёр, шпиль
    for x in range(KX0, KX1 + 1):
        for z in range(KZ0, KZ1 + 1):
            corner = x in (KX0, KX1) and z in (KZ0, KZ1)
            for y in (88, 89, 90):
                if corner: put(x, y, z, 'quartz_block:2')
            put(x, 91, z, 'stonebrick')
    for lvl, (a0, a1, b0, b1) in enumerate(((KX0, KX1, KZ0, KZ1), (KX0 + 1, KX1 - 1, KZ0 + 1, KZ1 - 1))):
        y = 92 + lvl
        for x in range(a0, a1 + 1):
            for z in range(b0, b1 + 1):
                if z == b0: m = 2
                elif z == b1: m = 3
                elif x == a0: m = 0
                elif x == a1: m = 1
                else: put(x, y, z, 'brick_block'); continue
                put(x, y, z, f'brick_stairs:{m}')
    put(-670, 94, AXZ, 'brick_block'); put(-670, 95, AXZ, 'quartz_block:2')
    put(-670, 96, AXZ, 'iron_bars'); put(-670, 97, AXZ, 'iron_bars')
    # колонна на площади
    cx, cz = COL
    fy = 65
    for x in range(cx - 1, cx + 2):
        for z in range(cz - 1, cz + 2):
            put(x, fy, z, 'sea_lantern' if (x != cx and z != cz) else 'stonebrick:3')
    put(cx, fy + 1, cz, 'quartz_block:1')
    for y in range(fy + 2, fy + 7): put(cx, y, cz, 'quartz_block:2')
    put(cx, fy + 7, cz, 'quartz_block:1'); put(cx, fy + 8, cz, 'gold_block')

    # ================= 2. ПОЛОСТИ =================
    for x in range(TX0 + 1, TX1):
        for z in range(TZ0 + 1, TZ1):
            tower_wall = (x in (KX0, KX1) or z in (KZ0, KZ1)) and KX0 <= x <= KX1 and KZ0 <= z <= KZ1
            part = x == -668 and 1822 <= z <= 1824
            if tower_wall: continue
            for y in list(range(F + 1, F2)) + list(range(F2 + 1, CEIL)):
                if part and y < F2: continue
                put(x, y, z, 'air')
    for x in range(KX0 + 1, KX1):                              # шахта башни над потолком
        for z in range(KZ0 + 1, KZ1):
            for y in range(CEIL + 1, 87): put(x, y, z, 'air')
            for y in (88, 89, 90): put(x, y, z, 'air')
    for x in range(KX0, KX1 + 1):                              # проёмы звонницы
        for z in range(KZ0, KZ1 + 1):
            if (x in (KX0, KX1) or z in (KZ0, KZ1)) and not (x in (KX0, KX1) and z in (KZ0, KZ1)):
                for y in (89, 90): put(x, y, z, 'air')
    # проёмы: башня → зал (1-й и 2-й этаж), вход
    for z in range(KZ0 + 1, KZ1):
        for y in (F + 1, F + 2, F + 3): put(KX1, y, z, 'air')
        for y in (F2 + 1, F2 + 2, F2 + 3): put(KX1, y, z, 'air')
    # проём лестницы в перекрытии (над ступенями 1…4) и кабельная шахта
    STAIR = [(z, F + 1 + i) for i, z in enumerate(range(1826, 1831))]   # (Z, Y) ступеней, X −664…−663
    for z, y in STAIR[:4]:
        for x in (-664, -663): put(x, F2, z, 'air')
    for y in range(SHAFT_BOT, F): put(SHAFT[0], y, SHAFT[1], 'air')
    for x in range(SHAFT[0] - 1, SHAFT[0] + 2):                 # обкладка шахты ниже пола
        for z in range(SHAFT[1] - 1, SHAFT[1] + 2):
            if (x, z) != SHAFT:
                for y in range(SHAFT_BOT - 1, F):
                    if (x, y, z) not in cells or cells[(x, y, z)] == 'air': put(x, y, z, 'stonebrick')
    put(SHAFT[0], SHAFT_BOT - 1, SHAFT[1], 'stonebrick')

    # ================= 3/4. ДЕТАЛИ =================
    for z, y in STAIR:
        for x in (-664, -663): put(x, y, z, 'stone_brick_stairs:2')           # подъём на юг
    for z in range(1826, 1830): put(-665, F2 + 1, z, 'dark_oak_fence')        # перила проёма
    for x in (-665, -664, -663): put(x, F2 + 1, 1825, 'dark_oak_fence')
    put(SHAFT[0], F, SHAFT[1], 'iron_trapdoor:8'); put(SHAFT[0], F2, SHAFT[1], 'iron_trapdoor:8')
    for y in range(F + 1, 88): put(LADDER[0], y, LADDER[1], 'ladder:3')      # стремянка у северной стены башни
    # двери: вход (на запад, в основании башни), щитовая
    put(TX0, F + 1, AXZ, 'dark_oak_door:0'); put(TX0, F + 2, AXZ, 'dark_oak_door:8')
    put(TX0, F + 3, AXZ, 'quartz_block:1')
    for z in (AXZ - 1, AXZ + 1):
        for y in (F + 1, F + 2): put(TX0, y, z, 'quartz_block:2')
        put(TX0, F + 3, z, 'quartz_block:1')
    put(-668, F + 1, 1823, 'wooden_door:2'); put(-668, F + 2, 1823, 'wooden_door:8')
    # окна
    def win(x, z, ys):
        for y in ys: put(x, y, z, STAINED.get(y, 'glass_pane') if y > F2 else 'glass_pane')
    for z in (1823, 1831): win(TX0, z, (F + 2, F + 3)); win(TX0, z, (F2 + 1, F2 + 2, F2 + 3))
    for z in (1823, 1825, 1827, 1829, 1831): win(TX1, z, (F + 2, F + 3)); win(TX1, z, (F2 + 1, F2 + 2, F2 + 3))
    for x in (-666, -664): win(x, TZ0, (F + 2, F + 3))
    for x in (-670, -666, -664): win(x, TZ0, (F2 + 1, F2 + 2, F2 + 3))
    for x in (-670, -666, -664): win(x, TZ1, (F + 2, F + 3)); win(x, TZ1, (F2 + 1, F2 + 2, F2 + 3))
    for y, c in zip((F2 + 1, F2 + 2, F2 + 3), (1, 4, 11)): put(TX0, y, AXZ, f'stained_glass_pane:{c}')   # над входом
    for y, c in ((78, 11), (81, 14)):
        for xz in ((KX0, AXZ), (-670, KZ1), (-670, KZ0)): put(xz[0], y, xz[1], f'stained_glass_pane:{c}')
    # нажимные плиты у дверей изнутри (пол каменный): вход — внутри вестибюля; щитовая — с обеих сторон
    put(TX0 + 1, F + 1, AXZ, 'stone_pressure_plate')
    put(-669, F + 1, 1823, 'stone_pressure_plate'); put(-667, F + 1, 1823, 'stone_pressure_plate')
    for k, b in USER_EDITS.items(): put(*k, b)
    # циферблаты: 3×3 белый кварц, в центре чёрный бетон
    for y in (84, 85, 86):
        for t in (-1, 0, 1):
            ctr = (y == 85 and t == 0)
            b = 'concrete:15' if ctr else 'quartz_block'
            put(KX0, y, AXZ + t, b); put(KX1, y, AXZ + t, b)
            put(-670 + t, y, KZ0, b); put(-670 + t, y, KZ1, b)
    # звонница: перила в проёмах (кроме клетки над стремянкой не нужно — стремянка внутри), колокол
    for x in range(KX0, KX1 + 1):
        for z in range(KZ0, KZ1 + 1):
            if (x in (KX0, KX1) or z in (KZ0, KZ1)) and not (x in (KX0, KX1) and z in (KZ0, KZ1)):
                put(x, 88, z, 'dark_oak_fence')
    put(-669, 90, 1828, 'dark_oak_fence'); put(-669, 89, 1828, 'gold_block')   # колокол в углу, не на пути
    # свет
    for x, z in ((-666, 1823), (-666, 1831), (-670, 1823), (-670, 1831), (-666, 1827)):
        put(x, F2, z, 'sea_lantern')
    for x, z in ((-666, 1823), (-666, 1827), (-666, 1831), (-670, 1823), (-670, 1831), (-670, AXZ)):
        put(x, CEIL, z, 'sea_lantern')
    put(-670, F2, AXZ, 'sea_lantern')
    for y in (77, 82): put(-669, y, KZ1, 'sea_lantern')
    put(-670, 91, AXZ, 'sea_lantern')
    # стол совета на 2-м этаже: столешница — верхние полублоки ели, стулья — еловые ступеньки
    for x in range(-667, -663):
        put(x, F2 + 1, 1823, 'wooden_slab:9')
        put(x, F2 + 1, 1822, 'spruce_stairs:3'); put(x, F2 + 1, 1824, 'spruce_stairs:2')
    # площадь: скамейки лицом к ратуше (восток), урны, кашпо, Т-фонари у входа
    for z0 in (1821, 1830):
        for i, z in enumerate(range(z0, z0 + 4)):
            put(-685, 65, z, ('trapdoor:4', 'birch_stairs:1', 'birch_stairs:1', 'trapdoor:5')[i])
    for z in (1820, 1834): put(-685, 65, z, 'cauldron')
    for x, z in ((-673, 1822), (-673, 1832)): put(x, 65, z, 'hardened_clay'); put(x, 66, z, 'leaves:4')
    for z in (1824, 1830):   # перекладина по Z
        x = -674
        put(x, 65, z, 'quartz_block:1')
        for y in (66, 67, 68): put(x, y, z, 'dark_oak_fence')
        put(x, 68, z - 1, 'dark_oak_fence'); put(x, 68, z + 1, 'dark_oak_fence')
        put(x, 67, z - 1, 'sea_lantern'); put(x, 67, z + 1, 'sea_lantern')
        put(x, 69, z, 'stone_slab:7')
    # обочина за восточной границей: откос к мощению
    for (x, z), h in list(H.items()):
        if x != BX1: continue
        lvl = int(h) - 1 if h == int(h) else int(h)
        for d, xx in ((1, BX1 + 1), (2, BX1 + 2)):
            g = W.surf(xx, z)
            if g < lvl - d:
                for y in range(g + 1, lvl - d): put(xx, y, z, 'stone')
                put(xx, lvl - d, z, 'grass')
                for y in range(lvl - d + 1, plant_top(xx, z) + 1): put(xx, y, z, 'air')
            elif g > lvl + d:
                for y in range(lvl + d + 1, max(g, plant_top(xx, z)) + 1): put(xx, y, z, 'air')
                put(xx, lvl + d, z, 'grass')
    return cells, H, anchors


def main():
    args = parse_args()
    W = World(built_before('oldtown-3-townhall.json'))
    cells, H, anchors = build(W)
    xs = [k[0] for k in cells]; ys = [k[1] for k in cells]; zs = [k[2] for k in cells]
    ox, oy, oz = min(xs), min(ys), min(zs)
    rel = {(x - ox, y - oy, z - oz): b for (x, y, z), b in cells.items()}
    order = dl.compute_order(rel)
    dl.save(rel, args.out, order)
    print('origin', ox, oy, oz, '| габарит', max(xs) - ox + 1, max(ys) - oy + 1, max(zs) - oz + 1, '| записей', len(cells))
    print('мощение: клеток', len(H), '| высоты', dict(sorted(Counter(H.values()).items())), '| якорей-улиц', len(anchors) - 1)

    def final(x, y, z):
        b = cells.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)

    def terrain_rel(x, y, z):
        b = W.block(x + ox, y + oy, z + oz)
        return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)

    print('== ПРОВЕРКИ ==')
    errs = dl.check_water(rel, terrain_rel)
    se, wr = dl.check_supports(rel, order, terrain_rel)
    print('опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок', len(errs) + len(se), '| предупреждений', len(wr))
    for m in (errs + se + wr)[:10]: print('  ', m)
    be = dl.check_bench_front(rel, terrain_rel)
    print('скамейки (место для ног):', len(be), 'ошибок', be[:3])
    jump = [(c, n) for c in H for n in ((c[0] + 1, c[1]), (c[0], c[1] + 1)) if n in H and abs(H[c] - H[n]) > 0.5]
    edge = [(c, a) for c in H for a in anchors if abs(c[0] - a[0]) + abs(c[1] - a[1]) == 1 and abs(H[c] - anchors[a]) > 0.5]
    print('мощение: перепад соседей > 0.5 —', len(jump), '| со стыком улицы > 0.5 —', len(edge))

    def walk(fin):
        return dl.walk_reachable(fin, (-690, 66, AXZ), (-692, -659), (1814, 1838), (60, 99))
    seen = walk(final)
    targets = {'площадь, колонна (перед)': (-683, 65, AXZ), 'площадь, СВ угол': (-674, 65, 1820),
               'выход на главный пр. (−676,1818)': (-676, 65, 1818), 'выход на Ратушную ул. (−670,1836)': (-670, 65, 1836),
               'восточное кольцо (−661,1827)': (-661, 65, AXZ), 'ратуша: вестибюль': (-670, 65, AXZ),
               'ратуша: зал 1 эт.': (-666, 65, 1831), 'щитовая': (-670, 65, 1823), 'зал 2 эт.': (-667, 70, 1831),
               'комната башни 2 эт.': (-670, 70, AXZ), 'звонница': (-670, 88, AXZ),
               'чердак (через проём владельца)': (-665, 75, AXZ)}
    bad_t = []
    for k, (x, y, z) in targets.items():
        ok = dl.reached(seen, x, y, z); bad_t += [] if ok else [k]
        print(f'  проходимость → {k}: {ok}')
    pav_miss = [c for c in H if not any(sx == c[0] and sz == c[1] for sx, sz, h in seen)
                and all((c[0], y, c[1]) not in cells or cells[(c[0], y, c[1])] in ('air',) for y in range(65, 70))]
    print('  клетки мощения без стоянки (кроме занятых декором):', len(pav_miss), pav_miss[:6])
    # кровля каньона, резерв
    lo = {}
    for (x, y, z) in cells: lo[(x, z)] = min(lo.get((x, z), 999), y)
    roof = min(y - W.cave_top(x, z) - 1 for (x, z), y in lo.items() if W.cave_top(x, z) is not None)
    in_res = lambda x, z: -696 <= x <= -684 or 1812 <= z <= 1820      # резерв трасс (CITY.md §7.3)
    print('кровля каньона под схемой: мин.', roof, '(норма >=', ROOF_MIN, ') | в резерве трасс ниже Y', RESERVE_Y, '—',
          sum(1 for k, b in cells.items() if b != 'air' and k[1] < RESERVE_Y and in_res(k[0], k[2])),
          '| вне резерва ниже Y 60 (дно шахты) —', sum(1 for k, b in cells.items() if b != 'air' and k[1] < RESERVE_Y and not in_res(k[0], k[2])))
    print('шахта: низ Y', SHAFT_BOT, '| кровля каньона под ней', W.cave_top(*SHAFT) and SHAFT_BOT - 1 - W.cave_top(*SHAFT) - 1)
    # негативы
    neg = dict(cells)
    for x in (-664, -663): neg[(x, F + 2, 1827)] = 'stonebrick'; neg[(x, F + 3, 1827)] = 'stonebrick'
    for y in (F + 2, F + 3, F + 4): neg[(LADDER[0], y, LADDER[1])] = 'air'
    s2 = walk(lambda x, y, z: neg.get((x, y, z)) or final(x, y, z))
    print('НЕГАТИВ: лестница перегорожена и стремянка разорвана у 1-го этажа — 2-й этаж недостижим:', not dl.reached(s2, -667, 70, 1831))
    neg = dict(cells); neg[(LADDER[0], 80, LADDER[1])] = 'air'; neg[(LADDER[0], 81, LADDER[1])] = 'air'
    s3 = walk(lambda x, y, z: neg.get((x, y, z)) or final(x, y, z))
    print('НЕГАТИВ: разрыв стремянки — звонница недостижима:', not dl.reached(s3, -670, 88, AXZ))
    neg = dict(cells); neg[(-684, 65, 1822)] = 'stonebrick'; neg[(-684, 65, 1823)] = 'stonebrick'
    rel2 = {(x - ox, y - oy, z - oz): b for (x, y, z), b in neg.items()}
    print('НЕГАТИВ: перед скамейкой блоки — ошибок', len(dl.check_bench_front(rel2, terrain_rel)), '(ждём > 0)')
    if args.fix_from:
        import json
        old = json.load(open(args.fix_from))
        o1 = (-687, 59, 1819)
        oldabs = {(e['x'] + o1[0], e['y'] + o1[1], e['z'] + o1[2]): e['block'] for e in old}
        fix = {k: b for k, b in cells.items() if oldabs.get(k) != b and k not in USER_EDITS}
        gone = [k for k in oldabs if k not in cells]
        print('исправление к v1: блоков', len(fix), dict(Counter(b.split(':')[0] for b in fix.values())), '| пропавших из v1:', len(gone))
        merged = dict(oldabs); merged.update(fix); merged.update(USER_EDITS)
        print('v1 + исправление + правки владельца = v2:', merged == cells)
        if args.fix_out:
            fx = [k[0] for k in fix]; fy = [k[1] for k in fix]; fz = [k[2] for k in fix]
            fo = (min(fx), min(fy), min(fz))
            frel = {(x - fo[0], y - fo[1], z - fo[2]): b for (x, y, z), b in fix.items()}
            forder = dl.compute_order(frel)
            dl.save(frel, args.fix_out, forder)

            def fterr(x, y, z):          # мир для исправления — построенная v1 поверх мира до неё
                k = (x + fo[0], y + fo[1], z + fo[2])
                if k in oldabs: return oldabs[k]
                b = W.block(*k)
                return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
            fe = dl.check_water(frel, fterr); fs, fw = dl.check_supports(frel, forder, fterr)
            print('исправление: origin', *fo, '| записей', len(frel), '| опоры/вода/порядок: ошибок', len(fe) + len(fs), '| предупреждений', len(fw))
    if args.preview: preview(args.preview, final)


def preview(path, final):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F_ = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CL = {'stonebrick': (122, 122, 122), 'stone': (125, 125, 125), 'double_stone_slab': (168, 168, 168),
          'stone_slab': (175, 175, 175), 'quartz_block': (236, 233, 226), 'concrete': (228, 228, 228),
          'brick_stairs': (150, 70, 55), 'brick_block': (140, 65, 50), 'stone_slab:4': (150, 70, 55),
          'glass_pane': (190, 220, 235), 'sea_lantern': (215, 240, 235), 'gold_block': (235, 200, 60),
          'dark_oak_fence': (70, 50, 30), 'dark_oak_door': (70, 50, 30), 'wooden_door': (150, 120, 70),
          'birch_stairs': (210, 195, 140), 'trapdoor': (150, 120, 70), 'hardened_clay': (160, 90, 60),
          'leaves': (70, 130, 50), 'grass': (95, 150, 60), 'cauldron': (60, 60, 60), 'iron_bars': (90, 90, 90),
          'ladder': (160, 125, 80), 'stone_brick_stairs': (122, 122, 122), 'iron_trapdoor': (200, 200, 200),
          'concrete:15': (25, 25, 25), 'stone:4': (225, 225, 225), 'stone:6': (140, 145, 145), 'stone:0': (125, 125, 125),
          'stonebrick:3': (122, 122, 122), 'wooden_slab': (110, 80, 50), 'spruce_stairs': (110, 80, 50)}

    def col(b):
        if b in CL: return CL[b]
        n = b.split(':')[0]
        return CL.get(n, (185, 180, 172))
    S = 11
    X0, X1, Z0, Z1 = -690, -658, 1816, 1838
    img = Image.new('RGB', (1500, 360), 'white'); dr = ImageDraw.Draw(img)
    dr.text((10, 4), 'Этап 3 — сверху (крыши — цвет верхнего блока)', fill='black', font=F_(12))
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            y = 99
            while y > 55 and final(x, y, z) == 'air': y -= 1
            b = final(x, y, z)
            c = col(b) if b not in ('ground',) else (130, 160, 90)
            dr.rectangle([10 + (x - X0) * S, 20 + (z - Z0) * S, 10 + (x - X0 + 1) * S - 1, 20 + (z - Z0 + 1) * S - 1], fill=c)
    # фасады: вид с запада (площадь) — проекция по X, и разрез Z=1827
    def elev(ox_, oy_, label, pts_fn, cols, rows=range(62, 99), S2=8):
        dr.text((ox_, oy_ - 16), label, fill='black', font=F_(12))
        for u, c in enumerate(cols):
            for y in rows:
                b = pts_fn(c, y)
                if b is None: continue
                yy = oy_ + (rows[-1] - y) * S2
                dr.rectangle([ox_ + u * S2, yy, ox_ + (u + 1) * S2 - 1, yy + S2 - 1], fill=col(b))

    def west_view(z, y):
        for x in range(-690, -655):
            b = final(x, y, z)
            if b not in ('air', 'ground'): return b
        return None

    def sec(z):
        return lambda x, y: (None if final(x, y, z) == 'air' else ('ground' if final(x, y, z) == 'stone' and y < 64 else final(x, y, z)))
    elev(400, 40, 'Фасад с площади (Z 1838…1816)', west_view, list(range(1838, 1815, -1)))
    elev(620, 40, 'Разрез Z=1827 (X −690…−658)', sec(AXZ), list(range(-690, -657)))
    elev(920, 40, 'Разрез Z=1828: лестница', sec(1828), list(range(-690, -657)))
    elev(1220, 40, 'Вид с юга (X −690…−658)', lambda x, y: next((final(x, y, z) for z in range(1840, 1815, -1)
                                                              if final(x, y, z) not in ('air', 'ground')), None), list(range(-690, -657)))
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
