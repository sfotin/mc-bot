"""Старый город, этап 6: библиотека с чаровальней, Библиотечная площадь и статуя крипера
(CITY.md §7.3; вместо собора плана v1 — решение владельца).

- библиотека X −717…−707, Z 1794…1810: 2 этажа (пол Y 66 и Y 71; над пустотами
  каньона — без выемок), песчаник, кварцевые пилястры и карниз, плоская кровля с
  парапетом и световыми фонарями; портик на восток (кварцевые колонны, фронтон) —
  вход с площади;
  1-й этаж: чаровальня 5×5 (стол зачарований, 30 книжных полок в два яруса),
  читальный зал с полками, столами и наковальней, лестница на 2-й этаж,
  электрощитовая 3×3 (СВ угол) с кабельной шахтой 1×1 от Y 60;
  2-й этаж: читальный зал; серверная ME 3×3 над щитовой (шахта с люком
  iron_trapdoor:8 проходит в неё), в её стене — проём 1×1 под ME-кабель и
  терминал со стороны зала (кабель, терминал, контроллер ставит игрок);
  нажимные плиты у дверей изнутри, у внутренних — с обеих сторон (CITY.md §6);
- Библиотечная площадь и обход X −719…−693, Z 1792…1813 (без пруда): песчаник с
  сеткой каменного кирпича, скамейки лицом к пруду, урна, фонари, кашпо;
- статуя крипера (масштаб 1 блок = 2 пикселя, высота 13 бл.) на постаменте 6×6
  X −699…−694, Z 1792…1797, лицом к проспекту С–Ю (восток).

v2 (после постройки v1): колонны портика и скамейки висели на блок над мощением —
портик поднят на Y 66 (ступени полублоками вокруг), скамейки и урна ставятся на мощение.
Исправление к построенной v1: --fix-from schemas/oldtown-6-library.json --fix-out
schemas/oldtown-6-fix-1.json. После его постройки вывод генератора — как построено.

Запуск: gen_oldtown_6.py [--out schemas/oldtown-6-library.json]
                         [--preview docs/districts/oldtown-6-preview.png]
Мир — World(built_before('oldtown-6-library.json')).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oldtown_lib import *  # noqa: E402,F403

BX0, BX1, BZ0, BZ1 = -719, -693, 1792, 1813
LX0, LX1, LZ0, LZ1 = -717, -707, 1794, 1810        # библиотека (стены)
POND = (-699, -693, 1799, 1812)
PLINTH = (-699, -694, 1792, 1797)                  # постамент статуи
F, F2, RF = 65, 70, 75                             # полы (блоки) 1 и 2 эт., кровля
DOOR_Z = 1802
TABLE = (-714, F + 1, 1797)                        # стол зачарований
ENCH = (-716, -712, 1795, 1799)                    # чаровальня (внутри)
ELEC = (-710, -708, 1795, 1797)                    # щитовая / серверная (внутри)
SHAFT = (-708, 1795)
ME_PORT = (-708, F2 + 2, 1798)                     # проём под ME-кабель и терминал
STAIR = [(-715 + i, F + 1 + i) for i in range(5)]  # (X, Y) ступеней, Z 1808…1809, подъём на восток


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default=os.path.join(REPO, 'schemas', 'oldtown-6-library.json'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-6-preview.png'))
    p.add_argument('--fix-from', help='построенная схема — для исправляющей схемы')
    p.add_argument('--fix-out', help='куда записать исправляющую схему')
    return p.parse_args()


def in_rect(x, z, r): return r[0] <= x <= r[1] and r[2] <= z <= r[3]


def enchant_power(final, t):
    """Число книжных полок, которые засчитывает стол зачарований (правило 1.12)."""
    x, y, z = t
    n = 0
    air = lambda a, b, c: final(a, b, c) == 'air'
    shelf = lambda a, b, c: final(a, b, c) == 'bookshelf'
    for k in (-1, 0, 1):
        for i in (-1, 0, 1):
            if (i, k) == (0, 0) or not (air(x + i, y, z + k) and air(x + i, y + 1, z + k)): continue
            n += shelf(x + 2 * i, y, z + 2 * k) + shelf(x + 2 * i, y + 1, z + 2 * k)
            if i and k:
                n += shelf(x + 2 * i, y, z + k) + shelf(x + 2 * i, y + 1, z + k)
                n += shelf(x + i, y, z + 2 * k) + shelf(x + i, y + 1, z + 2 * k)
    return n


def h32(x, y, z):
    v = (x * 73856093 ^ y * 19349663 ^ z * 83492791) & 0xffffffff
    v = (v ^ (v >> 13)) * 0x5bd1e995 & 0xffffffff
    return ((v ^ (v >> 15)) & 0xffff) / 0xffff


def build(W):
    S = Schema(W); put = S.put
    lib = (LX0, LX1, LZ0, LZ1)
    block = [(x, z) for x in range(BX0, BX1 + 1) for z in range(BZ0, BZ1 + 1)
             if not in_rect(x, z, lib) and not in_rect(x, z, POND) and not in_rect(x, z, PLINTH)]
    H, anchors = paving_heights(W, block, extra_anchors={(LX1 + 1, z): 66.0 for z in range(LZ0 + 2, LZ1 - 1)})   # портик Y 66
    portico = lambda x, z: x == LX1 + 1 and LZ0 + 2 <= z <= LZ1 - 2
    S.pave(H, lambda x, z: ('quartz_block', 'stone_slab:7') if portico(x, z) else
           ('stonebrick', 'stone_slab:5') if (x % 4 == 0 or z % 4 == 0) else ('sandstone:2', 'stone_slab:1'))
    # ================= 1. МАССИВЫ =================
    for x in range(LX0, LX1 + 1):
        for z in range(LZ0, LZ1 + 1):
            wall = x in (LX0, LX1) or z in (LZ0, LZ1)
            S.ground_to(x, z, F, 'stonebrick' if wall else ('stone:4' if (x + z) % 2 else 'stone:6'))
            if wall:
                corner = x in (LX0, LX1) and z in (LZ0, LZ1)
                for y in range(F + 1, RF): put(x, y, z, 'quartz_block:2' if corner else 'sandstone:2')
                put(x, F2, z, 'quartz_block')                       # пояс
                put(x, RF, z, 'quartz_block'); put(x, RF + 1, z, 'stone_slab:7')   # карниз, парапет
            else:
                put(x, F2, z, 'sandstone:2'); put(x, RF, z, 'sandstone:2')
    # перегородки: чаровальня, щитовая (1 эт.), серверная (2 эт.)
    for z in range(LZ0 + 1, 1801):
        for y in list(range(F + 1, F2)): put(-711, y, z, 'sandstone:2')
    for x in range(-716, -710):
        for y in range(F + 1, F2): put(x, y, 1800, 'sandstone:2')
    for x in range(-710, -707):
        for y in list(range(F + 1, F2)) + list(range(F2 + 1, RF)): put(x, y, 1798, 'sandstone:2')
    for z in range(LZ0 + 1, 1799):
        for y in range(F2 + 1, RF): put(-711, y, z, 'sandstone:2')
    # портик: колонны, антаблемент, фронтон
    PX = LX1 + 1
    for z in (1797, 1799, 1805, 1807):
        for y in range(F + 1, RF - 1): put(PX, y, z, 'quartz_block:2')
    for z in range(LZ0 + 2, LZ1 - 1):
        put(PX, RF - 1, z, 'quartz_block'); put(PX, RF, z, 'quartz_block:1')
    for i in range(7):
        z0, z1 = LZ0 + 2 + i, LZ1 - 2 - i
        if z0 > z1: break
        for z in range(z0, z1 + 1):
            put(PX, RF + 1 + i, z, 'quartz_stairs:2' if z == z0 and z0 != z1 else 'quartz_stairs:3' if z == z1 and z0 != z1 else 'quartz_block')
    # постамент статуи
    for x in range(PLINTH[0], PLINTH[1] + 1):
        for z in range(PLINTH[2], PLINTH[3] + 1):
            ring = x in (PLINTH[0], PLINTH[1]) or z in (PLINTH[2], PLINTH[3])
            S.ground_to(x, z, 66, 'quartz_block' if ring else 'stonebrick')
    # статуя крипера: ноги Y 67…69 (4×4), тело Y 70…75 (2×4), голова Y 76…79 (4×4)
    greens = ('concrete:5', 'wool:5', 'concrete:13', 'wool:13', 'concrete:5')
    def gc(x, y, z, dark=False):
        v = h32(x, y, z)
        return ('concrete:13' if v < 0.5 else 'wool:13') if dark else greens[int(v * 5) % 5]
    CX = (-698, -695); CZ = (1793, 1796)
    for x in range(CX[0], CX[1] + 1):
        for z in range(CZ[0], CZ[1] + 1):
            for y in (67, 68, 69): put(x, y, z, gc(x, y, z, True))
            for y in range(76, 80): put(x, y, z, gc(x, y, z))
    for x in (-697, -696):
        for z in range(CZ[0], CZ[1] + 1):
            for y in range(70, 76): put(x, y, z, gc(x, y, z))
    FACE = {79: 'GGGG', 78: 'BGGB', 77: 'GBBG', 76: 'GBBG'}         # лицо — на восточной грани головы
    for y, row in FACE.items():
        for i, c in enumerate(row):
            if c == 'B': put(CX[1], y, CZ[0] + i, 'concrete:15')
    # ================= 2. ПОЛОСТИ =================
    for x in range(LX0 + 1, LX1):
        for z in range(LZ0 + 1, LZ1):
            for y in list(range(F + 1, F2)) + list(range(F2 + 1, RF)):
                if S.cells.get((x, y, z)) != 'sandstone:2': put(x, y, z, 'air')
    for x, _ in STAIR[:4]:
        for z in (1808, 1809): put(x, F2, z, 'air')
    put(*ME_PORT, 'air')
    for y in range(60, F): put(SHAFT[0], y, SHAFT[1], 'air')
    for x in range(SHAFT[0] - 1, SHAFT[0] + 2):
        for z in range(SHAFT[1] - 1, SHAFT[1] + 2):
            if (x, z) != SHAFT:
                for y in range(59, F):
                    if S.cells.get((x, y, z), W.block(x, y, z)) in ('air', 'plant', 'water'): put(x, y, z, 'stonebrick')
    # ================= 3/4. ДЕТАЛИ =================
    for x, y in STAIR:
        for z in (1808, 1809): put(x, y, z, 'sandstone_stairs:0')
    for x in range(-715, -711): put(x, F2 + 1, 1807, 'dark_oak_fence')          # перила проёма
    put(SHAFT[0], F, SHAFT[1], 'iron_trapdoor:8'); put(SHAFT[0], F2, SHAFT[1], 'iron_trapdoor:8')
    S.door(LX1, F + 1, DOOR_Z, 2, 'dark_oak_door', 8)
    for z in (DOOR_Z - 1, DOOR_Z + 1):
        for y in (F + 1, F + 2): put(LX1, y, z, 'quartz_block:2')
    for z in (DOOR_Z - 1, DOOR_Z, DOOR_Z + 1): put(LX1, F + 3, z, 'quartz_block:1')
    S.door(-714, F + 1, 1800, 3, 'wooden_door', 8)           # чаровальня
    S.door(-709, F + 1, 1798, 3, 'wooden_door', 8)           # щитовая
    S.door(-709, F2 + 1, 1798, 3, 'wooden_door', 8)          # серверная
    door_plates(S, [(LX1, F + 1, DOOR_Z, (-1, 0), 'stone', False), (-714, F + 1, 1800, (0, -1), 'stone', True),
                    (-709, F + 1, 1798, (0, -1), 'stone', True), (-709, F2 + 1, 1798, (0, -1), 'stone', True)])
    # чаровальня: стол, 2 яруса полок по кольцу 5×5 (проём — дверь)
    put(*TABLE, 'enchanting_table')
    for x in range(ENCH[0], ENCH[1] + 1):
        for z in range(ENCH[2], ENCH[3] + 1):
            if (x in (ENCH[0], ENCH[1]) or z in (ENCH[2], ENCH[3])) and (x, z) != (-714, 1799):
                put(x, F + 1, z, 'bookshelf'); put(x, F + 2, z, 'bookshelf')
    # читальный зал 1 эт.: полки у стен, столы с креслами, наковальня
    for z in range(1801, 1808): put(-716, F + 1, z, 'bookshelf'); put(-716, F + 2, z, 'bookshelf')
    for z in range(1804, 1808): put(-708, F + 1, z, 'bookshelf'); put(-708, F + 2, z, 'bookshelf')
    for tz in (1803, 1806):
        put(-713, F + 1, tz, 'dark_oak_fence'); put(-713, F + 2, tz, 'wooden_pressure_plate')
        put(-714, F + 1, tz, 'spruce_stairs:1'); put(-712, F + 1, tz, 'spruce_stairs:0')
    put(-710, F + 1, 1805, 'anvil')
    # 2-й этаж: полки, столы, терминал ME (проём в стене серверной — место кабеля)
    for z in range(1795, 1807): put(-716, F2 + 1, z, 'bookshelf'); put(-716, F2 + 2, z, 'bookshelf'); put(-716, F2 + 3, z, 'bookshelf')
    for x in range(-715, -711): put(x, F2 + 1, LZ0 + 1, 'bookshelf'); put(x, F2 + 2, LZ0 + 1, 'bookshelf')
    for tz in (1801, 1804):
        put(-712, F2 + 1, tz, 'dark_oak_fence'); put(-712, F2 + 2, tz, 'wooden_pressure_plate')
        put(-713, F2 + 1, tz, 'spruce_stairs:1'); put(-711, F2 + 1, tz, 'spruce_stairs:0')
    # окна (прозрачные), световые фонари в кровле, свет
    def win(x, z, ys):
        for y in ys: put(x, y, z, 'glass_pane')
    for z in (1805, 1807): win(LX1, z, (F + 2, F + 3))
    for x in (-714, -710): win(x, LZ1, (F + 2, F + 3))
    for z in (1800, 1804, 1806, 1808): win(LX1, z, (F2 + 2, F2 + 3))
    for z in (1797, 1800, 1803): win(LX0, z, (F2 + 1, F2 + 2)) if False else None
    for x in (-714, -712, -710): win(x, LZ1, (F2 + 2, F2 + 3))
    for x in (-715, -713): win(x, LZ0, (F2 + 3,))
    for x in range(-714, -709):
        for z in (1802, 1805, 1808): put(x, RF, z, 'glass')
    for x, z in ((-714, 1797), (-713, 1803), (-713, 1806), (-709, 1802), (-709, 1796), (-709, 1807)): put(x, F2, z, 'glowstone')
    for x, z in ((-714, 1797), (-709, 1796), (-713, 1800), (-709, 1800)): put(x, RF, z, 'glowstone')
    # площадь: скамейки лицом к пруду, урна, фонари, кашпо
    for z0 in (1800, 1806):
        for i, z in enumerate(range(z0, z0 + 4)):
            put(-702, base_y(S, H, -702, z), z, ('trapdoor:4', 'birch_stairs:1', 'birch_stairs:1', 'trapdoor:5')[i])
    put(-702, base_y(S, H, -702, 1804), 1804, 'cauldron')
    for x, z in ((-705, 1794), (-705, 1812), (-719, 1793), (-719, 1812)):
        h = H[(x, z)]; b = int(h) if h == int(h) else int(h) + 1
        if h != int(h): put(x, int(h), z, 'stonebrick')
        for i, blk in enumerate(('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')):
            put(x, b + i, z, blk)
    for x, z in ((-712, 1812), (-704, 1812)):
        h = H[(x, z)]; b = int(h) if h == int(h) else int(h) + 1
        if h != int(h): put(x, int(h), z, 'stonebrick')
        put(x, b, z, 'hardened_clay'); put(x, b + 1, z, 'leaves:4')
    return S, H, anchors


def main():
    args = parse_args()
    W = World(built_before('oldtown-6-library.json'))
    S, H, anchors = build(W)
    o, rel, order = save(S, args.out)
    print('== ПРОВЕРКИ ==')
    final = std_checks(W, S.cells, o, rel, order, H, anchors)
    print('чаровальня: полок, засчитанных столом —', enchant_power(final, TABLE), '(максимум уровня — от 15)')
    B = ((-724, -689), (1788, 1816), (58, 90))
    targets = {'портик у двери': (-706, 66, DOOR_Z), 'портик, северный край': (-706, 66, 1796), 'читальный зал 1 эт.': (-711, 66, 1804), 'у стола зачарований': (-713, 66, 1797),
               'щитовая': (-709, 66, 1796), 'зал 2 эт.': (-713, 71, 1803), 'серверная': (-709, 71, 1796),
               'у терминала ME (перед проёмом)': (-708, 71, 1799), 'перед скамейкой у пруда': (-701, 65.5, 1802),
               'у статуи (запад постамента)': (-700, 65, 1795), 'к проспекту С–Ю (север пруда)': (-693, 65, 1798),
               'переулок (−712,1790)': (-712, 67, 1790), 'главный проспект (−711,1814)': (-711, 66, 1814),
               'обход с запада (−719,1800)': (-719, 65, 1800)}
    seen, bad = walk_report(final, (-712, 66, 1815), B, targets)
    miss = pave_unreached(S, H, seen)
    print('  клетки мощения без стоянки (кроме занятых):', len(miss), miss[:6])
    lo = W.cave_top(*SHAFT)
    print('шахта: низ Y 60 | кровля каньона под ней', None if lo is None else 58 - lo)
    run = lambda neg: dl.walk_reachable(lambda x, y, z: neg.get((x, y, z)) or final(x, y, z), (-712, 66, 1815), *B)
    neg = dict(S.cells)
    for z in (1808, 1809): neg[(-714, F + 2, z)] = 'sandstone:2'; neg[(-714, F + 3, z)] = 'sandstone:2'
    print('НЕГАТИВ: лестница перегорожена — 2-й этаж недостижим:', not dl.reached(run(neg), -713, 71, 1803))
    neg = dict(S.cells); neg[(-714, F + 1, 1800)] = 'sandstone:2'; neg[(-714, F + 2, 1800)] = 'sandstone:2'
    print('НЕГАТИВ: дверь чаровальни заложена — стол недостижим:', not dl.reached(run(neg), -713, 66, 1797))
    neg = dict(S.cells); neg[(-715, F + 1, 1796)] = 'stonebrick'
    fn = lambda x, y, z: neg.get((x, y, z)) or final(x, y, z)
    print('НЕГАТИВ: блок между столом и полками — полок засчитано', enchant_power(fn, TABLE), '(ждём < 30)')
    neg = dict(S.cells); neg[(-701, base_y(Schema(W), H, -701, 1801), 1801)] = 'stonebrick'
    _, tr = fns(W, S.cells, o)
    print('НЕГАТИВ: перед скамейкой блок — ошибок',
          len(dl.check_bench_front({(x - o[0], y - o[1], z - o[2]): b for (x, y, z), b in neg.items()}, tr)), '(ждём > 0)')
    if args.fix_from:
        write_fix(W, S.cells, args.fix_from, (-719, 60, 1792), args.fix_out)
        import json
        v1 = {(e['x'] - 719, e['y'] + 60, e['z'] + 1792): e['block'] for e in json.load(open(args.fix_from))}
        f1, _ = fns(W, v1, (-719, 60, 1792))
        print('НЕГАТИВ: построенная v1 — висящих над мощением', len(floating_over_paving(f1, v1, H)), '(ждём > 0)')
    if args.preview:
        v1 = elevation(final, 'x', None, range(1814, 1789, -1), range(-690, -726, -1))
        v2 = section(final, 'z', 1795, range(-720, -690))
        v3 = section(final, 'x', -709, range(1792, 1812))
        preview(args.preview, final, (-724, -690, 1788, 1815),
                [('Вид с проспекта (с востока)', v1[0], v1[1], (62, 84)), ('Разрез Z=1795 (чаровальня, серверная, статуя)', v2[0], v2[1], (62, 84)),
                 ('Разрез X=−709', v3[0], v3[1], (62, 84))], 'Этап 6 — библиотека, площадь, статуя крипера')


if __name__ == '__main__':
    main()
