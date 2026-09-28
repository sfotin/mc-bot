"""Старый город, этап 4: рынок — площадь с прилавками и крытый рынок (CITY.md §7.3).

Квартал X −687…−661, Z 1796…1813 (проспекты С–Ю и главный, Рыночный пер.,
восточная граница) целиком, пол Y 65, к улицам — полублоками:
- рыночная площадь X −687…−675: 5 прилавков под полосатыми тентами (ряд у
  проспекта лицом на восток, ряд у рынка лицом на запад, проход 4 бл.),
  скамейка, урна; место под вестибюль метро X −687…−683, Z 1807…1812 —
  свободное мощение;
- крытый рынок X −674…−663, Z 1797…1811: открытая аркада (песчаник,
  арки из перевёрнутых ступенек), пол — песчаник и оранжевая терракота
  шахматкой, двускатная кровля (конёк по Z) с фронтонами-витражами, фонари на
  цепях, прилавки внутри; электрощитовая 3×3 (СВ угол) с кабельной шахтой 1×1
  от Y 60, люк iron_trapdoor:8; нажимные плиты у двери щитовой с обеих сторон
  (пол каменный — каменные, CITY.md §6).

Запуск: gen_oldtown_4.py [--out schemas/oldtown-4-market.json]
                         [--preview docs/districts/oldtown-4-preview.png]
Мир — World(built_before('oldtown-4-market.json')).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oldtown_lib import *  # noqa: E402,F403

BX0, BX1, BZ0, BZ1 = -687, -661, 1796, 1813
HX0, HX1, HZ0, HZ1 = -674, -663, 1797, 1811          # крытый рынок
F = 64                                               # блок пола (верх 65)
PX = (-674, -671, -666, -663)                        # опоры по X на северной/южной стороне
PZ = (1797, 1801, 1807, 1811)                        # опоры по Z на западной/восточной стороне
EL = (-667, -663, 1797, 1801)                        # щитовая со стенами (внутри 3×3)
SHAFT = (-664, 1798)
VEST = (-687, -683, 1807, 1812)                      # резерв вестибюля «Центр»
STALLS = [  # (X зад, X перед, Z0, цвета тента) — прилавок 3 (Z) × 3 (X)
    (-686, -684, 1797, (11, 0)), (-686, -684, 1801, (14, 0)),
    (-677, -679, 1797, (1, 4)), (-677, -679, 1801, (5, 0)), (-677, -679, 1805, (11, 0))]
GOODS = ('melon_block', 'pumpkin:1', 'hay_block', 'melon_block', 'pumpkin:3')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-4-market.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-4-preview.png'))
    return p.parse_args()


def in_hall(x, z): return HX0 <= x <= HX1 and HZ0 <= z <= HZ1


def build(W):
    S = Schema(W); put = S.put
    block = [(x, z) for x in range(BX0, BX1 + 1) for z in range(BZ0, BZ1 + 1) if not in_hall(x, z)]
    H, anchors = paving_heights(W, block)

    def mat(x, z):
        if x > HX0 - 1 - 1 and not in_hall(x, z): return 'double_stone_slab', 'stone_slab'   # кольцо у рынка
        return ('stonebrick', 'stone_slab:5') if (x + z) % 5 else ('stone:6', 'stone_slab:5')
    S.pave(H, mat)
    # ---------- крытый рынок: 1. массивы ----------
    for x in range(HX0, HX1 + 1):
        for z in range(HZ0, HZ1 + 1):
            S.ground_to(x, z, F, 'sandstone:2' if (x + z) % 2 else 'stained_hardened_clay:1')
            put(x, F - 1, z, 'stone')
    edge = lambda x, z: x in (HX0, HX1) or z in (HZ0, HZ1)
    pillar = lambda x, z: (z in (HZ0, HZ1) and x in PX) or (x in (HX0, HX1) and z in PZ)
    for x in range(HX0, HX1 + 1):
        for z in range(HZ0, HZ1 + 1):
            if edge(x, z):
                for y in range(F + 1, F + 5): put(x, y, z, 'sandstone:2' if pillar(x, z) else 'air')
                put(x, F + 5, z, 'sandstone:2'); put(x, F + 6, z, 'sandstone:2')   # балка и фриз
            else:
                for y in range(F + 1, F + 6): put(x, y, z, 'air')
    # щитовая: стены, потолок
    ex0, ex1, ez0, ez1 = EL
    for x in range(ex0, ex1 + 1):
        for z in range(ez0, ez1 + 1):
            wall = x in (ex0, ex1) or z in (ez0, ez1)
            for y in range(F + 1, F + 5): put(x, y, z, 'sandstone:2' if wall else 'air')
            put(x, F + 5, z, 'sandstone:2')
    # кровля и фронтоны
    rows = S.gable_x(HX0 - 1, HX1 + 1, HZ0 - 1, HZ1 + 1, F + 7)
    for z in (HZ0, HZ1):
        for x in range(HX0, HX1 + 1):
            h = min(x - (HX0 - 1), (HX1 + 1) - x)
            for y in range(F + 7, F + 7 + h): put(x, y, z, 'sandstone:2')
    # ---------- 2. полости: шахта ----------
    for y in range(60, F): put(SHAFT[0], y, SHAFT[1], 'air')
    for x in range(SHAFT[0] - 1, SHAFT[0] + 2):
        for z in range(SHAFT[1] - 1, SHAFT[1] + 2):
            if (x, z) != SHAFT:
                for y in range(59, F):
                    if S.cells.get((x, y, z), 'air') == 'air': put(x, y, z, 'stone')
    put(SHAFT[0], 59, SHAFT[1], 'stone')
    # ---------- 3/4. детали ----------
    # арки: перевёрнутые ступеньки под балкой у опор, где пролёт >= 3
    for z in (HZ0, HZ1):
        xs = sorted(PX)
        for a, b in zip(xs, xs[1:]):
            if b - a - 1 >= 3: put(a + 1, F + 4, z, 'sandstone_stairs:5'); put(b - 1, F + 4, z, 'sandstone_stairs:4')
            else:
                for x in range(a + 1, b): put(x, F + 4, z, 'sandstone:2')
    for x in (HX0, HX1):
        zs = sorted(PZ)
        for a, b in zip(zs, zs[1:]):
            if x == HX1 and b <= EL[3]: continue
            if b - a - 1 >= 3: put(x, F + 4, a + 1, 'sandstone_stairs:7'); put(x, F + 4, b - 1, 'sandstone_stairs:6')
            else:
                for z in range(a + 1, b): put(x, F + 4, z, 'sandstone:2')
    # витражи во фронтонах (круглое окно 3×3 без углов) — на оси X −669/−668
    for z in (HZ0, HZ1):
        for x, y, c in ((-669, F + 9, 4), (-668, F + 9, 4), (-669, F + 10, 11), (-668, F + 10, 11), (-669, F + 8, 14), (-668, F + 8, 14)):
            put(x, y, z, f'stained_glass_pane:{c}')
    # дверь щитовой (на запад), плиты с обеих сторон, люк шахты, свет
    S.door(ex0, F + 1, 1799, 2)
    door_plates(S, [(ex0, F + 1, 1799, (1, 0), 'stone', True)])
    put(SHAFT[0], F, SHAFT[1], 'iron_trapdoor:8')
    put(-665, F + 5, 1799, 'sea_lantern')
    # фонари на цепях
    for x in (-671, -666):
        for z in (1804, 1808) if x == -666 else (1800, 1804, 1808):
            top = F + 7 + min(x - (HX0 - 1), (HX1 + 1) - x) - 1          # низ ступеньки ската над клеткой
            for y in range(F + 6, top): put(x, y, z, 'dark_oak_fence')
            put(x, F + 5, z, 'sea_lantern')
    for x, z in ((HX0, 1804), (HX1, 1804), (-668, HZ0), (-668, HZ1)): put(x, F + 5, z, 'sea_lantern')   # в балке над входами
    # прилавки в зале: стойки из еловых досок с товаром
    for i, (x, z0) in enumerate(((-671, 1799), (-671, 1803), (-671, 1807), (-666, 1804), (-666, 1807))):
        for dz in range(3):
            put(x, F + 1, z0 + dz, 'planks:1')
            put(x, F + 2, z0 + dz, GOODS[(i + dz) % len(GOODS)])
    # прилавки на площади
    for n, (xb, xf, z0, (c1, c2)) in enumerate(STALLS):
        base = 65
        xmid = (xb + xf) // 2
        for z in (z0, z0 + 2):
            for x in (xb, xf):
                for y in (base, base + 1, base + 2): put(x, y, z, 'dark_oak_fence')
        put(xf, base, z0 + 1, 'planks:5'); put(xf, base + 1, z0 + 1, GOODS[n])
        for x in range(min(xb, xf), max(xb, xf) + 1):
            for z in range(z0, z0 + 3):
                put(x, base + 3, z, f'wool:{c1 if (z - z0) % 2 == 0 else c2}')
        put(xmid, base + 3, z0 + 1, 'sea_lantern')
    # скамейка лицом на север (к прилавкам), урна, кашпо у рынка
    for i, x in enumerate(range(-681, -677)): put(x, 65, 1811, ('trapdoor:6', 'birch_stairs:2', 'birch_stairs:2', 'trapdoor:7')[i])
    put(-677, 65, 1811, 'cauldron')
    for x, z in ((-675, 1797), (-675, 1811), (-662, 1812), (-662, 1796)):
        put(x, 65, z, 'hardened_clay'); put(x, 66, z, 'leaves:4')
    return S, H, anchors


def main():
    args = parse_args()
    W = World(built_before('oldtown-4-market.json'))
    S, H, anchors = build(W)
    o, rel, order = save(S, args.out)
    print('== ПРОВЕРКИ ==')
    final = std_checks(W, S.cells, o, rel, order, H, anchors)
    targets = {'проход между рядами': (-681, 65, 1800), 'перед прилавком ряда 1': (-683, 65, 1802),
               'перед прилавком ряда 2': (-680, 65, 1806), 'скамейка (перед)': (-679, 65, 1810),
               'место вестибюля': (-685, 65, 1810), 'рынок: центр': (-668, 65, 1804), 'рынок: юг': (-668, 65, 1810),
               'щитовая': (-665, 65, 1799), 'выход на Рыночный пер.': (-668, 65, 1795),
               'выход на главный пр.': (-668, 64, 1814), 'восточная граница': (-661, 65, 1805)}
    seen, bad = walk_report(final, (-689, 65, 1804), ((-690, -659), (1793, 1815), (58, 80)), targets)
    miss = [c for c in H if not any(s[0] == c[0] and s[1] == c[1] for s in seen)
            and all(S.cells.get((c[0], y, c[1]), 'air') == 'air' for y in range(65, 69))]
    print('  клетки мощения без стоянки (кроме занятых):', len(miss), miss[:5])
    lo = S.W.cave_top(*SHAFT)
    print('шахта: низ Y 60 | кровля каньона под ней', None if lo is None else 58 - lo)
    # негативы
    neg = dict(S.cells)
    for z in range(HZ0, HZ1 + 1):
        for y in (65, 66): neg[(-669, y, z)] = 'sandstone:2'; neg[(-676, y, z)] = 'sandstone:2'
    for x in range(-676, -660):
        for y in (65, 66): neg[(x, y, 1812)] = 'sandstone:2'; neg[(x, y, 1796)] = 'sandstone:2'
    fn = lambda x, y, z: neg.get((x, y, z)) or final(x, y, z)
    s2 = dl.walk_reachable(fn, (-689, 65, 1804), (-690, -659), (1793, 1815), (58, 80))
    print('НЕГАТИВ: стена поперёк рынка и вокруг — центр недостижим с запада:', not dl.reached(s2, -666, 65, 1804))
    neg = dict(S.cells); neg[(-679, 65, 1810)] = 'planks:1'
    o_ = o; rel2 = {(x - o_[0], y - o_[1], z - o_[2]): b for (x, y, z), b in neg.items()}
    _, tr = fns(W, S.cells, o)
    print('НЕГАТИВ: перед скамейкой прилавок — ошибок', len(dl.check_bench_front(rel2, tr)), '(ждём > 0)')
    if args.preview:
        v1 = elevation(final, 'x', None, range(1813, 1795, -1), range(-690, -655))
        v2 = section(final, 'z', 1804, range(-690, -658))
        v3 = elevation(final, 'z', None, range(-690, -658), range(1820, 1790, -1))
        preview(args.preview, final, (-689, -659, 1794, 1815),
                [('Вид с запада (Z 1813…1796)', v1[0], v1[1], (62, 78)), ('Разрез Z=1804', v2[0], v2[1], (62, 78)),
                 ('Вид с юга (X −690…−659)', v3[0], v3[1], (62, 78))], 'Этап 4 — рынок, сверху')


if __name__ == '__main__':
    main()
