"""Старый город, этап 7: павильон «Галерея» и променад озера D (CITY.md §7.3).

- павильон X −703…−696, Z 1830…1838 (современная архитектура): пол Y 66
  (блок Y 65) вровень с набережной, северная часть — над водой на кварцевых
  сваях; белый бетон, стеклянные стены к озеру, плоская кровля-козырёк со свесом
  к воде; внутри — зал с «картинами» из глазурованной терракоты,
  электрощитовая 3×3 (ЮЗ угол, глухие стены) с кабельной шахтой 1×1 и люком
  iron_trapdoor:8; двери — на набережную (запад), к проспекту (восток), на
  переулок (юг); нажимные плиты изнутри (пол бетон — каменные), у щитовой — с
  обеих сторон (CITY.md §6);
- променад: набережные озера (верх Y 66) + полоса X −708…−707 и южная полоса
  Z 1834…1838 — мощение песчаником, скамейки лицом к озеру, фонари, кашпо, урны.

Запуск: gen_oldtown_7.py [--out schemas/oldtown-7-gallery.json]
                         [--preview docs/districts/oldtown-7-preview.png]
Мир — World(built_before('oldtown-7-gallery.json')).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oldtown_lib import *  # noqa: E402,F403

BX0, BX1, BZ0, BZ1 = -708, -693, 1819, 1838
PX0, PX1, PZ0, PZ1 = -703, -696, 1830, 1838       # павильон
LAKE = (-706, -693, 1819, 1833)                   # озеро D с набережной
F = 65
TOP = 70                                          # плита кровли
EL = (-703, -699, 1834, 1838)                     # щитовая со стенами
SHAFT = (-702, 1836)
ART = ('light_blue_glazed_terracotta:0', 'orange_glazed_terracotta:1', 'magenta_glazed_terracotta:2',
       'yellow_glazed_terracotta:3', 'cyan_glazed_terracotta:0', 'lime_glazed_terracotta:1')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-7-gallery.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-7-preview.png'))
    return p.parse_args()


def in_rect(x, z, r): return r[0] <= x <= r[1] and r[2] <= z <= r[3]


def build(W):
    S = Schema(W); put = S.put
    pav = (PX0, PX1, PZ0, PZ1)
    block = [(x, z) for x in range(BX0, BX1 + 1) for z in range(BZ0, BZ1 + 1)
             if not in_rect(x, z, pav) and not in_rect(x, z, LAKE)]
    H, anchors = paving_heights(W, block, base=66.0, extra_anchors={(PX1 + 1, 1835): 66.0})
    S.pave(H, lambda x, z: ('stonebrick', 'stone_slab:5') if z % 5 == 0 else ('sandstone:2', 'stone_slab:1'))
    # ================= 1. МАССИВЫ =================
    for x in range(PX0, PX1 + 1):
        for z in range(PZ0, PZ1 + 1):
            over_water = W.block(x, F, z) == 'water'
            if over_water: put(x, F, z, 'concrete:0')
            else: S.ground_to(x, z, F, 'concrete:0')
            edge = x in (PX0, PX1) or z in (PZ0, PZ1)
            corner = x in (PX0, PX1) and z in (PZ0, PZ1)
            for y in range(F + 1, TOP):
                if not edge: put(x, y, z, 'air')
                elif corner or z == PZ1 or (x == PX0 and z >= EL[2]): put(x, y, z, 'concrete:0')
                else: put(x, y, z, 'glass')
    for x in range(PX0 - 1, PX1 + 2):                 # плита кровли со свесом (к воде — 2)
        for z in range(PZ0 - 2, PZ1 + 1):
            put(x, TOP, z, 'concrete:0')
    for x in range(PX0 - 1, PX1 + 2):
        for z in range(PZ0 - 2, PZ1 + 1):
            if x in (PX0 - 1, PX1 + 1) or z in (PZ0 - 2, PZ1): put(x, TOP + 1, z, 'stone_slab:7')
    for x in (PX0, (PX0 + PX1) // 2, PX1):           # сваи под свесом пола
        for y in range(62, F): put(x, y, PZ0, 'quartz_block:2')
    ex0, ex1, ez0, ez1 = EL
    for x in range(ex0, ex1 + 1):
        for z in range(ez0, ez1 + 1):
            if (x == ex1 or z == ez0) and not (x in (PX0, PX1) or z in (PZ0, PZ1)):
                for y in range(F + 1, TOP): put(x, y, z, 'concrete:0')
    # ================= 2. ПОЛОСТИ =================
    for y in range(60, F): put(SHAFT[0], y, SHAFT[1], 'air')
    for x in range(SHAFT[0] - 1, SHAFT[0] + 2):
        for z in range(SHAFT[1] - 1, SHAFT[1] + 2):
            if (x, z) != SHAFT:
                for y in range(59, F):
                    if S.cells.get((x, y, z), W.block(x, y, z)) in ('air', 'plant', 'water'): put(x, y, z, 'concrete:0')
    if W.block(SHAFT[0], 59, SHAFT[1]) in ('air', 'plant', 'water'): put(SHAFT[0], 59, SHAFT[1], 'concrete:0')
    # ================= 3/4. ДЕТАЛИ =================
    S.door(PX0, F + 1, 1833, 0, 'iron_door' if False else 'birch_door', 8)       # на набережную (запад)
    S.door(PX1, F + 1, 1835, 2, 'birch_door', 8)                                   # к проспекту (восток)
    S.door(-698, F + 1, PZ1, 3, 'birch_door', 8)                                   # на переулок (юг; снаружи 65.5)
    S.door(-701, F + 1, ez0, 1, 'birch_door', 8)                                   # щитовая
    door_plates(S, [(PX0, F + 1, 1833, (1, 0), 'stone', False), (PX1, F + 1, 1835, (-1, 0), 'stone', False),
                    (-698, F + 1, PZ1, (0, -1), 'stone', False), (-701, F + 1, ez0, (0, 1), 'stone', True)])
    put(SHAFT[0], F, SHAFT[1], 'iron_trapdoor:8')
    for x, z in ((-701, 1831), (-698, 1831), (-701, 1836), (-697, 1836)): put(x, TOP, z, 'sea_lantern')
    # «картины»: панели 1×2 из глазурованной терракоты на белых тумбах вдоль щитовой и у восточной стены
    for i, (x, z) in enumerate(((-700, 1832), (-698, 1832))):
        put(x, F + 1, z, 'quartz_block'); put(x, F + 2, z, ART[2 * i]); put(x, F + 3, z, ART[2 * i + 1])
    for i, z in enumerate((1836, 1837)):
        put(-697, F + 2, z, ART[4 + i])            # тумбы у восточной стены
        put(-697, F + 1, z, 'quartz_block')
    # променад: скамейки лицом к озеру (восток), фонари, кашпо, урны
    for z0 in (1821, 1827):
        for i, z in enumerate(range(z0, z0 + 4)):
            put(-707, 66, z, ('trapdoor:4', 'birch_stairs:1', 'birch_stairs:1', 'trapdoor:5')[i])
    put(-707, 66, 1826, 'cauldron')
    for x, z in ((-708, 1820), (-708, 1833), (-694, 1837)):
        h = H[(x, z)]; b = int(h) if h == int(h) else int(h) + 1
        if h != int(h): put(x, int(h), z, 'stonebrick')
        for i, blk in enumerate(('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')):
            put(x, b + i, z, blk)
    for x, z in ((-708, 1837), (-705, 1837), (-694, 1834)):
        h = H[(x, z)]; b = int(h) if h == int(h) else int(h) + 1
        if h != int(h): put(x, int(h), z, 'stonebrick')
        put(x, b, z, 'hardened_clay'); put(x, b + 1, z, 'leaves:4')
    return S, H, anchors


def main():
    args = parse_args()
    W = World(built_before('oldtown-7-gallery.json'))
    S, H, anchors = build(W)
    o, rel, order = save(S, args.out)
    print('== ПРОВЕРКИ ==')
    final = std_checks(W, S.cells, o, rel, order, H, anchors)
    targets = {'павильон: зал у воды': (-699, 66, 1831), 'павильон: восток': (-698, 66, 1836), 'щитовая': (-701, 66, 1836),
               'перед скамейкой (набережная)': (-706, 66, 1823), 'набережная, север': (-700, 66, 1819),
               'набережная, восток': (-693, 66, 1826), 'южная полоса': (-706, 66, 1836), 'переулок Z1840': (-700, 66, 1840),
               'проспект С–Ю': (-690, 66, 1830), 'главный проспект': (-700, 66, 1817)}
    seen, bad = walk_report(final, (-700, 66, 1817), ((-710, -689), (1816, 1842), (58, 80)), targets)
    miss = pave_unreached(S, H, seen)
    print('  клетки мощения без стоянки (кроме занятых):', len(miss), miss[:6])
    lo = W.cave_top(*SHAFT)
    print('шахта: низ Y 60 | кровля каньона под ней', None if lo is None else 58 - lo)
    # маршрут через павильон: с набережной (запад) — к переулку (юг), обход по южной полосе закрыт
    neg = dict(S.cells)
    for x in range(-710, -692):                       # переулок закрыт стеной, кроме клетки у южной двери
        if x != -698:
            for y in (65, 66, 67): neg[(x, y, 1839)] = 'stonebrick'
    for y in (65, 66, 67): neg[(-698, y, 1840)] = 'stonebrick'
    fn = lambda x, y, z: neg.get((x, y, z)) or final(x, y, z)
    s1 = dl.walk_reachable(fn, (-706, 66, 1830), (-710, -693), (1819, 1842), (58, 80))   # без проспекта С–Ю
    print('  маршрут: набережная → западная дверь → зал → южная дверь → переулок (обходы закрыты):', dl.reached(s1, -698, 65.5, 1839))
    neg2 = dict(neg)
    for y in (66, 67): neg2[(-698, y, PZ1)] = 'concrete:0'; neg2[(PX1, y, 1835)] = 'concrete:0'
    s2 = dl.walk_reachable(lambda x, y, z: neg2.get((x, y, z)) or final(x, y, z), (-706, 66, 1830), (-710, -693), (1819, 1842), (58, 80))
    print('НЕГАТИВ: южная и восточная двери заложены — переулок через павильон недостижим:', not dl.reached(s2, -698, 65.5, 1839))
    neg3 = dict(S.cells); neg3[(-706, 66, 1822)] = 'stonebrick'
    _, tr = fns(W, S.cells, o)
    rel3 = {(x - o[0], y - o[1], z - o[2]): b for (x, y, z), b in neg3.items()}
    print('НЕГАТИВ: перед скамейкой блок — ошибок', len(dl.check_bench_front(rel3, tr)), '(ждём > 0)')
    if args.preview:
        v1 = elevation(final, 'z', None, range(-710, -690), range(1816, 1845))
        v2 = section(final, 'x', -700, range(1816, 1842))
        v3 = elevation(final, 'x', None, range(1842, 1816, -1), range(-688, -712, -1))
        preview(args.preview, final, (-710, -689, 1816, 1842),
                [('С озера (с севера)', v1[0], v1[1], (60, 74)), ('Разрез X=−700', v2[0], v2[1], (60, 74)),
                 ('С проспекта (с востока)', v3[0], v3[1], (60, 74))], 'Этап 7 — павильон «Галерея» и променад')


if __name__ == '__main__':
    main()
