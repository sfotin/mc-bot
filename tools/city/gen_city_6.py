"""Сити, этап 6 — холм (CITY.md §7.4):

- city-6-pebbles.json — Т5 «Галька» ×3 (овальные башни, скруглённый верх, полосы белого бетона и серого
  стекла; оболочка точно по форме; пол 1-го этажа по рельефу холма, фасад в грунт — бетон), в каждой —
  электрощитовая с кабельной шахтой, стремянки ко всем этажам; дорожки на холм: площадка у «Гальки»
  X −789…−781, Z 1804…1811, тропа X −789 (Z 1794…1803) к «Гальке 1», тропа Z 1793 (X −788…−780);
- city-6-summit.json — площадка «Вершина» на плато (X −800…−792, Z 1784…1793, ход Y 76; выемка в холм
  с подпорной стенкой из каменного кирпича, по краю над склоном — парапет), лестница из каменных
  ступеней в выемке от конца Северной улицы (X −791…−785, Z 1789…1790, по блоку на ступень), скамейки,
  фонари, кашпо; воздушный шар над площадкой — висит статично, без тросов (план: Y 167…187, оболочка
  из шерсти полосами красная/жёлтая — полая, корзина тёмного дуба, стропы — забор, горелка — морской
  фонарь и оранжевое стекло).

Запуск: gen_city_6.py [--outdir schemas] [--preview docs/districts/city-6-preview.png]
Мир — World() (после постройки — built_before('city-6-pebbles.json')).
Проверки: опоры + вода + порядок (decor_lib), проходимость без прыжков от Северной улицы и тротуара
проспекта до каждого этажа (каждой части) каждой «Гальки», щитовых и площадки «Вершина»; подходы к
дверям; перепад дорожек; кровля каньона; шар не задевает «Гальку»; негатив.
"""
import argparse
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from city_lib import *  # noqa: E402,F401,F403
import plan_city_v1 as P  # noqa: E402

TOW = {t[0]: t for t in P.TOWERS}
NAMES = ['city-6-pebbles.json', 'city-6-summit.json']
PLAT = (-800, -792, 1784, 1793)
PLAT_Y = 75                          # верхний блок площадки (ход 76)
STAIR_Z = (1789, 1790)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--outdir', default=os.path.join(REPO, 'schemas'))
    p.add_argument('--preview', default=os.path.join(REPO, 'docs', 'districts', 'city-6-preview.png'))
    return p.parse_args()


def stripes(x, y, z): return 'concrete:0' if y % 3 == 0 else 'stained_glass:7'


def pebbles(W):
    Ts = []
    spec = [('t5a', 'Галька 1', 73, [(-795, 1804, 3)], ('щитовая «Гальки 1»', (-798, -796, 1797, 1799), (-795, 1798, 2), (-798, 1797))),
            ('t5b', 'Галька 2', 68, [(-784, 1803, 3)], ('щитовая «Гальки 2»', (-787, -785, 1796, 1798), (-784, 1797, 2), (-787, 1796))),
            ('t5c', 'Галька 3', 69, [(-790, 1808, 2)], ('щитовая «Гальки 3»', (-795, -793, 1807, 1809), (-792, 1808, 2), (-795, 1807)))]
    for k, name, f0, doors, room in spec:
        t = TOW[k]
        T = Tower(W, name, t[7], (t[2] - 1, t[3] + 1, t[4] - 1, t[5] + 1), f0, t[9], glass_fn=stripes, exact=True)
        T.shell()
        for d in doors: T.door(*d)
        T.room(room[0], room[1], room[2], shaft=room[3])
        Ts.append(T)
    paths = ({(x, z) for x in range(-789, -780) for z in range(1804, 1812)} - {(-789, z) for z in (1809, 1810, 1811)}) | {(-789, z) for z in range(1794, 1804)} | \
            {(x, 1793) for x in range(-788, -779)} | {(x, 1805) for x in range(-795, -789)}
    thin = {c for c in paths if W.cave_top(*c) is not None and W.surf(*c) - W.cave_top(*c) <= 4}
    return Ts, paths - thin          # над тонкой кровлей пустоты — газон (клумба), дорожка в обход


