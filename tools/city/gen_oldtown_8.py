"""Старый город, этап 8: исторические кварталы К1–К6 — ряды домов 3–4 этажа (CITY.md §7.3).

Каждый квартал — отдельная схема schemas/oldtown-8-k<N>.json. Дом (модуль house()):
- фасад к улице, дверь по центру (у К6 — сдвинута, чтобы вход не упирался в воду),
  нажимная плита изнутри (пол — еловые доски — деревянная, CITY.md §6);
- этажи по 4 блока, пол 1-го этажа — вровень с улицей перед дверью (разница ≤ 0.5);
- стены — белый бетон, песчаник или пастельная терракота, углы и пояса — кварц или
  каменный кирпич; окна 1×2 на фасаде и задней стене;
- кровля — двускатная терракотовая (конёк вдоль улицы) или плоская с парапетом;
- внутри этажи пустые (обстановка — игрок), свет — светокамень в потолках (и на
  чердаке), подъём — стремянка у задней стены через проёмы в перекрытиях;
- жилой квартал — одно здание в смысле CITY.md §6: одна электрощитовая 3×3 на
  квартал в первом этаже одного из домов (вход с улицы, прихожая со стремянкой,
  дверь в щитовую), кабельная шахта 1×1 от Y 60 с люком iron_trapdoor:8.
Полосы между домами и улицей (К3 юг, К4, К6) мостятся; дворы и сады — газон, деревья.

Запуск: gen_oldtown_8.py [--only k1,k2,...] [--outdir schemas]
                         [--preview docs/districts/oldtown-8-preview.png]
Мир — World(built_before('oldtown-8-k1.json')) (кварталы не пересекаются).
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oldtown_lib import *  # noqa: E402,F403

STY = [('concrete:0', 'quartz_block'), ('stained_hardened_clay:4', 'quartz_block'), ('sandstone:2', 'stonebrick'),
       ('stained_hardened_clay:6', 'quartz_block'), ('stained_hardened_clay:0', 'stonebrick'), ('stained_hardened_clay:1', 'quartz_block')]
FLOORS = [3, 4, 3, 3, 4, 3, 4]
FLAT_EVERY = 3                 # каждый третий дом — плоская кровля

# квартал: (дома: (x0, x1, z0, z1, фасад, электрощитовая 'A'|'B'|None, u двери или None), полосы мощения, газоны, деревья)
Q = {
    'k1': dict(houses=[(-724, -719, 1782, 1788, 'S', 'A', None), (-718, -714, 1782, 1788, 'S', None, None),
                       (-713, -709, 1782, 1788, 'S', None, None), (-708, -704, 1782, 1788, 'S', None, None),
                       (-703, -699, 1782, 1788, 'S', None, None), (-698, -694, 1782, 1788, 'S', None, None)],
               strips=[], lawns=[(-724, -694, 1780, 1781)], trees=[]),
    'k2': dict(houses=[(-724, -720, 1792, 1798, 'E', 'B', None), (-724, -720, 1799, 1805, 'E', None, None),
                       (-724, -720, 1806, 1812, 'E', None, None)], strips=[], lawns=[], trees=[]),
    'k3': dict(houses=[(-724, -719, 1819, 1825, 'N', 'A', None), (-718, -714, 1819, 1825, 'N', None, None),
                       (-713, -709, 1819, 1825, 'N', None, None), (-724, -720, 1831, 1837, 'S', None, None),
                       (-719, -714, 1831, 1837, 'S', None, None), (-713, -709, 1831, 1837, 'S', None, None),
                       (-715, -709, 1826, 1830, 'E', None, None)],
               strips=[(-724, -709, 1838, 1838)], lawns=[(-724, -716, 1826, 1830)], trees=[(-720, 1828)]),
    'k4': dict(houses=[(-724, -718, 1842, 1847, 'S', 'B', None), (-717, -712, 1842, 1847, 'S', None, None),
                       (-711, -706, 1842, 1847, 'S', None, None), (-705, -700, 1842, 1847, 'S', None, None)],
               strips=[(-724, -701, 1848, 1848)], lawns=[], trees=[]),
    'k5': dict(houses=[(-687, -683, 1786, 1792, 'S', 'A', None), (-682, -678, 1786, 1792, 'S', None, None),
                       (-677, -672, 1786, 1792, 'S', None, None), (-671, -666, 1786, 1792, 'S', None, None),
                       (-665, -661, 1786, 1792, 'S', None, None)],
               strips=[], lawns=[(-687, -661, 1780, 1785)], trees=[(-683, 1782), (-674, 1782), (-665, 1782)]),
    'k6': dict(houses=[(-675, -671, 1841, 1847, 'S', 'A', None), (-670, -666, 1841, 1847, 'S', None, None),
                       (-665, -661, 1841, 1847, 'S', None, 1)],
               strips=[(-675, -664, 1848, 1848)], lawns=[(-675, -661, 1840, 1840)], trees=[]),
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--only', default='k1,k2,k3,k4,k5,k6')
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'oldtown-8-preview.png'))
    return p.parse_args()


class Frame:
    """Локальные координаты дома: u — вдоль фасада, v — вглубь от фасада (v=0 — фасадная стена)."""
    def __init__(self, x0, x1, z0, z1, front):
        self.x0, self.x1, self.z0, self.z1, self.f = x0, x1, z0, z1, front
        self.W = (x1 - x0 + 1) if front in 'NS' else (z1 - z0 + 1)
        self.D = (z1 - z0 + 1) if front in 'NS' else (x1 - x0 + 1)

    def xz(self, u, v):
        f = self.f
        if f == 'S': return self.x0 + u, self.z1 - v
        if f == 'N': return self.x1 - u, self.z0 + v
        if f == 'E': return self.x1 - v, self.z0 + u
        return self.x0 + v, self.z1 - u                      # W

    def dir_in(self):          # единичный вектор «вглубь» (от улицы)
        return {'S': (0, -1), 'N': (0, 1), 'E': (-1, 0), 'W': (1, 0)}[self.f]


DOOR_META = {'S': 3, 'N': 1, 'E': 2, 'W': 0}               # дверь открывается внутрь
STAIR_IN = {'S': 3, 'N': 2, 'E': 1, 'W': 0}                # ступенька «вверх» — вглубь дома


def ladder_meta(dx, dz):   # стремянка крепится к блоку со стороны (dx, dz)
    return {(0, -1): 3, (0, 1): 2, (-1, 0): 5, (1, 0): 4}[(dx, dz)]


def house(S, W, fr, n, style, elec, door_u, t_front, flat):
    """Строит дом; возвращает цели проверки проходимости и данные о щитовой."""
    put = S.put
    wall, trim = style
    Wd, D = fr.W, fr.D
    f0 = math.ceil(t_front) - 1                            # блок пола 1-го этажа
    T = f0 + 4 * n
    uc = door_u if door_u is not None else Wd // 2
    if elec == 'B': uc = Wd - 2
    di = fr.dir_in()
    # фундамент, пол, стены, перекрытия
    for u in range(Wd):
        for v in range(D):
            x, z = fr.xz(u, v)
            edge = u in (0, Wd - 1) or v in (0, D - 1)
            S.ground_to(x, z, f0, trim if edge else 'planks:1')
            for k in range(n):
                y0 = f0 + 4 * k
                if k: put(x, y0, z, trim if edge else 'planks:1')
                for y in range(y0 + 1, y0 + 4):
                    corner = u in (0, Wd - 1) and v in (0, D - 1)
                    put(x, y, z, (trim if corner else wall) if edge else 'air')
            put(x, T, z, trim if edge else ('double_stone_slab' if flat else 'planks:1'))   # плоская кровля — гладкий камень
    # кровля
    if flat:
        for u in range(Wd):
            for v in range(D):
                if u in (0, Wd - 1) or v in (0, D - 1):
                    x, z = fr.xz(u, v); put(x, T + 1, z, 'stone_slab:7')
    else:
        rows = (D + 1) // 2
        for i in range(rows):
            for u in range(Wd):
                for v, m in ((i, STAIR_IN[fr.f]), (D - 1 - i, {3: 2, 2: 3, 1: 0, 0: 1}[STAIR_IN[fr.f]])):
                    x, z = fr.xz(u, v); put(x, T + 1 + i, z, f'brick_stairs:{m}')
            if D % 2 == 1 and i == rows - 1:
                for u in range(Wd):
                    x, z = fr.xz(u, i); put(x, T + 1 + i, z, 'brick_block'); put(x, T + 2 + i, z, 'stone_slab:4')
        for u in (0, Wd - 1):                               # фронтоны (торцевые стены)
            for v in range(1, D - 1):
                h = min(v, D - 1 - v)
                x, z = fr.xz(u, v)
                for y in range(T + 1, T + 1 + h): put(x, y, z, wall)
    # окна
    for k in range(n):
        y0 = f0 + 4 * k
        for u in range(1, Wd - 1):
            if (u - uc) % 2: continue
            if not (k == 0 and u == uc):
                x, z = fr.xz(u, 0); put(x, y0 + 2, z, 'glass_pane'); put(x, y0 + 3, z, 'glass_pane')
        for u in range(2, Wd - 1, 2):
            x, z = fr.xz(u, D - 1); put(x, y0 + 2, z, 'glass_pane'); put(x, y0 + 3, z, 'glass_pane')
    # дверь и плита
    dx, dz = fr.xz(uc, 0)
    S.door(dx, f0 + 1, dz, DOOR_META[fr.f], 'spruce_door', 8)
    ix, iz = fr.xz(uc, 1)
    put(ix, f0 + 1, iz, 'wooden_pressure_plate')
    targets = {}
    # стремянка
    if elec == 'A':
        lu, lv = 1, 1
        att = fr.xz(0, 1); lx, lz = fr.xz(lu, lv)
    elif elec == 'B':
        lu, lv = Wd - 2, D - 2
        att = fr.xz(lu, D - 1); lx, lz = fr.xz(lu, lv)
    else:
        lu, lv = 1, D - 2
        att = fr.xz(1, D - 1); lx, lz = fr.xz(lu, lv)
    lm = ladder_meta(att[0] - lx, att[1] - lz)
    for y in range(f0 + 1, f0 + 4 * (n - 1) + 1): put(lx, y, lz, f'ladder:{lm}')
    # окно за стремянкой — нельзя (стремянке нужен сплошной блок)
    for k in range(n):
        put(att[0], f0 + 4 * k + 2, att[1], wall); put(att[0], f0 + 4 * k + 3, att[1], wall)
    # свет
    cu, cv = Wd // 2, (D - 1) // 2
    for k in range(1, n + 1):
        x, z = fr.xz(cu if (cu, cv) != (lu, lv) else cu + 1, cv)
        put(x, f0 + 4 * k, z, 'glowstone')
    # щитовая
    el = None
    if elec == 'A':            # прихожая v=1, перегородка v=2 с дверью, щитовая v=3…D−2
        for u in range(1, Wd - 1):
            x, z = fr.xz(u, 2)
            for y in (f0 + 1, f0 + 2, f0 + 3): put(x, y, z, wall)
        px, pz = fr.xz(uc, 2)
        S.door(px, f0 + 1, pz, DOOR_META[fr.f], 'spruce_door', 8)
        rx, rz = fr.xz(uc, 3); put(rx, f0 + 1, rz, 'wooden_pressure_plate')
        sh = fr.xz(Wd - 2, D - 2)
        el = (sh, f0); targets['щитовая'] = (rx, f0 + 1, rz)
    elif elec == 'B':          # щитовая u=1…3, перегородка u=4 с дверью, коридор u=5
        for v in range(1, D - 1):
            x, z = fr.xz(4, v)
            for y in (f0 + 1, f0 + 2, f0 + 3): put(x, y, z, wall)
        px, pz = fr.xz(4, 2)
        S.door(px, f0 + 1, pz, {'S': 2, 'N': 0, 'E': 3, 'W': 1}[fr.f], 'spruce_door', 8)
        for u in (3, 5):
            x, z = fr.xz(u, 2); put(x, f0 + 1, z, 'wooden_pressure_plate')
        sh = fr.xz(1, D - 2)
        x, z = fr.xz(2, 2); el = (sh, f0); targets['щитовая'] = (x, f0 + 1, z)
    if el:
        (sx, sz), fl = el
        for y in range(60, fl): put(sx, y, sz, 'air')
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                if (a, b) == (0, 0): continue
                for y in range(59, fl):
                    if S.cells.get((sx + a, y, sz + b), W.block(sx + a, y, sz + b)) in ('air', 'plant', 'water'):
                        put(sx + a, y, sz + b, 'stonebrick')
        put(sx, fl, sz, 'iron_trapdoor:8')
    ex, ez = fr.xz(uc, 1)
    targets['1 эт.'] = (ex, f0 + 1, ez)
    tx, tz = fr.xz(lu + (1 if lu < Wd - 2 else -1), lv)
    targets[f'{n} эт.'] = (tx, f0 + 4 * (n - 1) + 1, tz)
    fx, fz = fr.xz(uc, -1)
    return targets, (fx, t_front, fz), el


def build_quarter(W, key, idx0):
    spec = Q[key]
    S = Schema(W)
    strips = [(x, z) for (a, b, c, d) in spec['strips'] for x in range(a, b + 1) for z in range(c, d + 1)
              if W.block(x, W.surf(x, z) + 1, z) != 'water']
    H, anchors = paving_heights(W, strips) if strips else ({}, {})
    S.pave(H, lambda x, z: ('double_stone_slab', 'stone_slab'))
    for (a, b, c, d) in spec['lawns']:
        for x in range(a, b + 1):
            for z in range(c, d + 1):
                g = W.surf(x, z)
                if W.block(x, g, z) in ('ground', 'grass'):
                    for y in range(g + 1, S.plant_top(x, z) + 1): put_air = S.put(x, y, z, 'air')
    for (x, z) in spec['trees']:
        g = W.surf(x, z)
        for y in range(g + 1, g + 5): S.put(x, y, z, 'log:0')
        for a in range(-1, 2):
            for b in range(-1, 2):
                for y in (g + 4, g + 5):
                    if (a, b) != (0, 0) or y == g + 5: S.put(x + a, y, z + b, 'leaves:4')
    info = []
    for i, (x0, x1, z0, z1, f, elec, du) in enumerate(spec['houses']):
        fr = Frame(x0, x1, z0, z1, f)
        uc = du if du is not None else (fr.W - 2 if elec == 'B' else fr.W // 2)
        fx, fz = fr.xz(uc, -1)
        t = H.get((fx, fz)) or street_top(W, fx, fz)
        if t is None: t = W.surf(fx, fz) + 1.0
        k = idx0 + i
        n = FLOORS[k % len(FLOORS)]
        tg, front, el = house(S, W, fr, n, STY[k % len(STY)], elec, du, t, (k % FLAT_EVERY) == 2)
        info.append((fr, n, tg, front, el))
    return S, H, anchors, info


def main():
    args = parse_args()
    W = World(built_before('oldtown-8-k1.json'))
    idx = 0; finals = {}
    total_bad = 0
    for key in ('k1', 'k2', 'k3', 'k4', 'k5', 'k6'):
        S, H, anchors, info = build_quarter(W, key, idx)
        idx += len(Q[key]['houses'])
        if key not in args.only.split(','): continue
        print(f'===== {key.upper()}: домов {len(info)}, этажность {[n for _, n, *_ in info]} =====')
        o, rel, order = save(S, os.path.join(args.outdir, f'oldtown-8-{key}.json'))
        final = std_checks(W, S.cells, o, rel, order, H, anchors) if H else None
        if final is None:
            final, tr = fns(W, S.cells, o)
            errs = dl.check_water(rel, tr); se, wr = dl.check_supports(rel, order, tr)
            print('опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок', len(errs) + len(se), '| предупреждений', len(wr))
            lo = {}
            for (x, y, z) in S.cells: lo[(x, z)] = min(lo.get((x, z), 999), y)
            roofs = [y - W.cave_top(x, z) - 1 for (x, z), y in lo.items() if W.cave_top(x, z) is not None]
            print('кровля каньона под схемой: мин.', min(roofs) if roofs else '—', '(норма >= 3)')
        finals[key] = final
        bad = 0; els = 0
        for fr, n, tg, (fx, t, fz), el in info:
            seen = dl.walk_reachable(final, (fx, t, fz), (min(fr.x0, fr.x1) - 3, max(fr.x0, fr.x1) + 3),
                                     (min(fr.z0, fr.z1) - 3, max(fr.z0, fr.z1) + 3), (58, 100))
            res = {k: dl.reached(seen, *p) for k, p in tg.items()}
            bad += sum(1 for v in res.values() if not v); els += 1 if el else 0
            if not all(res.values()): print('  НЕ ДОСТИЖИМО:', fr.x0, fr.z0, res)
        print(f'  проходимость: домов {len(info)}, с улицы до 1-го и верхнего этажа и в щитовую — недостижимых {bad}; щитовых {els}')
        total_bad += bad
        if key == 'k1':        # негатив: разорванная стремянка — верхний этаж недостижим
            fr, n, tg, (fx, t, fz), el = info[1]
            lx, lz = fr.xz(1, fr.D - 2); f0 = math.ceil(t) - 1
            neg = dict(S.cells); neg[(lx, f0 + 3, lz)] = 'air'; neg[(lx, f0 + 4, lz)] = 'planks:1'
            s2 = dl.walk_reachable(lambda x, y, z: neg.get((x, y, z)) or final(x, y, z), (fx, t, fz),
                                   (fr.x0 - 3, fr.x1 + 3), (fr.z0 - 3, fr.z1 + 3), (58, 100))
            k_top = [k for k in tg if k.endswith('эт.') and k != '1 эт.'][0]
            print('НЕГАТИВ: стремянка перекрыта полом — верхний этаж недостижим:', not dl.reached(s2, *tg[k_top]))
    print('ИТОГО недостижимых точек:', total_bad)
    if args.preview and finals:
        def fin(x, y, z):
            for f in finals.values():
                b = f(x, y, z)
                if b not in ('air',) and b != W.block(x, y, z): return b
            b = W.block(x, y, z); return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
        v1 = elevation(fin, 'z', None, range(-726, -658), range(1795, 1775, -1))
        v2 = elevation(fin, 'z', None, range(-726, -658), range(1852, 1830, -1))
        v3 = elevation(fin, 'x', None, range(1850, 1776, -1), range(-728, -700))
        preview(args.preview, fin, (-726, -659, 1777, 1850),
                [('Север: К1, К5 (вид с юга)', v1[0], v1[1], (62, 90)), ('Юг: К4, К6 (вид с моря)', v2[0], v2[1], (62, 90)),
                 ('Запад: К1–К4 (вид с запада)', v3[0], v3[1], (62, 90))], 'Этап 8 — кварталы К1–К6')


if __name__ == '__main__':
    main()
