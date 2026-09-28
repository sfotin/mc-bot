"""Старый город, этап 5: бар «Таверна» с террасой к морю (CITY.md §7.3).

Квартал X −687…−676, Z 1839…1847 (Ратушная ул., проспект С–Ю, площадь с фонтаном
набережной), пол Y 65:
- таверна X −686…−677, Z 1839…1845: белые стены, угловые столбы из тёмного дуба,
  пояс из досок тёмного дуба, двускатная терракотовая кровля (конёк по X),
  окна к морю с витражной верхней строкой; внутри — стойка бара, за ней место
  под бочки IC2 (ставит игрок, X −685…−683, Z 1840), табуреты; электрощитовая
  3×3 (СВ угол) с кабельной шахтой 1×1 от Y 60, люк iron_trapdoor:8;
- двери: с проспекта (запад) и на террасу (юг); нажимные плиты изнутри
  (пол деревянный — деревянные, CITY.md §6), у щитовой — с обеих сторон;
- терраса Z 1846…1847 (настил из еловых досок) под полосатым тентом, два
  столика с креслами, стык с площадью набережной (Z 1848) вровень.

Запуск: gen_oldtown_5.py [--out schemas/oldtown-5-tavern.json]
                         [--preview docs/districts/oldtown-5-preview.png]
Мир — World(built_before('oldtown-5-tavern.json')).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oldtown_lib import *  # noqa: E402,F403

BX0, BX1, BZ0, BZ1 = -687, -676, 1839, 1847
TX0, TX1, TZ0, TZ1 = -686, -677, 1839, 1845         # таверна (стены)
F = 64
CEIL = 69
EL = (-681, -677, 1839, 1843)                       # щитовая со стенами (внутри X −680…−678, Z 1840…1842)
SHAFT = (-678, 1840)
BARRELS = [(-685, 1840), (-684, 1840), (-683, 1840)]   # место под бочки IC2
TERR = (-686, -677, 1846, 1847)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-5-tavern.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-5-preview.png'))
    return p.parse_args()


def in_bld(x, z): return TX0 <= x <= TX1 and TZ0 <= z <= TZ1


def build(W):
    S = Schema(W); put = S.put
    block = [(x, z) for x in range(BX0, BX1 + 1) for z in range(BZ0, BZ1 + 1) if not in_bld(x, z)]
    terr = {(x, z) for x in range(TERR[0], TERR[1] + 1) for z in range(TERR[2], TERR[3] + 1)}
    H, anchors = paving_heights(W, block)
    S.pave(H, lambda x, z: ('planks:1', 'wooden_slab:1') if (x, z) in terr else ('double_stone_slab', 'stone_slab'))
    # ---------- 1. массивы ----------
    for x in range(TX0, TX1 + 1):
        for z in range(TZ0, TZ1 + 1):
            wall = x in (TX0, TX1) or z in (TZ0, TZ1)
            S.ground_to(x, z, F, 'stonebrick' if wall else 'planks:1')
            put(x, F - 1, z, 'stone')
            if wall:
                corner = x in (TX0, TX1) and z in (TZ0, TZ1)
                for y in range(F + 1, CEIL): put(x, y, z, 'log2:1' if corner else 'concrete:0')
                put(x, CEIL, z, 'planks:5'); put(x, CEIL + 1, z, 'concrete:0')
            else:
                for y in range(F + 1, CEIL): put(x, y, z, 'air')
                put(x, CEIL, z, 'planks:5')
    ex0, ex1, ez0, ez1 = EL
    for x in range(ex0, ex1 + 1):
        for z in range(ez0, ez1 + 1):
            if (x in (ex0, ex1) or z in (ez0, ez1)) and not in_bld(x, z) is False and not (x in (TX0, TX1) or z in (TZ0, TZ1)):
                for y in range(F + 1, CEIL): put(x, y, z, 'concrete:0')
    S.gable_z(TX0 - 1, TX1 + 1, TZ0 - 1, TZ1 + 1, CEIL + 1)
    for x in range(TX0 - 1, TX1 + 2):
        put(x, CEIL + 5, 1842, 'brick_block'); put(x, CEIL + 6, 1842, 'stone_slab:4')
    for x in (TX0, TX1):
        for z in range(TZ0 + 1, TZ1):
            h = min(z - (TZ0 - 1), (TZ1 + 1) - z)
            for y in range(CEIL + 1, CEIL + 1 + h): put(x, y, z, 'concrete:0')
    # ---------- 2. полости: шахта ----------
    for y in range(60, F): put(SHAFT[0], y, SHAFT[1], 'air')
    for x in range(SHAFT[0] - 1, SHAFT[0] + 2):
        for z in range(SHAFT[1] - 1, SHAFT[1] + 2):
            if (x, z) != SHAFT:
                for y in range(59, F):
                    if S.cells.get((x, y, z), 'air') == 'air': put(x, y, z, 'stone')
    put(SHAFT[0], 59, SHAFT[1], 'stone')
    # ---------- 3/4. детали ----------
    put(SHAFT[0], F, SHAFT[1], 'iron_trapdoor:8')
    S.door(TX0, F + 1, 1844, 0)                 # вход с проспекта (с запада, открывается внутрь)
    S.door(-681, F + 1, TZ1, 3)                 # на террасу (с юга)
    S.door(ex0, F + 1, 1841, 2)                 # щитовая
    door_plates(S, [(TX0, F + 1, 1844, (1, 0), 'wood', False), (-681, F + 1, TZ1, (0, -1), 'wood', False),
                    (ex0, F + 1, 1841, (1, 0), 'wood', True)])
    # стойка бара Z 1842 X −685…−683, проход X −682; табуреты перед стойкой лицом к ней (на север)
    for x in (-685, -684, -683):
        put(x, F + 1, 1842, 'planks:5'); put(x, F + 1, 1843, 'spruce_stairs:2')
    put(-685, F + 2, 1842, 'flower_pot')
    # окна: юг (к морю) — нижняя строка прозрачная, верхняя — витраж; север, запад
    for x in (-685, -684, -683, -679, -678):
        put(x, F + 2, TZ1, 'glass_pane'); put(x, F + 3, TZ1, 'stained_glass_pane:1')
    for x in (-684, -683):
        put(x, F + 2, TZ0, 'glass_pane'); put(x, F + 3, TZ0, 'stained_glass_pane:4')
    for z in (1841, 1842):
        put(TX0, F + 2, z, 'glass_pane'); put(TX0, F + 3, z, 'stained_glass_pane:14')
    # свет: светокамень в потолке
    for x, z in ((-684, 1841), (-683, 1844), (-679, 1844), (-679, 1841)): put(x, CEIL, z, 'glowstone')
    # терраса: тент на столбах, два столика с креслами (лицом к столу)
    for x in (TX0, -681, TX1):
        for y in (F + 1, F + 2, F + 3): put(x, y, 1847, 'dark_oak_fence')
    for x in range(TX0, TX1 + 1):
        for z in (1846, 1847):
            put(x, F + 4, z, 'wool:11' if (x % 2) else 'wool:0')
    for tx in (-684, -679):
        put(tx, F + 1, 1846, 'dark_oak_fence'); put(tx, F + 2, 1846, 'wooden_pressure_plate')
        put(tx - 1, F + 1, 1846, 'spruce_stairs:1'); put(tx + 1, F + 1, 1846, 'spruce_stairs:0')
    put(-687, 65, 1839, 'hardened_clay'); put(-687, 66, 1839, 'leaves:4')   # кашпо у угла (проспект рядом)
    return S, H, anchors


def main():
    args = parse_args()
    W = World(built_before('oldtown-5-tavern.json'))
    S, H, anchors = build(W)
    o, rel, order = save(S, args.out)
    print('== ПРОВЕРКИ ==')
    final = std_checks(W, S.cells, o, rel, order, H, anchors)
    targets = {'зал у стойки': (-684, 65, 1844), 'за стойкой (место бармена)': (-684, 65, 1841),
               'место под бочки': (-684, 65, 1840), 'щитовая': (-679, 65, 1841), 'терраса': (-682, 65, 1847),
               'стык с площадью набережной': (-682, 65, 1848), 'Ратушная ул.': (-681, 65.5, 1838),
               'восточный край (−676,1843)': (-676, 65, 1843)}
    seen, bad = walk_report(final, (-689, 65, 1844), ((-690, -674), (1836, 1850), (58, 80)), targets)
    # отдельный маршрут: вход с проспекта → терраса через зал (снаружи перекрыт)
    neg_out = dict(S.cells)
    for z in range(1836, 1850):
        for y in (65, 66, 67): neg_out.setdefault((-687, y, z), 'air')
    for z in range(1839, 1850):
        for y in (65, 66, 67):
            neg_out[(-687, y, z)] = 'stonebrick' if z != 1844 else neg_out.get((-687, y, z), 'air')
            neg_out[(-676, y, z)] = 'stonebrick'
    for x in range(-687, -675):
        for y in (65, 66, 67): neg_out[(x, y, 1838)] = 'stonebrick'
    for x in range(-690, -673):
        for y in (65, 66, 67): neg_out[(x, y, 1848)] = 'stonebrick'
    for y in (65, 66, 67): neg_out[(-686, y, 1847)] = 'stonebrick'
    fn = lambda x, y, z: neg_out.get((x, y, z)) or final(x, y, z)
    s1 = dl.walk_reachable(fn, (-689, 65, 1844), (-690, -674), (1836, 1850), (58, 80))
    print('  маршрут: проспект → дверь → зал → дверь террасы → терраса (обходы снаружи закрыты):', dl.reached(s1, -682, 65, 1847))
    neg = dict(neg_out); neg[(-681, F + 1, TZ1)] = 'concrete:0'; neg[(-681, F + 2, TZ1)] = 'concrete:0'
    fn2 = lambda x, y, z: neg.get((x, y, z)) or final(x, y, z)
    s2 = dl.walk_reachable(fn2, (-689, 65, 1844), (-690, -674), (1836, 1850), (58, 80))
    print('НЕГАТИВ: дверь на террасу заложена — терраса изнутри недостижима:', not dl.reached(s2, -682, 65, 1847))
    lo = W.cave_top(*SHAFT)
    print('шахта: низ Y 60 | кровля каньона под ней', None if lo is None else 58 - lo)
    if args.preview:
        v1 = elevation(final, 'z', None, range(-689, -673), range(1852, 1830, -1))
        v2 = section(final, 'x', -684, range(1836, 1850))
        v3 = elevation(final, 'x', None, range(1849, 1835, -1), range(-690, -670))
        preview(args.preview, final, (-689, -674, 1836, 1850),
                [('Фасад к морю (с юга)', v1[0], v1[1], (62, 77)), ('Разрез X=−684', v2[0], v2[1], (62, 77)),
                 ('Вид с запада', v3[0], v3[1], (62, 77))], 'Этап 5 — таверна')


if __name__ == '__main__':
    main()