def summit(W):
    c = {}
    x0, x1, z0, z1 = PLAT
    plat = {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    for (x, z) in plat:
        g = W.surf(x, z)
        for y in range(g + 1, PLAT_Y): c[(x, y, z)] = 'stone'
        edge = x in (x0, x1) or z in (z0, z1)
        c[(x, PLAT_Y, z)] = 'quartz_block' if edge else ('double_stone_slab:8' if (x + z) % 2 else 'stone:4')
        for y in range(PLAT_Y + 1, max(g, PLAT_Y) + 3): c[(x, y, z)] = 'air'
    # лестница в выемке: ступень i (X −784−i) — блок на Y 68+i, по бокам — подпорная стенка
    stairs = {}
    for i in range(1, 8):
        x = -784 - i
        if x < x1: break
        for z in STAIR_Z:
            g = W.surf(x, z); y = 68 + i
            for yy in range(g + 1, y): c[(x, yy, z)] = 'stone'
            c[(x, y, z)] = 'stone_brick_stairs:1'
            for yy in range(y + 1, max(g, y) + 4): c[(x, yy, z)] = 'air'
            stairs[(x, z)] = y
        for z in (STAIR_Z[0] - 1, STAIR_Z[1] + 1):
            g = W.surf(x, z); y = 68 + i
            for yy in range(y, max(g, y + 1) + 1): c[(x, yy, z)] = 'stonebrick'
    # края площадки: где снаружи грунт выше — подпорная стенка из каменного кирпича, где ниже — парапет
    for (x, z) in plat:
        for a, b in N4:
            n = (x + a, z + b)
            if n in plat or n in stairs or not (-800 <= n[0]) or (n[0], n[1]) in {(s[0], s[1]) for s in stairs}: continue
            gn = W.surf(*n)
            if gn > PLAT_Y and -800 <= n[0] <= -725:
                for y in range(PLAT_Y, gn + 1): c[(n[0], y, n[1])] = 'stonebrick'
            elif gn < PLAT_Y - 1 and not (P.pebble(-795, 1799, 5.5, 5.0, 160)(n[0], PLAT_Y + 1, n[1])):
                c[(x, PLAT_Y + 1, z)] = 'stone_slab:7'
    # обстановка: скамейки лицом к югу (к городу и морю), фонари по углам, кашпо
    for bx in (-799, -795):
        c[(bx, PLAT_Y + 1, 1785)] = 'trapdoor:6'; c[(bx + 1, PLAT_Y + 1, 1785)] = 'birch_stairs:3'
        c[(bx + 2, PLAT_Y + 1, 1785)] = 'birch_stairs:3'; c[(bx + 3, PLAT_Y + 1, 1785)] = 'trapdoor:7'
    lamps = [(-799, 1792), (-793, 1792), (-793, 1784)]
    for (x, z) in lamps:
        for i, b in enumerate(('quartz_block:1', 'dark_oak_fence', 'dark_oak_fence', 'sea_lantern', 'stone_slab:7')):
            c[(x, PLAT_Y + 1 + i, z)] = b
    for (x, z) in ((-799, 1789), (-793, 1788)):
        c[(x, PLAT_Y + 1, z)] = 'hardened_clay'; c[(x, PLAT_Y + 2, z)] = 'leaves:4'
    # воздушный шар (статично): оболочка полая, полосы по сектору; корзина, стропы, горелка
    cx, cz = -795, 1787.5
    B = P.BALLOON
    for (x, y, z) in B:
        if y >= 172:
            if all((x + a, y, z + b) in B for a, b in N4) and (x, y + 1, z) in B and (x, y - 1, z) in B: continue
            sec = int((math.atan2(z - cz, x - cx) + math.pi) / (2 * math.pi) * 8) % 2
            c[(x, y, z)] = 'wool:14' if sec == 0 else 'wool:4'
        elif y >= 169: c[(x, y, z)] = 'dark_oak_fence'
        else: c[(x, y, z)] = 'planks:5'
    c[(-795, 169, 1787)] = 'sea_lantern'; c[(-795, 169, 1788)] = 'sea_lantern'
    c[(-795, 170, 1787)] = 'stained_glass:1'; c[(-795, 170, 1788)] = 'stained_glass:1'
    return c, stairs


def main():
    args = parse_args()
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
    names = [b[0] for b in BUILT]
    W = World(built_before(NAMES[0])) if NAMES[0] in names else World()
    Ts, paths = pebbles(W)
    fixed = {}
    for T in Ts:
        for (x, y, z, m) in T.doors:
            a, b = DOOR_IN[m]; fixed[(x - a, z - b)] = float(y)
    px0, px1, pz0, pz1 = P.POND
    skip = {(x, z) for x in range(px0, px1 + 1) for z in range(pz0, pz1 + 1)}    # берег пруда — не мощение
    H, anchors, bad = path_heights(W, paths | set(fixed), fixed, skip)
    pc = pave_cells(W, set(H), H)
    lost = 0
    for T in Ts:
        for k, v in pc.items():
            if T.cells.get(k) in (None, 'air'): T.cells[k] = v
        lost += T.plan_ladders()
    cells = {}
    for T in Ts:
        for k, v in T.cells.items():
            if cells.get(k) in (None, 'air'): cells[k] = v
    sc, stairs = summit(W)
    outs = []
    for nm, cc in ((NAMES[0], cells), (NAMES[1], sc)):
        o, rel, order, dims = save_schema(cc, os.path.join(args.outdir, nm))
        outs.append((nm, cc, o, rel, order))
        print(f'{nm}: origin {o[0]} {o[1]} {o[2]} | габарит {dims[0]} {dims[1]} {dims[2]} | записей {len(cc)}')
    print(f'«Галька»: этажей {[T.storeys() for T in Ts]}, стремянок-звеньев {sum(len(T.ladders) for T in Ts)}, '
          f'частей этажей без стремянки {lost}')
    print('== ПРОВЕРКИ ==')
    ALL = dict(cells); ALL.update(sc)

    def final(x, y, z):
        b = ALL.get((x, y, z)) or W.block(x, y, z)
        return 'air' if b == 'plant' else ('stone' if b == 'ground' else b)
    for nm, cc, o, rel, order in outs:
        def terr(x, y, z, o=o):
            b = W.block(x + o[0], y + o[1], z + o[2])
            return 'stone' if b == 'ground' else ('air' if b == 'plant' else b)
        errs = dl.check_water(rel, terr)
        se, wr = dl.check_supports(rel, order, terr)
        print(f'{nm}: опоры/вода/порядок постройки (decor_lib, порядок бота): ошибок {len(errs) + len(se)} | предупреждений {len(wr)}')
        for m in (errs + se + wr)[:4]: print('   ', m)
        be = dl.check_bench_front(rel, terr)
        print(f'{nm}: скамейки (место для ног): ошибок {len(be)}', be[:2])
    print('перепад дорожек между соседями > 0.5 —', len(bad), bad[:12])
    doors = [d for T in Ts for d in T.doors]
    di = door_approach_issues(final, doors)
    print('подходы к наружным дверям:', len(doors), 'ошибок', len(di), di[:2])
    lo = {}
    for (x, y, z), b in ALL.items():
        if b == 'air' and y <= W.surf(x, z): lo[(x, z)] = min(lo.get((x, z), 999), y)
    roofs = [y - W.cave_top(x, z) - 1 for (x, z), y in lo.items() if W.cave_top(x, z) is not None]
    print('кровля каньона под выемками: мин.', min(roofs) if roofs else '—', '(норма >= 3)')
    hit = [k for k in P.BALLOON if any((k[0], k[1], k[2]) in T.cells and T.cells[k] != 'air' for T in Ts)]
    print('шар задевает «Гальку»:', len(hit))
    box = ((-803, -770), (1780, 1816), (58, 165))
    starts = [(-784, 69.0, 1790), (-785, 67.0, 1812)]
    seen = set()
    for s in starts: seen |= dl.walk_reachable(final, s, *box)
    targets = {}
    for T in Ts:
        targets.update(T.level_targets()); targets.update(T.targets)
        for (x, y, z, m) in T.doors:
            a, b = DOOR_IN[m]; targets[f'{T.name}: перед дверью'] = (x - a, y, z - b)
    targets['«Вершина» (центр)'] = (-796, PLAT_Y + 1, 1789)
    targets['«Вершина» (северо-запад)'] = (-799, PLAT_Y + 1, 1786)
    bad_t = [k for k, (x, y, z) in targets.items() if not dl.reached(seen, x, y, z)]
    for k in bad_t[:8]: print(f'  маршрут → {k}: False')
    print(f'маршрутов {len(targets)} (все этажи и их части, щитовые, двери, «Вершина»), недостижимо {len(bad_t)}')
    print('ИТОГО недостижимых точек:', len(bad_t) + lost)
    neg = dict(ALL)
    for z in STAIR_Z: neg[(-788, 72, z)] = 'air'; neg[(-788, 71, z)] = 'air'; neg[(-788, 70, z)] = 'air'
    fin2 = lambda x, y, z: (lambda b: 'air' if b == 'plant' else ('stone' if b == 'ground' else b))(neg.get((x, y, z)) or W.block(x, y, z))
    s2 = dl.walk_reachable(fin2, starts[0], *box)
    print('НЕГАТИВ: убрана ступень лестницы — «Вершина» недостижима:', not dl.reached(s2, -796, PLAT_Y + 1, 1789))
    if args.preview: preview(args.preview, final)


def preview(path, final):
    from PIL import Image, ImageDraw, ImageFont
    fp = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf') if os.path.exists(f)), None)
    F = lambda n: ImageFont.truetype(fp, n) if fp else ImageFont.load_default()
    CX = dict(CL); CX.update({'concrete:0': (235, 235, 235), 'stained_glass:7': (110, 115, 120), 'wool:14': (200, 50, 45),
                              'wool:4': (235, 200, 40), 'planks:5': (70, 45, 25), 'quartz_block': (240, 238, 232),
                              'stone_brick_stairs': (125, 125, 125), 'stonebrick': (125, 125, 125)})
    cc = lambda b: CX.get(b) or CX.get(b.split(':')[0]) or col(b)
    S = 5
    img = Image.new('RGB', (2 * 40 * S + 60, 135 * S + 40), 'white')
    dr = ImageDraw.Draw(img)
    dr.text((10, 4), 'Сити, холм: «Галька» ×3, «Вершина», шар — вид с юга (слева) и с востока (справа), Y 60…190', fill='black', font=F(12))
    for side in (0, 1):
        ox = 20 + side * (40 * S + 20)
        for u in range(40):
            for y in range(60, 191, 1):
                yy = 30 + (190 - y) * S // 1 // 1 * 1
                if yy > 30 + 130 * S: continue
                rng = range(1860, 1774, -1) if side == 0 else range(-760, -806, -1)
                for w in rng:
                    x, z = (-805 + u, w) if side == 0 else (w, 1776 + u)
                    b = final(x, y, z)
                    if b in ('air',): continue
                    c = (190, 180, 150) if b in ('stone', 'grass', 'dirt') else cc(b)
                    dr.rectangle([ox + u * S, 30 + (190 - y) * S // 1, ox + (u + 1) * S - 1, 30 + (191 - y) * S - 1], fill=c)
                    break
    img.save(path)
    print('превью', path)


if __name__ == '__main__':
    main()
